"""Telegram User Client через Telethon для личного аккаунта."""

import asyncio
import logging
from datetime import timedelta
from pathlib import Path
from typing import Optional

from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError

from .ai_client import AIClient
from .calendar import GoogleCalendar
from .config import Config
from .memory import Memory
from .rate_limiter import RateLimiter
from .sales_flow import SalesFlow, SalesStage
from .voice_handler import VoiceHandler

logger = logging.getLogger(__name__)


class TelegramUserClient:
    """Клиент Telegram для личного аккаунта."""

    def __init__(self, config: Config):
        """
        Инициализация Telegram клиента.

        Args:
            config: Конфигурация приложения
        """
        self.config = config
        self.client: Optional[TelegramClient] = None
        self.ai_client: Optional[AIClient] = None
        self.memory: Optional[Memory] = None
        self.calendar: Optional[GoogleCalendar] = None
        self.rate_limiter: Optional[RateLimiter] = None
        self.voice_handler: Optional[VoiceHandler] = None
        self.sales_flow: Optional[SalesFlow] = None

        # Инициализируем компоненты
        self._init_components()

    def _init_components(self):
        """Инициализация всех компонентов."""
        # Telegram клиент
        session_path = Path(self.config.telegram.session_path)
        session_path.parent.mkdir(parents=True, exist_ok=True)

        self.client = TelegramClient(
            str(session_path),
            self.config.telegram.api_id,
            self.config.telegram.api_hash,
        )

        # AI клиент
        self.ai_client = AIClient(
            base_url=self.config.ai_server.base_url,
            model=self.config.ai_server.model,
            api_key=self.config.ai_server.api_key,
            timeout=self.config.ai_server.timeout,
            max_retries=self.config.ai_server.max_retries,
            max_tokens=self.config.ai_server.max_tokens,
            system_prompt=self.config.ai_server.system_prompt,
            temperature=self.config.ai_server.temperature,
            timezone_name=self.config.ai_server.timezone,
            date_format=self.config.ai_server.date_format,
        )

        # Memory
        self.memory = Memory(
            db_path=self.config.memory.db_path,
            context_window=self.config.memory.context_window,
            max_history_days=self.config.memory.max_history_days,
        )

        # Rate Limiter
        self.rate_limiter = RateLimiter(
            session_factory=self.memory.SessionLocal,
            enabled=self.config.rate_limiting.enabled,
            messages_per_minute=self.config.rate_limiting.messages_per_minute,
            messages_per_hour=self.config.rate_limiting.messages_per_hour,
            min_interval_seconds=self.config.rate_limiting.min_interval_seconds,
            block_duration_minutes=self.config.rate_limiting.block_duration_minutes,
            max_repeated_messages=self.config.rate_limiting.spam_detection.max_repeated_messages,
            min_message_length=self.config.rate_limiting.spam_detection.min_message_length,
            max_message_length=self.config.rate_limiting.spam_detection.max_message_length,
        )

        # Voice Handler (если включен)
        if self.config.asr_server.enabled:
            self.voice_handler = VoiceHandler(
                base_url=self.config.asr_server.base_url,
                timeout=self.config.asr_server.timeout,
                enabled=self.config.asr_server.enabled,
            )
            logger.info("VoiceHandler initialized")

        # Sales Flow (если включен)
        if self.config.sales_flow.enabled:
            self.sales_flow = SalesFlow(enabled=self.config.sales_flow.enabled)
            logger.info("SalesFlow initialized")

        # Google Calendar (если включен)
        if self.config.google_calendar.enabled:
            try:
                # Проверяем что файл существует
                creds_path = Path(self.config.google_calendar.credentials_path)
                if creds_path.exists():
                    self.calendar = GoogleCalendar(
                        credentials_path=self.config.google_calendar.credentials_path,
                        token_path=self.config.google_calendar.token_path,
                        auto_create_consultations=self.config.google_calendar.auto_create_consultations,
                        default_consultation_duration_minutes=self.config.google_calendar.default_consultation_duration_minutes,
                        available_slots=self.config.google_calendar.available_slots,
                    )
                    logger.info("Google Calendar initialized")
                else:
                    logger.warning(
                        f"Google Calendar credentials file not found: {creds_path}. "
                        "Disabling Google Calendar integration."
                    )
                    self.calendar = None
            except Exception as e:
                logger.warning(
                    f"Failed to initialize Google Calendar: {e}. "
                    "Make sure you have OAuth 2.0 credentials (Desktop app), not service account."
                )
                self.calendar = None

        logger.info("All components initialized")

    async def start(self):
        """Запустить клиент и выполнить авторизацию."""
        session_path = Path(self.config.telegram.session_path)
        
        # Проверяем существует ли сессия
        if session_path.exists():
            logger.info(f"Found existing session: {session_path}")
            logger.info("Will try to use saved session (no login required)")
        else:
            logger.info("No existing session found. First-time login required.")
        
        # Используем callback для ввода кода (только если нужно)
        def code_callback():
            logger.info("Code required - please check Telegram")
            return input("Enter the code you received: ")

        def password_callback():
            logger.info("2FA password required")
            return input("Enter your 2FA password: ")

        await self.client.start(
            phone=self.config.telegram.phone,
            code_callback=code_callback,
            password=password_callback,
        )

        me = await self.client.get_me()
        logger.info(f"✅ Authorized as {me.first_name} (@{me.username})")
        logger.info(f"Session saved to: {session_path}")

        # Регистрируем обработчики
        self._register_handlers()

        logger.info("Telegram client started and ready")

    def _register_handlers(self):
        """Зарегистрировать обработчики событий."""

        @self.client.on(events.NewMessage)
        async def handle_new_message(event: events.NewMessage.Event):
            """Обработчик новых сообщений."""
            try:
                # Проверяем фильтры
                if not self._should_handle_message(event):
                    return

                # Получаем информацию о сообщении
                sender = await event.get_sender()
                chat = await event.get_chat()
                message_text = event.message.message or ""

                # Обработка голосовых сообщений
                if event.message.voice or event.message.audio:
                    if self.voice_handler and self.voice_handler.enabled:
                        try:
                            logger.info(f"🎤 Voice message received from {sender.id}")
                            # Скачиваем аудио файл
                            audio_path = await event.message.download_media(file="./temp_audio/")
                            audio_path = Path(audio_path)

                            # Транскрибируем
                            transcribed_text = await self.voice_handler.transcribe_voice(
                                audio_path, language="ru"
                            )
                            logger.info(f"✅ Transcribed: {transcribed_text[:100]}...")

                            # Используем транскрипт как текст сообщения
                            message_text = transcribed_text

                            # Удаляем временный файл
                            try:
                                audio_path.unlink()
                            except Exception as e:
                                logger.warning(f"Failed to delete temp audio file: {e}")

                        except Exception as e:
                            logger.error(f"Error transcribing voice message: {e}", exc_info=True)
                            await event.reply("Извините, не удалось распознать голосовое сообщение. Попробуйте отправить текстом.")
                            return
                    else:
                        await event.reply("Обработка голосовых сообщений отключена.")
                        return

                logger.info(
                    f"📨 New message from {sender.id} ({getattr(sender, 'username', 'N/A')}): "
                    f"{message_text[:100] if message_text else '(no text)'}..."
                )
                logger.debug(f"Full message content: {message_text}")
                logger.debug(f"Chat ID: {chat.id}, Chat type: {type(chat).__name__}")

                # Проверка rate limit (только для текстовых сообщений)
                if message_text:
                    allowed, reason = self.rate_limiter.check_rate_limit(
                        sender.id, message_text
                    )
                    if not allowed:
                        logger.warning(
                            f"Rate limit exceeded for user {sender.id}: {reason}"
                        )
                        await event.reply(reason)
                        return

                # Обработка команд Google Calendar
                if self.calendar and message_text.startswith("/"):
                    handled = await self._handle_calendar_command(event, message_text)
                    if handled:
                        return

                # Сохраняем сообщение пользователя (только если есть текст)
                username = getattr(sender, "username", None)
                if message_text:
                    # Записываем сообщение в rate limiter после успешной проверки
                    self.rate_limiter.record_message(sender.id, message_text)
                    
                    self.memory.save_message(
                        user_id=sender.id,
                        content=message_text,
                        role="user",
                        username=username,
                    )

                # Получаем контекст
                context = self.memory.get_context(sender.id)

                # Работа со скриптом продаж
                user_context_data = self.memory.get_user_context(sender.id)
                if self.sales_flow and self.sales_flow.enabled:
                    current_stage = self.sales_flow.get_stage(user_context_data)
                    
                    # Определяем переход на следующий этап
                    new_stage = self.sales_flow.detect_stage_transition(message_text, current_stage)
                    if new_stage:
                        logger.info(f"Sales flow: {current_stage.value} -> {new_stage.value}")
                        user_context_data = self.sales_flow.update_stage(user_context_data, new_stage)
                        self.memory.save_user_context(sender.id, user_context_data)
                        current_stage = new_stage
                    else:
                        # Обновляем контекст если его нет
                        if not user_context_data:
                            user_context_data = self.sales_flow.update_stage(None, current_stage)
                            self.memory.save_user_context(sender.id, user_context_data)

                    # Модифицируем системный промпт для текущего этапа
                    stage_modifier = self.sales_flow.get_stage_prompt_modifier(current_stage)
                    if stage_modifier and context:
                        # Добавляем модификатор как системное сообщение
                        modified_context = context.copy()
                        # Обновляем или добавляем системное сообщение
                        system_found = False
                        for msg in modified_context:
                            if msg.get("role") == "system":
                                msg["content"] = stage_modifier + "\n\n" + msg.get("content", "")
                                system_found = True
                                break
                        if not system_found:
                            modified_context.insert(0, {"role": "system", "content": stage_modifier})
                        context = modified_context

                # Генерируем ответ через AI
                try:
                    logger.info(f"🤖 Sending {len(context)} messages to AI server...")
                    response = await self.ai_client.get_response(context)
                    logger.info(f"✅ AI response received ({len(response)} chars): {response[:150]}...")
                    logger.debug(f"Full AI response: {response}")

                    # Отправляем ответ
                    await event.reply(response)
                    logger.info(f"✅ Reply sent to user {sender.id}")

                    # Сохраняем ответ ассистента
                    self.memory.save_message(
                        user_id=sender.id,
                        content=response,
                        role="assistant",
                        username=username,
                    )

                    # Автоматическое создание встреч при запросах на консультацию
                    if (
                        self.calendar
                        and self.calendar.auto_create_consultations
                        and self.calendar.detect_consultation_request(message_text)
                    ):
                        try:
                            # Извлекаем время из сообщения или ответа
                            extracted_time = self.calendar.extract_time_from_message(
                                message_text
                            )
                            if not extracted_time:
                                extracted_time = self.calendar.extract_time_from_message(
                                    response
                                )

                            if extracted_time:
                                # Создаем встречу на указанное время
                                end_time = extracted_time + timedelta(
                                    minutes=self.calendar.default_consultation_duration_minutes
                                )
                                event_id = self.calendar.create_event(
                                    summary="Консультация Scanovich.ai",
                                    description=f"Консультация с пользователем Telegram",
                                    start_time=extracted_time,
                                    end_time=end_time,
                                )
                                logger.info(
                                    f"✅ Consultation event created: {event_id} at {extracted_time}"
                                )
                                await event.reply(
                                    f"✅ Встреча создана на {extracted_time.strftime('%d.%m в %H:%M')}!"
                                )
                            else:
                                # Предлагаем доступные слоты
                                slots = self.calendar.suggest_available_slots()
                                slots_text = "\n".join(f"• {slot}" for slot in slots)
                                await event.reply(
                                    f"📅 Предлагаю следующие варианты времени:\n{slots_text}\n\n"
                                    "Напишите удобное время, и я создам встречу!"
                                )
                        except Exception as e:
                            logger.error(
                                f"Error creating consultation event: {e}", exc_info=True
                            )

                except Exception as e:
                    logger.error(f"Error getting AI response: {e}", exc_info=True)
                    error_msg = str(e)
                    # Более информативное сообщение об ошибке
                    if "404" in error_msg or "Not Found" in error_msg:
                        user_error = "Ошибка подключения к AI серверу. Проверьте настройки."
                    elif "timeout" in error_msg.lower():
                        user_error = "AI сервер не отвечает. Попробуйте позже."
                    else:
                        user_error = f"Ошибка при генерации ответа: {error_msg[:100]}"
                    
                    await event.reply(user_error)

            except Exception as e:
                logger.error(f"Error handling message: {e}", exc_info=True)

    def _should_handle_message(self, event: events.NewMessage.Event) -> bool:
        """
        Проверить, нужно ли обрабатывать сообщение.

        Args:
            event: Событие нового сообщения

        Returns:
            True если нужно обрабатывать, False иначе
        """
        # Не обрабатываем исходящие сообщения
        if event.message.out:
            return False

        # Проверяем тип чата
        if event.is_private:
            return self.config.telegram.handle_private_chats
        elif event.is_group:
            return self.config.telegram.handle_groups
        elif event.is_channel:
            return self.config.telegram.handle_channels

        return False

    async def _handle_calendar_command(
        self, event: events.NewMessage.Event, message_text: str
    ) -> bool:
        """
        Обработать команду Google Calendar.

        Args:
            event: Событие сообщения
            message_text: Текст сообщения

        Returns:
            True если команда обработана, False иначе
        """
        if not self.calendar:
            return False

        try:
            sender = await event.get_sender()

            # Команда /calendar или /events - список событий
            if message_text.startswith(("/calendar", "/events")):
                events_list = self.calendar.list_events(max_results=10)
                if events_list:
                    response = "📅 Предстоящие события:\n\n"
                    for evt in events_list:
                        response += self.calendar.format_event(evt) + "\n"
                else:
                    response = "📅 Нет предстоящих событий."
                await event.reply(response)
                return True

            # Команда /create_event - создать событие (простой формат)
            # Формат: /create_event Название события | Описание (опционально)
            if message_text.startswith("/create_event"):
                parts = message_text.split("|", 1)
                summary = parts[0].replace("/create_event", "").strip()
                description = parts[1].strip() if len(parts) > 1 else None

                if not summary:
                    await event.reply(
                        "Использование: /create_event Название события | Описание (опционально)"
                    )
                    return True

                event_id = self.calendar.create_event(
                    summary=summary, description=description
                )
                await event.reply(f"✅ Событие создано: {summary}")
                return True

        except Exception as e:
            logger.error(f"Error handling calendar command: {e}", exc_info=True)
            await event.reply("Ошибка при обработке команды календаря.")

        return False

    async def run(self):
        """Запустить клиент и работать до остановки."""
        await self.start()

        logger.info("Client is running. Press Ctrl+C to stop.")
        try:
            await self.client.run_until_disconnected()
        except KeyboardInterrupt:
            logger.info("Received interrupt signal, shutting down...")
        finally:
            await self.stop()

    async def stop(self):
        """Остановить клиент."""
        logger.info("Stopping client...")

        if self.ai_client:
            await self.ai_client.close()

        if self.voice_handler:
            await self.voice_handler.close()

        if self.client:
            await self.client.disconnect()

        logger.info("Client stopped")

