"""RAG система для поиска актуальной информации о компании/услугах."""

import logging
from pathlib import Path
from typing import Dict, List, Optional

from .vector_memory import VectorMemory

logger = logging.getLogger(__name__)


class RAGSystem:
    """RAG система для поиска релевантной информации из документации компании."""

    def __init__(
        self,
        vector_memory: Optional[VectorMemory] = None,
        enabled: bool = True,
        knowledge_base_path: Optional[str] = None,
        max_results: int = 3,
        min_score: float = 0.7,
    ):
        """
        Инициализация RAG системы.

        Args:
            vector_memory: Экземпляр VectorMemory для векторного поиска
            enabled: Включить RAG систему
            knowledge_base_path: Путь к директории с документацией (опционально)
            max_results: Максимальное количество результатов поиска
            min_score: Минимальный score для включения результата
        """
        self.enabled = enabled
        self.knowledge_base_path = Path(knowledge_base_path) if knowledge_base_path else None
        self.max_results = max_results
        self.min_score = min_score
        self.rag_collection = None
        self.rag_collection_name = None

        # Создаем отдельную коллекцию для RAG (отдельно от истории сообщений)
        if enabled and vector_memory:
            self.vector_memory = vector_memory
            # Используем отдельную коллекцию для RAG
            self.rag_collection_name = "rag_knowledge_base"
            self._init_rag_collection()
        else:
            self.vector_memory = None
            logger.info("RAG system disabled")

    def _init_rag_collection(self):
        """Инициализировать коллекцию для RAG если нужно."""
        if not self.enabled or not self.vector_memory or not self.vector_memory.enabled:
            return

        try:
            # Создаем отдельную коллекцию для RAG
            if self.vector_memory.client:
                self.rag_collection = self.vector_memory.client.get_or_create_collection(
                    name=self.rag_collection_name,
                    metadata={"hnsw:space": "cosine"},
                )
                logger.info(f"RAG collection initialized: {self.rag_collection_name}")
            else:
                self.rag_collection = None
        except Exception as e:
            logger.error(f"Error initializing RAG collection: {e}", exc_info=True)
            self.rag_collection = None
            self.enabled = False

    async def load_knowledge_base(self) -> int:
        """
        Загрузить документацию из knowledge_base_path в векторное хранилище.

        Returns:
            Количество загруженных документов
        """
        if not self.enabled or not self.knowledge_base_path or not self.rag_collection:
            logger.warning("RAG system not enabled or knowledge base path not set")
            return 0

        if not self.knowledge_base_path.exists():
            logger.warning(f"Knowledge base path does not exist: {self.knowledge_base_path}")
            return 0

        loaded_count = 0

        try:
            # Поддерживаем текстовые файлы (.txt, .md)
            supported_extensions = {".txt", ".md"}
            files = [
                f
                for f in self.knowledge_base_path.rglob("*")
                if f.is_file() and f.suffix.lower() in supported_extensions
            ]

            for file_path in files:
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()

                    if not content.strip():
                        continue

                    # Разбиваем на чанки для лучшего поиска
                    chunks = self._split_into_chunks(content, chunk_size=500)

                    for i, chunk in enumerate(chunks):
                        doc_id = f"doc_{file_path.stem}_{i}"
                        metadata = {
                            "file_path": str(file_path.relative_to(self.knowledge_base_path)),
                            "chunk_index": i,
                            "total_chunks": len(chunks),
                        }

                        # Получаем embedding если доступен
                        embedding = await self.vector_memory.get_embedding(chunk)

                        if embedding:
                            self.rag_collection.add(
                                ids=[doc_id],
                                embeddings=[embedding],
                                documents=[chunk],
                                metadatas=[metadata],
                            )
                        else:
                            # Используем встроенные embeddings ChromaDB
                            self.rag_collection.add(
                                ids=[doc_id],
                                documents=[chunk],
                                metadatas=[metadata],
                            )

                        loaded_count += 1

                    logger.info(f"Loaded {len(chunks)} chunks from {file_path.name}")
                except Exception as e:
                    logger.error(f"Error loading file {file_path}: {e}", exc_info=True)
                    continue

            logger.info(f"Knowledge base loaded: {loaded_count} chunks from {len(files)} files")
            return loaded_count

        except Exception as e:
            logger.error(f"Error loading knowledge base: {e}", exc_info=True)
            return loaded_count

    def _split_into_chunks(self, text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
        """
        Разбить текст на чанки с перекрытием.

        Args:
            text: Текст для разбиения
            chunk_size: Размер чанка в символах
            overlap: Перекрытие между чанками в символах

        Returns:
            Список чанков
        """
        if len(text) <= chunk_size:
            return [text]

        chunks = []
        start = 0

        while start < len(text):
            end = start + chunk_size

            # Пытаемся разбить по предложениям для лучшей гранулярности
            if end < len(text):
                # Ищем последнюю точку/перенос строки перед end
                last_period = text.rfind(".", start, end)
                last_newline = text.rfind("\n", start, end)

                if last_period > start or last_newline > start:
                    end = max(last_period, last_newline) + 1

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            start = end - overlap

        return chunks

    async def search_relevant_info(self, query: str) -> List[Dict]:
        """
        Найти релевантную информацию из базы знаний.

        Args:
            query: Поисковый запрос

        Returns:
            Список словарей с найденной информацией:
            [{"content": str, "file_path": str, "score": float, ...}, ...]
        """
        if not self.enabled or not self.rag_collection:
            return []

        if not query or not query.strip():
            return []

        try:
            # Получаем embedding для запроса
            query_embedding = await self.vector_memory.get_embedding(query)

            # Выполняем поиск
            if query_embedding:
                results = self.rag_collection.query(
                    query_embeddings=[query_embedding],
                    n_results=self.max_results,
                )
            else:
                # Используем текстовый поиск
                results = self.rag_collection.query(
                    query_texts=[query],
                    n_results=self.max_results,
                )

            # Обрабатываем результаты
            found_info = []
            if results and "ids" in results and len(results["ids"]) > 0:
                for i, doc_id in enumerate(results["ids"][0]):
                    if i < len(results["metadatas"][0]) and i < len(results["documents"][0]):
                        metadata = results["metadatas"][0][i]
                        content = results["documents"][0][i]

                        # Получаем score
                        distance = 0.0
                        if "distances" in results and len(results["distances"]) > 0:
                            distance = results["distances"][0][i]

                        # Конвертируем расстояние в score
                        score = 1.0 - (distance / 2.0) if distance else 0.0

                        if score >= self.min_score:
                            found_info.append(
                                {
                                    "content": content,
                                    "file_path": metadata.get("file_path", ""),
                                    "score": score,
                                    "chunk_index": metadata.get("chunk_index", 0),
                                }
                            )

            logger.debug(
                f"Found {len(found_info)} relevant info chunks for query: {query[:50]}..."
            )
            return found_info

        except Exception as e:
            logger.error(f"Error searching RAG knowledge base: {e}", exc_info=True)
            return []

    def format_context(self, found_info: List[Dict]) -> str:
        """
        Форматировать найденную информацию для включения в промпт.

        Args:
            found_info: Список найденной информации

        Returns:
            Отформатированная строка для включения в системный промпт
        """
        if not found_info:
            return ""

        context_parts = ["\n\n📚 **Релевантная информация из базы знаний:**\n"]

        for i, info in enumerate(found_info, 1):
            content = info["content"]
            file_path = info.get("file_path", "unknown")
            score = info.get("score", 0.0)

            context_parts.append(f"\n--- Фрагмент {i} (из {file_path}, релевантность: {score:.2f}) ---\n{content}")

        context_parts.append(
            "\n\n⚠️ **Важно:** Используй эту информацию для ответа на вопросы о компании/услугах. "
            "Если информация из базы знаний противоречит твоим знаниям, приоритет имеет информация из базы знаний."
        )

        return "\n".join(context_parts)

