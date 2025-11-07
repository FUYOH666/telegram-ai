"""Redis клиент для кеширования и очередей."""

import json
import logging
from typing import Any, Optional

import redis.asyncio as redis
from redis.asyncio import Redis

from shared.config.settings import RedisConfig

logger = logging.getLogger(__name__)


class RedisClient:
    """Клиент для работы с Redis."""

    def __init__(self, config: RedisConfig):
        """
        Инициализация Redis клиента.

        Args:
            config: Конфигурация Redis
        """
        self.config = config
        self.client: Optional[Redis] = None
        logger.info(f"RedisClient initialized: url={config.url}, db={config.db}")

    async def connect(self):
        """Подключиться к Redis."""
        try:
            self.client = await redis.from_url(
                self.config.url,
                db=self.config.db,
                decode_responses=self.config.decode_responses,
            )
            # Проверяем подключение
            await self.client.ping()
            logger.info("Connected to Redis")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}", exc_info=True)
            raise

    async def disconnect(self):
        """Отключиться от Redis."""
        if self.client:
            await self.client.close()
            logger.info("Disconnected from Redis")

    async def get(self, key: str) -> Optional[str]:
        """
        Получить значение по ключу.

        Args:
            key: Ключ

        Returns:
            Значение или None
        """
        if not self.client:
            return None
        try:
            return await self.client.get(key)
        except Exception as e:
            logger.error(f"Error getting key {key}: {e}", exc_info=True)
            return None

    async def set(self, key: str, value: str, ttl: Optional[int] = None):
        """
        Установить значение по ключу.

        Args:
            key: Ключ
            value: Значение
            ttl: Время жизни в секундах (опционально)
        """
        if not self.client:
            return
        try:
            if ttl:
                await self.client.setex(key, ttl, value)
            else:
                await self.client.set(key, value)
        except Exception as e:
            logger.error(f"Error setting key {key}: {e}", exc_info=True)

    async def delete(self, key: str):
        """
        Удалить ключ.

        Args:
            key: Ключ
        """
        if not self.client:
            return
        try:
            await self.client.delete(key)
        except Exception as e:
            logger.error(f"Error deleting key {key}: {e}", exc_info=True)

    async def get_json(self, key: str) -> Optional[Any]:
        """
        Получить JSON значение по ключу.

        Args:
            key: Ключ

        Returns:
            Распарсенное JSON значение или None
        """
        value = await self.get(key)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return None
        return None

    async def set_json(self, key: str, value: Any, ttl: Optional[int] = None):
        """
        Установить JSON значение по ключу.

        Args:
            key: Ключ
            value: Значение для сериализации в JSON
            ttl: Время жизни в секундах (опционально)
        """
        json_value = json.dumps(value)
        await self.set(key, json_value, ttl)

    async def increment(self, key: str, amount: int = 1) -> int:
        """
        Увеличить значение по ключу.

        Args:
            key: Ключ
            amount: Количество для увеличения

        Returns:
            Новое значение
        """
        if not self.client:
            return 0
        try:
            return await self.client.incrby(key, amount)
        except Exception as e:
            logger.error(f"Error incrementing key {key}: {e}", exc_info=True)
            return 0

    async def expire(self, key: str, ttl: int):
        """
        Установить время жизни ключа.

        Args:
            key: Ключ
            ttl: Время жизни в секундах
        """
        if not self.client:
            return
        try:
            await self.client.expire(key, ttl)
        except Exception as e:
            logger.error(f"Error setting expire for key {key}: {e}", exc_info=True)

