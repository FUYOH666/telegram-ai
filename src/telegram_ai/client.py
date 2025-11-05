"""Telegram User Client через Telethon для личного аккаунта."""

import asyncio
import logging
from pathlib import Path
from typing import Optional

from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError

from .ai_client import AIClient
from .calendar import GoogleCalendar
from .config import Config
from .memory import Memory

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
        )

        # Memory
        self.memory = Memory(
            db_path=self.config.memory.db_path,
            context_window=self.config.memory.context_window,
            max_history_days=self.config.memory.max_history_days,
        )

        # Google Calendar (если включен)
        if self.config.google_calendar.enabled:
            try:
                self.calendar = GoogleCalendar(
                    credentials_path=self.config.google_calendar.credentials_path,
                    token_path=self.config.google_calendar.token_path,
                )
                logger.info("Google Calendar initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Google Calendar: {e}")
                self.calendar = None

        logger.info("All components initialized")

    async def start(self):
        """Запустить клиент и выполнить авторизацию."""
        await self.client.start(phone=self.config.telegram.phone)

        if not await self.client.is_user_authorized():
            logger.info("Not authorized. Sending code request...")
            await self.client.send_code_request(self.config.telegram.phone)

            code = input("Enter the code you received: ")
            try:
                await self.client.sign_in(self.config.telegram.phone, code)
            except SessionPasswordNeededError:
                password = input("Enter your 2FA password: ")
                await self.client.sign_in(password=password)

        me = await self.client.get_me()
        logger.info(f"Authorized as {me.first_name} (@{me.username})")

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
                message_text = event.message.message

                logger.info(
                    f"New message from {sender.id} ({getattr(sender, 'username', 'N/A')}): "
                    f"{message_text[:100]}..."
                )

                # Обработка команд Google Calendar
                if self.calendar and message_text.startswith("/"):
                    handled = await self._handle_calendar_command(event, message_text)
                    if handled:
                        return

                # Сохраняем сообщение пользователя
                username = getattr(sender, "username", None)
                self.memory.save_message(
                    user_id=sender.id,
                    content=message_text,
                    role="user",
                    username=username,
                )

                # Получаем контекст
                context = self.memory.get_context(sender.id)

                # Генерируем ответ через AI
                try:
                    response = await self.ai_client.get_response(context)
                    logger.debug(f"AI response: {response[:100]}...")

                    # Отправляем ответ
                    await event.reply(response)

                    # Сохраняем ответ ассистента
                    self.memory.save_message(
                        user_id=sender.id,
                        content=response,
                        role="assistant",
                        username=username,
                    )

                except Exception as e:
                    logger.error(f"Error getting AI response: {e}", exc_info=True)
                    await event.reply(
                        "Извините, произошла ошибка при генерации ответа. Попробуйте позже."
                    )

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

        if self.client:
            await self.client.disconnect()

        logger.info("Client stopped")

