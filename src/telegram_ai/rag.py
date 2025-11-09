"""RAG система для поиска актуальной информации о компании/услугах."""

import logging
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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
        log_stats_interval: int = 100,
    ):
        """
        Инициализация RAG системы.

        Args:
            vector_memory: Экземпляр VectorMemory для векторного поиска
            enabled: Включить RAG систему
            knowledge_base_path: Путь к директории с документацией (опционально)
            max_results: Максимальное количество результатов поиска
            min_score: Минимальный score для включения результата
            log_stats_interval: Интервал для логирования статистики (количество запросов)
        """
        self.enabled = enabled
        self.knowledge_base_path = Path(knowledge_base_path) if knowledge_base_path else None
        self.max_results = max_results
        self.min_score = min_score
        self.rag_collection = None
        self.rag_collection_name = None
        self.log_stats_interval = log_stats_interval

        # Метрики использования
        self.total_queries = 0
        self.successful_queries = 0
        self.empty_results = 0
        self.total_chunks_found = 0
        self.scores: List[float] = []  # Все scores для вычисления статистики
        self.file_usage: Dict[str, int] = defaultdict(int)  # Счетчик использования по файлам

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
        skipped_count = 0
        total_chunks = 0

        try:
            # Поддерживаем текстовые файлы (.txt, .md)
            supported_extensions = {".txt", ".md"}
            files = [
                f
                for f in self.knowledge_base_path.rglob("*")
                if f.is_file() and f.suffix.lower() in supported_extensions
            ]

            if not files:
                logger.warning(f"No supported files (.txt, .md) found in {self.knowledge_base_path}")
                return 0

            for file_path in files:
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()

                    if not content.strip():
                        logger.debug(f"Skipping empty file: {file_path.name}")
                        continue

                    # Разбиваем на чанки для лучшего поиска
                    chunks = self._split_into_chunks(content, chunk_size=500)
                    total_chunks += len(chunks)
                    file_loaded = 0
                    file_skipped = 0

                    for i, chunk in enumerate(chunks):
                        doc_id = f"doc_{file_path.stem}_{i}"
                        metadata = {
                            "file_path": str(file_path.relative_to(self.knowledge_base_path)),
                            "chunk_index": i,
                            "total_chunks": len(chunks),
                        }

                        # Проверяем, не существует ли уже этот документ
                        try:
                            existing = self.rag_collection.get(ids=[doc_id])
                            if existing and len(existing["ids"]) > 0:
                                # Документ уже существует, пропускаем
                                file_skipped += 1
                                skipped_count += 1
                                continue
                        except Exception as e:
                            logger.debug(f"Error checking existing document {doc_id}: {e}")

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
                        file_loaded += 1

                    if file_loaded > 0:
                        logger.info(f"Loaded {file_loaded} new chunks from {file_path.name} (skipped {file_skipped} existing)")
                    elif file_skipped > 0:
                        logger.debug(f"All {file_skipped} chunks from {file_path.name} already exist, skipped")
                except Exception as e:
                    logger.error(f"Error loading file {file_path}: {e}", exc_info=True)
                    continue

            # Проверяем общее количество документов в коллекции
            try:
                collection_count = self.rag_collection.count()
            except Exception:
                collection_count = 0

            if loaded_count > 0:
                logger.info(
                    f"Knowledge base loaded: {loaded_count} new chunks from {len(files)} files "
                    f"(skipped {skipped_count} existing, total in collection: {collection_count})"
                )
            elif skipped_count > 0:
                logger.info(
                    f"Knowledge base already loaded: {skipped_count} chunks from {len(files)} files "
                    f"already exist in collection (total: {collection_count})"
                )
            elif total_chunks == 0:
                logger.warning(
                    f"Knowledge base is empty: found {len(files)} files but no chunks extracted "
                    "(files may be empty or contain only whitespace)"
                )
            else:
                logger.warning(
                    f"Knowledge base loading issue: {len(files)} files processed, "
                    f"but no chunks were loaded (total chunks expected: {total_chunks})"
                )

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

        # Обновляем метрики
        self.total_queries += 1

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
                            file_path = metadata.get("file_path", "unknown")
                            found_info.append(
                                {
                                    "content": content,
                                    "file_path": file_path,
                                    "score": score,
                                    "chunk_index": metadata.get("chunk_index", 0),
                                }
                            )
                            # Обновляем метрики
                            self.scores.append(score)
                            self.file_usage[file_path] += 1

            # Обновляем метрики использования
            if found_info:
                self.successful_queries += 1
                self.total_chunks_found += len(found_info)
            else:
                self.empty_results += 1
                # Логируем случаи, когда RAG не находит релевантной информации
                logger.debug(
                    f"RAG: No relevant info found for query '{query[:50]}...' "
                    f"(min_score={self.min_score:.2f})"
                )

            # Логируем каждый вызов
            scores_str = ", ".join([f"{info['score']:.2f}" for info in found_info])
            logger.debug(
                f"RAG query #{self.total_queries}: '{query[:50]}...' -> "
                f"{len(found_info)} chunks found (scores: [{scores_str}])"
            )

            # Периодическое логирование статистики
            if self.total_queries % self.log_stats_interval == 0:
                self._log_statistics()

            return found_info

        except Exception as e:
            logger.error(f"Error searching RAG knowledge base: {e}", exc_info=True)
            self.empty_results += 1
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

    def _log_statistics(self) -> None:
        """Логировать статистику использования RAG системы."""
        if self.total_queries == 0:
            return

        avg_score = sum(self.scores) / len(self.scores) if self.scores else 0.0
        min_score = min(self.scores) if self.scores else 0.0
        max_score = max(self.scores) if self.scores else 0.0
        success_rate = (self.successful_queries / self.total_queries * 100) if self.total_queries > 0 else 0.0

        logger.info(
            f"RAG Statistics (last {self.total_queries} queries): "
            f"successful={self.successful_queries} ({success_rate:.1f}%), "
            f"empty_results={self.empty_results}, "
            f"total_chunks={self.total_chunks_found}, "
            f"avg_score={avg_score:.3f}, "
            f"min_score={min_score:.3f}, "
            f"max_score={max_score:.3f}"
        )

        # Топ-5 наиболее используемых файлов
        if self.file_usage:
            top_files = sorted(self.file_usage.items(), key=lambda x: x[1], reverse=True)[:5]
            logger.debug(
                f"RAG Top files: {', '.join([f'{path} ({count})' for path, count in top_files])}"
            )

    def get_statistics(self) -> Dict[str, Any]:
        """
        Получить статистику использования RAG системы.

        Returns:
            Словарь со статистикой:
            {
                "total_queries": int,
                "successful_queries": int,
                "empty_results": int,
                "total_chunks_found": int,
                "success_rate": float,
                "avg_score": float,
                "min_score": float,
                "max_score": float,
                "top_files": List[Tuple[str, int]],
                "collection_count": int
            }
        """
        avg_score = sum(self.scores) / len(self.scores) if self.scores else 0.0
        min_score = min(self.scores) if self.scores else 0.0
        max_score = max(self.scores) if self.scores else 0.0
        success_rate = (self.successful_queries / self.total_queries * 100) if self.total_queries > 0 else 0.0

        # Топ-10 наиболее используемых файлов
        top_files = sorted(self.file_usage.items(), key=lambda x: x[1], reverse=True)[:10]

        # Количество документов в коллекции
        collection_count = 0
        if self.rag_collection:
            try:
                collection_count = self.rag_collection.count()
            except Exception:
                pass

        return {
            "total_queries": self.total_queries,
            "successful_queries": self.successful_queries,
            "empty_results": self.empty_results,
            "total_chunks_found": self.total_chunks_found,
            "success_rate": success_rate,
            "avg_score": avg_score,
            "min_score": min_score,
            "max_score": max_score,
            "top_files": top_files,
            "collection_count": collection_count,
        }

    def reset_statistics(self) -> None:
        """Сбросить статистику использования RAG системы."""
        self.total_queries = 0
        self.successful_queries = 0
        self.empty_results = 0
        self.total_chunks_found = 0
        self.scores.clear()
        self.file_usage.clear()
        logger.info("RAG statistics reset")

