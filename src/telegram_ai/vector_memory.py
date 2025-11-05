"""Векторное хранилище для семантического поиска в истории диалогов."""

import logging
from pathlib import Path
from typing import Dict, List, Optional

try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False

logger = logging.getLogger(__name__)


class VectorMemory:
    """Векторное хранилище для семантического поиска сообщений."""

    def __init__(
        self,
        persist_directory: str = "./data/chroma_db",
        collection_name: str = "messages",
        ai_client=None,
        enabled: bool = True,
    ):
        """
        Инициализация VectorMemory.

        Args:
            persist_directory: Директория для хранения ChromaDB
            collection_name: Имя коллекции в ChromaDB
            ai_client: Экземпляр AIClient для получения embeddings (опционально)
            enabled: Включить векторный поиск
        """
        self.enabled = enabled
        self.ai_client = ai_client
        self.collection_name = collection_name
        self.persist_directory = Path(persist_directory)
        self.persist_directory.mkdir(parents=True, exist_ok=True)

        if not CHROMADB_AVAILABLE:
            logger.warning("chromadb not available, vector search disabled")
            self.enabled = False
            self.client = None
            self.collection = None
            return

        if not self.enabled:
            self.client = None
            self.collection = None
            logger.info("VectorMemory disabled")
            return

        try:
            # Инициализируем ChromaDB клиент
            self.client = chromadb.PersistentClient(
                path=str(self.persist_directory),
                settings=Settings(anonymized_telemetry=False),
            )

            # Получаем или создаем коллекцию
            self.collection = self.client.get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"},  # Используем cosine similarity
            )

            logger.info(
                f"VectorMemory initialized: collection={collection_name}, "
                f"persist_directory={persist_directory}"
            )
        except Exception as e:
            logger.error(f"Error initializing VectorMemory: {e}", exc_info=True)
            self.enabled = False
            self.client = None
            self.collection = None

    async def get_embedding(self, text: str) -> Optional[List[float]]:
        """
        Получить embedding для текста.

        Args:
            text: Текст для векторизации

        Returns:
            Список чисел (embedding) или None если не удалось получить
        """
        if not self.enabled or not self.ai_client:
            return None

        # Если LLM API поддерживает embeddings endpoint - используем его
        # Иначе используем встроенные embeddings ChromaDB
        try:
            # Пробуем получить embeddings через LLM API
            embedding = await self._get_embedding_from_api(text)
            if embedding:
                return embedding
        except Exception as e:
            logger.debug(f"Failed to get embedding from API: {e}")

        # Fallback: используем встроенные embeddings ChromaDB
        # ChromaDB автоматически создаст embeddings при добавлении документов
        return None

    async def _get_embedding_from_api(self, text: str) -> Optional[List[float]]:
        """
        Получить embedding через LLM API (если поддерживается).

        Args:
            text: Текст для векторизации

        Returns:
            Список чисел (embedding) или None
        """
        if not self.ai_client:
            return None

        try:
            # Проверяем, поддерживает ли API embeddings endpoint
            # OpenAI-compatible API обычно имеет /v1/embeddings
            url = f"{self.ai_client.base_url}/v1/embeddings"
            headers = {}
            if self.ai_client.api_key:
                headers["Authorization"] = f"Bearer {self.ai_client.api_key}"

            async with self.ai_client.client as client:
                response = await client.post(
                    url,
                    json={"input": text, "model": self.ai_client.model},
                    headers=headers,
                    timeout=self.ai_client.timeout,
                )
                response.raise_for_status()
                data = response.json()
                if "data" in data and len(data["data"]) > 0:
                    return data["data"][0]["embedding"]
        except Exception as e:
            logger.debug(f"Embeddings API not available or error: {e}")
            return None

        return None

    async def add_message(
        self,
        message_id: int,
        user_id: int,
        conversation_id: int,
        content: str,
        role: str,
        timestamp: Optional[str] = None,
    ) -> bool:
        """
        Добавить сообщение в векторное хранилище.

        Args:
            message_id: ID сообщения из БД
            user_id: ID пользователя Telegram
            conversation_id: ID разговора
            content: Текст сообщения
            role: Роль ('user' или 'assistant')
            timestamp: Временная метка (опционально)

        Returns:
            True если успешно добавлено, False иначе
        """
        if not self.enabled or not self.collection:
            return False

        if not content or not content.strip():
            return False

        try:
            # Получаем embedding если доступен API
            embedding = await self.get_embedding(content)

            # Формируем уникальный ID для документа
            doc_id = f"msg_{message_id}_user_{user_id}_conv_{conversation_id}"

            # Метаданные для фильтрации
            metadata = {
                "message_id": message_id,
                "user_id": user_id,
                "conversation_id": conversation_id,
                "role": role,
            }
            if timestamp:
                metadata["timestamp"] = timestamp

            # Добавляем в коллекцию
            # Если embedding не получен - ChromaDB создаст его автоматически
            if embedding:
                self.collection.add(
                    ids=[doc_id],
                    embeddings=[embedding],
                    documents=[content],
                    metadatas=[metadata],
                )
            else:
                # Используем встроенные embeddings ChromaDB
                self.collection.add(
                    ids=[doc_id],
                    documents=[content],
                    metadatas=[metadata],
                )

            logger.debug(f"Added message {message_id} to vector store")
            return True

        except Exception as e:
            logger.error(f"Error adding message to vector store: {e}", exc_info=True)
            return False

    async def search_relevant_messages(
        self,
        query: str,
        user_id: int,
        conversation_id: Optional[int] = None,
        limit: int = 5,
        min_score: float = 0.7,
    ) -> List[Dict]:
        """
        Найти релевантные сообщения по семантическому поиску.

        Args:
            query: Поисковый запрос
            user_id: ID пользователя для фильтрации
            conversation_id: ID разговора для фильтрации (опционально)
            limit: Максимальное количество результатов
            min_score: Минимальный score для включения результата

        Returns:
            Список словарей с найденными сообщениями:
            [{"message_id": int, "content": str, "role": str, "score": float, ...}, ...]
        """
        if not self.enabled or not self.collection:
            return []

        if not query or not query.strip():
            return []

        try:
            # Формируем фильтр по user_id
            where_filter = {"user_id": user_id}
            if conversation_id is not None:
                where_filter["conversation_id"] = conversation_id

            # Получаем embedding для запроса
            query_embedding = await self.get_embedding(query)

            # Выполняем поиск
            if query_embedding:
                results = self.collection.query(
                    query_embeddings=[query_embedding],
                    n_results=limit,
                    where=where_filter,
                )
            else:
                # Используем текстовый поиск (ChromaDB создаст embedding автоматически)
                results = self.collection.query(
                    query_texts=[query],
                    n_results=limit,
                    where=where_filter,
                )

            # Обрабатываем результаты
            found_messages = []
            if results and "ids" in results and len(results["ids"]) > 0:
                for i, doc_id in enumerate(results["ids"][0]):
                    if i < len(results["metadatas"][0]) and i < len(results["documents"][0]):
                        metadata = results["metadatas"][0][i]
                        content = results["documents"][0][i]

                        # Получаем score (расстояние)
                        distance = 0.0
                        if "distances" in results and len(results["distances"]) > 0:
                            distance = results["distances"][0][i]

                        # Конвертируем расстояние в score (cosine distance -> similarity)
                        # cosine distance: 0 = идентично, 2 = противоположно
                        # similarity: 1 - distance/2
                        score = 1.0 - (distance / 2.0) if distance else 0.0

                        if score >= min_score:
                            found_messages.append(
                                {
                                    "message_id": metadata.get("message_id"),
                                    "content": content,
                                    "role": metadata.get("role", "user"),
                                    "score": score,
                                    "conversation_id": metadata.get("conversation_id"),
                                    "timestamp": metadata.get("timestamp"),
                                }
                            )

            logger.debug(
                f"Found {len(found_messages)} relevant messages for query: {query[:50]}..."
            )
            return found_messages

        except Exception as e:
            logger.error(f"Error searching vector store: {e}", exc_info=True)
            return []

    def delete_message(self, message_id: int, user_id: int, conversation_id: int) -> bool:
        """
        Удалить сообщение из векторного хранилища.

        Args:
            message_id: ID сообщения
            user_id: ID пользователя
            conversation_id: ID разговора

        Returns:
            True если успешно удалено, False иначе
        """
        if not self.enabled or not self.collection:
            return False

        try:
            doc_id = f"msg_{message_id}_user_{user_id}_conv_{conversation_id}"
            self.collection.delete(ids=[doc_id])
            logger.debug(f"Deleted message {message_id} from vector store")
            return True
        except Exception as e:
            logger.error(f"Error deleting message from vector store: {e}", exc_info=True)
            return False

    def delete_conversation(self, conversation_id: int, user_id: int) -> bool:
        """
        Удалить все сообщения разговора из векторного хранилища.

        Args:
            conversation_id: ID разговора
            user_id: ID пользователя

        Returns:
            True если успешно удалено, False иначе
        """
        if not self.enabled or not self.collection:
            return False

        try:
            self.collection.delete(
                where={"conversation_id": conversation_id, "user_id": user_id}
            )
            logger.debug(f"Deleted conversation {conversation_id} from vector store")
            return True
        except Exception as e:
            logger.error(
                f"Error deleting conversation from vector store: {e}", exc_info=True
            )
            return False

