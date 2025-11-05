"""Защита от флуда и DDoS через rate limiting."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from .memory import Base, RateLimit

logger = logging.getLogger(__name__)


class RateLimiter:
    """Rate limiter с простым счетчиком за период для защиты от флуда."""

    def __init__(
        self,
        session_factory,
        enabled: bool = True,
        messages_per_minute: int = 10,
        messages_per_hour: int = 50,
        min_interval_seconds: int = 2,
        block_duration_minutes: int = 10,
        max_repeated_messages: int = 3,
        min_message_length: int = 2,
        max_message_length: int = 5000,
    ):
        """
        Инициализация RateLimiter.

        Args:
            session_factory: Фабрика сессий SQLAlchemy для работы с БД
            enabled: Включить rate limiting
            messages_per_minute: Максимальное количество сообщений в минуту
            messages_per_hour: Максимальное количество сообщений в час
            min_interval_seconds: Минимальный интервал между сообщениями (секунды)
            block_duration_minutes: Длительность блокировки при превышении лимита (минуты)
            max_repeated_messages: Максимальное количество повторяющихся сообщений подряд
            min_message_length: Минимальная длина сообщения (символов)
            max_message_length: Максимальная длина сообщения (символов)
        """
        self.session_factory = session_factory
        self.enabled = enabled
        self.messages_per_minute = messages_per_minute
        self.messages_per_hour = messages_per_hour
        self.min_interval_seconds = min_interval_seconds
        self.block_duration_minutes = block_duration_minutes
        self.max_repeated_messages = max_repeated_messages
        self.min_message_length = min_message_length
        self.max_message_length = max_message_length

        # Создаем таблицу если её нет
        engine = session_factory().bind
        Base.metadata.create_all(engine)

        logger.info(
            f"RateLimiter initialized: enabled={enabled}, "
            f"messages_per_minute={messages_per_minute}, "
            f"messages_per_hour={messages_per_hour}"
        )

    def _get_session(self) -> Session:
        """Получить сессию БД."""
        return self.session_factory()

    def is_blocked(self, user_id: int) -> Tuple[bool, Optional[str]]:
        """
        Проверить, заблокирован ли пользователь.

        Args:
            user_id: ID пользователя

        Returns:
            Tuple[bool, Optional[str]]: (заблокирован, причина/время разблокировки)
        """
        if not self.enabled:
            return False, None

        session = self._get_session()
        try:
            rate_limit = (
                session.query(RateLimit).filter(RateLimit.user_id == user_id).first()
            )

            if not rate_limit:
                return False, None

            now = datetime.now(timezone.utc)

            # Проверяем временную блокировку
            # Нормализуем blocked_until к UTC если нужно
            blocked_until = rate_limit.blocked_until
            if blocked_until:
                if blocked_until.tzinfo is None:
                    blocked_until = blocked_until.replace(tzinfo=timezone.utc)
                if blocked_until > now:
                    remaining_minutes = int(
                        (blocked_until - now).total_seconds() / 60
                    ) + 1
                    return True, f"Слишком много сообщений. Подождите {remaining_minutes} минут."

            # Если блокировка истекла, снимаем её
            if blocked_until and blocked_until <= now:
                rate_limit.blocked_until = None
                rate_limit.message_count_minute = 0
                rate_limit.message_count_hour = 0
                rate_limit.repeated_messages = 0
                session.commit()

            return False, None
        finally:
            session.close()

    def check_rate_limit(
        self, user_id: int, message_content: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Проверить rate limit для сообщения.

        Args:
            user_id: ID пользователя
            message_content: Содержимое сообщения

        Returns:
            Tuple[bool, Optional[str]]: (превышен лимит, причина блокировки)
        """
        if not self.enabled:
            return True, None

        # Проверяем заблокирован ли пользователь
        blocked, reason = self.is_blocked(user_id)
        if blocked:
            return False, reason

        # Проверка длины сообщения
        message_len = len(message_content)
        if message_len < self.min_message_length:
            logger.debug(
                f"Message too short ({message_len} < {self.min_message_length}) for user {user_id}"
            )
            return False, f"Сообщение слишком короткое (минимум {self.min_message_length} символов)."

        if message_len > self.max_message_length:
            logger.debug(
                f"Message too long ({message_len} > {self.max_message_length}) for user {user_id}"
            )
            return False, f"Сообщение слишком длинное (максимум {self.max_message_length} символов)."

        session = self._get_session()
        try:
            now = datetime.now(timezone.utc)
            rate_limit = (
                session.query(RateLimit).filter(RateLimit.user_id == user_id).first()
            )

            if not rate_limit:
                # Создаем новую запись и сразу записываем первое сообщение
                rate_limit = RateLimit(
                    user_id=user_id,
                    message_count_minute=1,  # Первое сообщение
                    message_count_hour=1,  # Первое сообщение
                    window_start_minute=now,
                    window_start_hour=now,
                    last_message_time=now,
                    repeated_messages=0,
                    last_message_content=message_content,
                )
                session.add(rate_limit)
                session.commit()
                return True, None

            # Проверка минимального интервала
            last_time = rate_limit.last_message_time
            if last_time.tzinfo is None:
                last_time = last_time.replace(tzinfo=timezone.utc)
            time_since_last = (now - last_time).total_seconds()
            if time_since_last < self.min_interval_seconds:
                logger.debug(
                    f"Message too soon ({time_since_last:.1f}s < {self.min_interval_seconds}s) for user {user_id}"
                )
                return False, f"Подождите {self.min_interval_seconds} секунд перед следующим сообщением."

            # Проверка повторяющихся сообщений
            # Проверяем ПЕРЕД увеличением счетчика повторений
            is_repeated = (
                rate_limit.last_message_content
                and message_content == rate_limit.last_message_content
            )
            
            if is_repeated:
                # Если это будет уже max_repeated_messages-е повторяющееся сообщение, блокируем
                if rate_limit.repeated_messages + 1 >= self.max_repeated_messages:
                    logger.warning(
                        f"User {user_id} blocked for repeated messages ({rate_limit.repeated_messages + 1})"
                    )
                    self.block_user(user_id, "Повторяющиеся сообщения")
                    return False, "Слишком много повторяющихся сообщений. Подождите 10 минут."
                # Иначе увеличиваем счетчик (будет сохранен в record_message)
                rate_limit.repeated_messages += 1
            else:
                rate_limit.repeated_messages = 0
            
            # Сохраняем изменения в БД перед вызовом record_message
            session.commit()

            # Обновляем окна времени (простой счетчик с reset)
            minute_window_start = rate_limit.window_start_minute
            if minute_window_start.tzinfo is None:
                minute_window_start = minute_window_start.replace(tzinfo=timezone.utc)
            hour_window_start = rate_limit.window_start_hour
            if hour_window_start.tzinfo is None:
                hour_window_start = hour_window_start.replace(tzinfo=timezone.utc)

            # Сброс счетчика минутного окна
            if (now - minute_window_start).total_seconds() >= 60:
                rate_limit.message_count_minute = 0
                rate_limit.window_start_minute = now

            # Сброс счетчика часового окна
            if (now - hour_window_start).total_seconds() >= 3600:
                rate_limit.message_count_hour = 0
                rate_limit.window_start_hour = now

            # Проверка лимитов (проверяем ПЕРЕД увеличением счетчика)
            # Если текущий счетчик + 1 превысит лимит, блокируем
            if rate_limit.message_count_minute + 1 > self.messages_per_minute:
                logger.warning(
                    f"User {user_id} exceeded minute limit ({rate_limit.message_count_minute + 1}/{self.messages_per_minute})"
                )
                self.block_user(user_id, "Превышен лимит сообщений в минуту")
                return False, f"Слишком много сообщений в минуту (лимит: {self.messages_per_minute}). Подождите 10 минут."

            if rate_limit.message_count_hour + 1 > self.messages_per_hour:
                logger.warning(
                    f"User {user_id} exceeded hour limit ({rate_limit.message_count_hour + 1}/{self.messages_per_hour})"
                )
                self.block_user(user_id, "Превышен лимит сообщений в час")
                return False, f"Слишком много сообщений в час (лимит: {self.messages_per_hour}). Подождите 10 минут."

            # Все проверки пройдены - записываем сообщение
            self.record_message(user_id, message_content)

            return True, None

        finally:
            session.close()

    def record_message(self, user_id: int, message_content: str):
        """
        Записать сообщение (увеличить счетчики).

        Args:
            user_id: ID пользователя
            message_content: Содержимое сообщения
        """
        if not self.enabled:
            return

        session = self._get_session()
        try:
            rate_limit = (
                session.query(RateLimit).filter(RateLimit.user_id == user_id).first()
            )

            if not rate_limit:
                now = datetime.now(timezone.utc)
                rate_limit = RateLimit(
                    user_id=user_id,
                    message_count_minute=1,
                    message_count_hour=1,
                    window_start_minute=now,
                    window_start_hour=now,
                    last_message_time=now,
                    repeated_messages=0,
                    last_message_content=message_content,
                )
                session.add(rate_limit)
            else:
                now = datetime.now(timezone.utc)

                # Обновляем окна если нужно
                window_start_minute = rate_limit.window_start_minute
                if window_start_minute.tzinfo is None:
                    window_start_minute = window_start_minute.replace(tzinfo=timezone.utc)
                if (now - window_start_minute).total_seconds() >= 60:
                    rate_limit.message_count_minute = 0
                    rate_limit.window_start_minute = now

                window_start_hour = rate_limit.window_start_hour
                if window_start_hour.tzinfo is None:
                    window_start_hour = window_start_hour.replace(tzinfo=timezone.utc)
                if (now - window_start_hour).total_seconds() >= 3600:
                    rate_limit.message_count_hour = 0
                    rate_limit.window_start_hour = now

                # Обновляем счетчик повторяющихся сообщений ПЕРЕД обновлением last_message_content
                # Если сообщение повторяющееся, счетчик уже был увеличен в check_rate_limit
                # Если нет - сбрасываем
                if rate_limit.last_message_content == message_content:
                    # Это повторяющееся сообщение, счетчик уже увеличен в check_rate_limit
                    pass
                else:
                    # Новое сообщение, сбрасываем счетчик
                    rate_limit.repeated_messages = 0
                
                # Увеличиваем счетчики
                rate_limit.message_count_minute += 1
                rate_limit.message_count_hour += 1
                rate_limit.last_message_time = now
                rate_limit.last_message_content = message_content

            session.commit()
            logger.debug(
                f"Recorded message for user {user_id}: "
                f"minute={rate_limit.message_count_minute}, hour={rate_limit.message_count_hour}"
            )
        finally:
            session.close()

    def block_user(self, user_id: int, reason: str):
        """
        Заблокировать пользователя на указанное время.

        Args:
            user_id: ID пользователя
            reason: Причина блокировки (для логирования)
        """
        session = self._get_session()
        try:
            rate_limit = (
                session.query(RateLimit).filter(RateLimit.user_id == user_id).first()
            )

            if not rate_limit:
                now = datetime.now(timezone.utc)
                rate_limit = RateLimit(
                    user_id=user_id,
                    message_count_minute=0,
                    message_count_hour=0,
                    window_start_minute=now,
                    window_start_hour=now,
                    blocked_until=now + timedelta(minutes=self.block_duration_minutes),
                    last_message_time=now,
                    repeated_messages=0,
                    last_message_content=None,
                )
                session.add(rate_limit)
            else:
                rate_limit.blocked_until = datetime.now(timezone.utc) + timedelta(
                    minutes=self.block_duration_minutes
                )
                # Сбрасываем счетчики при блокировке
                rate_limit.message_count_minute = 0
                rate_limit.message_count_hour = 0
                rate_limit.repeated_messages = 0

            session.commit()
            logger.warning(
                f"User {user_id} blocked for {self.block_duration_minutes} minutes. Reason: {reason}"
            )
        finally:
            session.close()

