"""Защита от флуда и DDoS через rate limiting."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from .memory import Base, RateLimit, GlobalRateLimit, FloodWaitHistory

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
        self, user_id: int, message_content: str, messages_per_minute: Optional[int] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Проверить rate limit для сообщения.

        Args:
            user_id: ID пользователя
            message_content: Содержимое сообщения
            messages_per_minute: Переопределить лимит сообщений в минуту (для типов чатов)

        Returns:
            Tuple[bool, Optional[str]]: (превышен лимит, причина блокировки)
        """
        if not self.enabled:
            return True, None
        
        # Используем переданный лимит или базовый
        effective_limit = messages_per_minute if messages_per_minute is not None else self.messages_per_minute

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
            if rate_limit.message_count_minute + 1 > effective_limit:
                logger.warning(
                    f"User {user_id} exceeded minute limit ({rate_limit.message_count_minute + 1}/{effective_limit})"
                )
                self.block_user(user_id, "Превышен лимит сообщений в минуту")
                return False, f"Слишком много сообщений в минуту (лимит: {effective_limit}). Подождите 10 минут."

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


class GlobalRateLimiter:
    """Глобальный rate limiter на уровне аккаунта для защиты от блокировок Telegram."""

    def __init__(
        self,
        session_factory,
        enabled: bool = True,
        messages_per_minute: int = 25,
        messages_per_hour: int = 500,
        block_duration_minutes: int = 10,
        adaptive_enabled: bool = True,
        reduction_on_floodwait_percent: int = 20,
        recovery_period_minutes: int = 10,
        recovery_increment_percent: int = 5,
    ):
        """
        Инициализация GlobalRateLimiter.

        Args:
            session_factory: Фабрика сессий SQLAlchemy для работы с БД
            enabled: Включить глобальный rate limiting
            messages_per_minute: Максимальное количество сообщений в минуту на весь аккаунт
            messages_per_hour: Максимальное количество сообщений в час на весь аккаунт
            block_duration_minutes: Длительность блокировки при превышении лимита (минуты)
        """
        self.session_factory = session_factory
        self.enabled = enabled
        self.base_messages_per_minute = messages_per_minute
        self.base_messages_per_hour = messages_per_hour
        self.messages_per_minute = messages_per_minute  # Текущий адаптивный лимит
        self.messages_per_hour = messages_per_hour  # Текущий адаптивный лимит
        self.block_duration_minutes = block_duration_minutes
        
        # Адаптивные настройки
        self.adaptive_enabled = adaptive_enabled
        self.reduction_on_floodwait_percent = reduction_on_floodwait_percent
        self.recovery_period_minutes = recovery_period_minutes
        self.recovery_increment_percent = recovery_increment_percent
        self.last_recovery_check = datetime.now(timezone.utc)

        # Создаем таблицу если её нет
        engine = session_factory().bind
        Base.metadata.create_all(engine)

        logger.info(
            f"GlobalRateLimiter initialized: enabled={enabled}, "
            f"base_messages_per_minute={self.base_messages_per_minute}, "
            f"current_messages_per_minute={self.messages_per_minute}, "
            f"adaptive_enabled={adaptive_enabled}"
        )

    def _get_session(self) -> Session:
        """Получить сессию БД."""
        return self.session_factory()

    def is_blocked(self) -> Tuple[bool, Optional[str]]:
        """
        Проверить, заблокирован ли аккаунт глобально.

        Returns:
            Tuple[bool, Optional[str]]: (заблокирован, причина/время разблокировки)
        """
        if not self.enabled:
            return False, None

        session = self._get_session()
        try:
            global_limit = session.query(GlobalRateLimit).filter(GlobalRateLimit.id == 1).first()

            if not global_limit:
                return False, None

            now = datetime.now(timezone.utc)

            # Проверяем временную блокировку
            blocked_until = global_limit.blocked_until
            if blocked_until:
                if blocked_until.tzinfo is None:
                    blocked_until = blocked_until.replace(tzinfo=timezone.utc)
                if blocked_until > now:
                    remaining_minutes = int(
                        (blocked_until - now).total_seconds() / 60
                    ) + 1
                    return True, f"Глобальный лимит превышен. Подождите {remaining_minutes} минут."

            # Если блокировка истекла, снимаем её
            if blocked_until and blocked_until <= now:
                global_limit.blocked_until = None
                global_limit.message_count_minute = 0
                global_limit.message_count_hour = 0
                session.commit()

            return False, None
        finally:
            session.close()

    def check_global_limit(self) -> Tuple[bool, Optional[str]]:
        """
        Проверить глобальный лимит перед отправкой сообщения.

        Returns:
            Tuple[bool, Optional[str]]: (разрешено, причина блокировки)
        """
        if not self.enabled:
            return True, None

        # Проверяем и восстанавливаем адаптивные лимиты
        if self.adaptive_enabled:
            self._check_and_recover_limits()

        # Проверяем заблокирован ли аккаунт
        blocked, reason = self.is_blocked()
        if blocked:
            return False, reason

        session = self._get_session()
        try:
            now = datetime.now(timezone.utc)
            global_limit = session.query(GlobalRateLimit).filter(GlobalRateLimit.id == 1).first()

            if not global_limit:
                # Создаем новую запись
                global_limit = GlobalRateLimit(
                    id=1,
                    message_count_minute=1,
                    message_count_hour=1,
                    window_start_minute=now,
                    window_start_hour=now,
                    last_message_time=now,
                )
                session.add(global_limit)
                session.commit()
                return True, None

            # Обновляем окна времени
            minute_window_start = global_limit.window_start_minute
            if minute_window_start.tzinfo is None:
                minute_window_start = minute_window_start.replace(tzinfo=timezone.utc)
            hour_window_start = global_limit.window_start_hour
            if hour_window_start.tzinfo is None:
                hour_window_start = hour_window_start.replace(tzinfo=timezone.utc)

            # Сброс счетчика минутного окна
            if (now - minute_window_start).total_seconds() >= 60:
                global_limit.message_count_minute = 0
                global_limit.window_start_minute = now

            # Сброс счетчика часового окна
            if (now - hour_window_start).total_seconds() >= 3600:
                global_limit.message_count_hour = 0
                global_limit.window_start_hour = now

            # Проверка лимитов (проверяем ПЕРЕД увеличением счетчика)
            if global_limit.message_count_minute + 1 > self.messages_per_minute:
                logger.warning(
                    f"Global minute limit exceeded ({global_limit.message_count_minute + 1}/{self.messages_per_minute})"
                )
                self.block_account("Превышен глобальный лимит сообщений в минуту")
                return False, f"Глобальный лимит превышен: слишком много сообщений в минуту (лимит: {self.messages_per_minute}). Подождите {self.block_duration_minutes} минут."

            if global_limit.message_count_hour + 1 > self.messages_per_hour:
                logger.warning(
                    f"Global hour limit exceeded ({global_limit.message_count_hour + 1}/{self.messages_per_hour})"
                )
                self.block_account("Превышен глобальный лимит сообщений в час")
                return False, f"Глобальный лимит превышен: слишком много сообщений в час (лимит: {self.messages_per_hour}). Подождите {self.block_duration_minutes} минут."

            # Все проверки пройдены - записываем сообщение
            self.record_message()

            return True, None

        finally:
            session.close()

    def record_message(self):
        """Записать сообщение (увеличить глобальные счетчики)."""
        if not self.enabled:
            return

        session = self._get_session()
        try:
            global_limit = session.query(GlobalRateLimit).filter(GlobalRateLimit.id == 1).first()

            if not global_limit:
                now = datetime.now(timezone.utc)
                global_limit = GlobalRateLimit(
                    id=1,
                    message_count_minute=1,
                    message_count_hour=1,
                    window_start_minute=now,
                    window_start_hour=now,
                    last_message_time=now,
                )
                session.add(global_limit)
            else:
                now = datetime.now(timezone.utc)

                # Обновляем окна если нужно
                window_start_minute = global_limit.window_start_minute
                if window_start_minute.tzinfo is None:
                    window_start_minute = window_start_minute.replace(tzinfo=timezone.utc)
                if (now - window_start_minute).total_seconds() >= 60:
                    global_limit.message_count_minute = 0
                    global_limit.window_start_minute = now

                window_start_hour = global_limit.window_start_hour
                if window_start_hour.tzinfo is None:
                    window_start_hour = window_start_hour.replace(tzinfo=timezone.utc)
                if (now - window_start_hour).total_seconds() >= 3600:
                    global_limit.message_count_hour = 0
                    global_limit.window_start_hour = now

                # Увеличиваем счетчики
                global_limit.message_count_minute += 1
                global_limit.message_count_hour += 1
                global_limit.last_message_time = now

            session.commit()
            logger.debug(
                f"Recorded global message: "
                f"minute={global_limit.message_count_minute}, hour={global_limit.message_count_hour}"
            )
        finally:
            session.close()

    def block_account(self, reason: str):
        """
        Заблокировать аккаунт на указанное время.

        Args:
            reason: Причина блокировки (для логирования)
        """
        session = self._get_session()
        try:
            global_limit = session.query(GlobalRateLimit).filter(GlobalRateLimit.id == 1).first()

            if not global_limit:
                now = datetime.now(timezone.utc)
                global_limit = GlobalRateLimit(
                    id=1,
                    message_count_minute=0,
                    message_count_hour=0,
                    window_start_minute=now,
                    window_start_hour=now,
                    blocked_until=now + timedelta(minutes=self.block_duration_minutes),
                    last_message_time=now,
                )
                session.add(global_limit)
            else:
                global_limit.blocked_until = datetime.now(timezone.utc) + timedelta(
                    minutes=self.block_duration_minutes
                )
                # Сбрасываем счетчики при блокировке
                global_limit.message_count_minute = 0
                global_limit.message_count_hour = 0

            session.commit()
            logger.warning(
                f"Account blocked globally for {self.block_duration_minutes} minutes. Reason: {reason}"
            )
        finally:
            session.close()

    def record_flood_wait(self, wait_seconds: int, chat_type: Optional[str] = None):
        """
        Записать событие FloodWait в историю и адаптировать лимиты.

        Args:
            wait_seconds: Количество секунд ожидания от Telegram
            chat_type: Тип чата ('private', 'group', 'channel')
        """
        session = self._get_session()
        try:
            flood_wait = FloodWaitHistory(
                wait_seconds=wait_seconds,
                occurred_at=datetime.now(timezone.utc),
                chat_type=chat_type,
            )
            session.add(flood_wait)
            session.commit()
            
            if wait_seconds > 60:
                logger.critical(
                    f"CRITICAL FloodWait: {wait_seconds} seconds! Chat type: {chat_type}"
                )
            else:
                logger.warning(
                    f"FloodWait recorded: {wait_seconds} seconds. Chat type: {chat_type}"
                )
            
            # Адаптация лимитов при FloodWait
            if self.adaptive_enabled:
                self._reduce_limits_on_floodwait()
        finally:
            session.close()
    
    def _reduce_limits_on_floodwait(self):
        """Снизить лимиты при получении FloodWait."""
        reduction_factor = 1.0 - (self.reduction_on_floodwait_percent / 100.0)
        old_minute = self.messages_per_minute
        old_hour = self.messages_per_hour
        
        self.messages_per_minute = max(1, int(self.messages_per_minute * reduction_factor))
        self.messages_per_hour = max(10, int(self.messages_per_hour * reduction_factor))
        
        logger.info(
            f"Adaptive limits reduced: minute {old_minute} -> {self.messages_per_minute}, "
            f"hour {old_hour} -> {self.messages_per_hour}"
        )
    
    def _check_and_recover_limits(self):
        """Проверить и восстановить лимиты если прошло достаточно времени без FloodWait."""
        if not self.adaptive_enabled:
            return
        
        now = datetime.now(timezone.utc)
        time_since_last_check = (now - self.last_recovery_check).total_seconds() / 60
        
        if time_since_last_check >= self.recovery_period_minutes:
            # Проверяем, были ли FloodWait за последний период
            stats = self.get_flood_wait_stats(hours=self.recovery_period_minutes / 60)
            
            if stats["count"] == 0:
                # Нет FloodWait - восстанавливаем лимиты
                increment_factor = 1.0 + (self.recovery_increment_percent / 100.0)
                old_minute = self.messages_per_minute
                old_hour = self.messages_per_hour
                
                self.messages_per_minute = min(
                    self.base_messages_per_minute,
                    int(self.messages_per_minute * increment_factor)
                )
                self.messages_per_hour = min(
                    self.base_messages_per_hour,
                    int(self.messages_per_hour * increment_factor)
                )
                
                if old_minute != self.messages_per_minute or old_hour != self.messages_per_hour:
                    logger.info(
                        f"Adaptive limits recovered: minute {old_minute} -> {self.messages_per_minute}, "
                        f"hour {old_hour} -> {self.messages_per_hour}"
                    )
            
            self.last_recovery_check = now

    def get_flood_wait_stats(self, hours: int = 24) -> dict:
        """
        Получить статистику FloodWait за последние N часов.

        Args:
            hours: Количество часов для анализа

        Returns:
            dict: Статистика FloodWait
        """
        session = self._get_session()
        try:
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
            flood_waits = (
                session.query(FloodWaitHistory)
                .filter(FloodWaitHistory.occurred_at >= cutoff_time)
                .all()
            )

            if not flood_waits:
                return {
                    "count": 0,
                    "total_wait_seconds": 0,
                    "avg_wait_seconds": 0,
                    "max_wait_seconds": 0,
                }

            wait_times = [fw.wait_seconds for fw in flood_waits]
            return {
                "count": len(flood_waits),
                "total_wait_seconds": sum(wait_times),
                "avg_wait_seconds": sum(wait_times) / len(wait_times),
                "max_wait_seconds": max(wait_times),
            }
        finally:
            session.close()

