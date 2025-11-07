"""Telegram User Client через Telethon для личного аккаунта."""

import asyncio
import json
import logging
import re
import time
from datetime import timedelta
from pathlib import Path
from typing import List, Optional

import httpx
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError

from .ai_client import AIClient
from .calendar import GoogleCalendar
from .config import Config
from .intent_classifier import IntentClassifier
from .language_detector import (
    SUPPORTED_LANGUAGES,
    detect_language,
    get_language_name,
    should_respond_in_language,
)
from .meeting_summary import MeetingSummary
from .memory import Memory
from .rag import RAGSystem
from .rate_limiter import GlobalRateLimiter, RateLimiter
from .consent import ConsentManager
from .events import Event, EventBus, EVENT_NEW_MESSAGE, EVENT_SLOT_FOUND, EVENT_TIME_PROPOSED, EVENT_CONSENT_GIVEN, EVENT_CONFLICT_FOUND, EVENT_INTENT_CHANGED
from .sales_flow import SalesFlow, SalesStage
from .slot_extractor import SlotExtractor
from .tools import Tools
from .vector_memory import VectorMemory
from .voice_handler import VoiceHandler
from .web_search import WebSearchTool

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
        self.global_rate_limiter: Optional[GlobalRateLimiter] = None
        self.voice_handler: Optional[VoiceHandler] = None
        self.sales_flow: Optional[SalesFlow] = None
        self.intent_classifier: Optional[IntentClassifier] = None
        self.tools: Optional[Tools] = None
        self.slot_extractor: Optional[SlotExtractor] = None
        self.vector_memory: Optional[VectorMemory] = None
        self.rag_system: Optional[RAGSystem] = None
        self.meeting_summary: Optional[MeetingSummary] = None
        self.consent_manager: Optional[ConsentManager] = None

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

        # Vector Memory (если включен)
        vector_memory = None
        if self.config.memory.vector_search_enabled:
            vector_memory = VectorMemory(
                persist_directory=self.config.memory.vector_db_path,
                collection_name="messages",
                ai_client=self.ai_client,
                enabled=self.config.memory.vector_search_enabled,
            )
            self.vector_memory = vector_memory
            logger.info("VectorMemory initialized")

        # RAG System (если включен)
        if self.config.rag.enabled:
            # Используем vector_memory если доступен, иначе создаем новый для RAG
            rag_vector_memory = vector_memory
            if not rag_vector_memory:
                # Создаем отдельный VectorMemory для RAG если основной не включен
                rag_vector_memory = VectorMemory(
                    persist_directory=self.config.memory.vector_db_path,
                    collection_name="rag_knowledge_base",
                    ai_client=self.ai_client,
                    enabled=True,
                )

            self.rag_system = RAGSystem(
                vector_memory=rag_vector_memory,
                enabled=self.config.rag.enabled,
                knowledge_base_path=self.config.rag.knowledge_base_path,
                max_results=self.config.rag.max_results,
                min_score=self.config.rag.min_score,
            )
            logger.info("RAGSystem initialized")
        else:
            self.rag_system = None

        # Memory
        self.memory = Memory(
            db_path=self.config.memory.db_path,
            context_window=self.config.memory.context_window,
            max_history_days=self.config.memory.max_history_days,
            auto_summarize=self.config.memory.auto_summarize,
            summary_threshold=self.config.memory.summary_threshold,
            ai_client=self.ai_client,  # Передаем ai_client для summarization
            vector_memory=vector_memory,  # Передаем vector_memory для векторного поиска
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

        # Global Rate Limiter
        self.global_rate_limiter = GlobalRateLimiter(
            session_factory=self.memory.SessionLocal,
            enabled=self.config.rate_limiting.global_limits.enabled,
            messages_per_minute=self.config.rate_limiting.global_limits.messages_per_minute,
            messages_per_hour=self.config.rate_limiting.global_limits.messages_per_hour,
            block_duration_minutes=self.config.rate_limiting.block_duration_minutes,  # Используется для глобальных блокировок
            adaptive_enabled=self.config.rate_limiting.adaptive.enabled,
            reduction_on_floodwait_percent=self.config.rate_limiting.adaptive.reduction_on_floodwait_percent,
            recovery_period_minutes=self.config.rate_limiting.adaptive.recovery_period_minutes,
            recovery_increment_percent=self.config.rate_limiting.adaptive.recovery_increment_percent,
        )

        # Voice Handler (если включен)
        if self.config.asr_server.enabled:
            self.voice_handler = VoiceHandler(
                base_url=self.config.asr_server.base_url,
                timeout=self.config.asr_server.timeout,
                enabled=self.config.asr_server.enabled,
            )
            logger.info("VoiceHandler initialized")

        # Slot Extractor (если включен)
        if self.config.slot_extraction.enabled:
            self.slot_extractor = SlotExtractor(
                ai_client=self.ai_client,
                enabled=self.config.slot_extraction.enabled,
            )
            logger.info("SlotExtractor initialized")
        else:
            self.slot_extractor = None

        # EventBus для событийной системы
        from .events import EventBus
        self.event_bus = EventBus()
        logger.info("EventBus initialized")

        # Sales Flow (если включен)
        if self.config.sales_flow.enabled:
            self.sales_flow = SalesFlow(
                enabled=self.config.sales_flow.enabled,
                slot_extractor=self.slot_extractor,
                event_bus=self.event_bus,
            )
            logger.info("SalesFlow initialized")

        # Meeting Summary (всегда инициализируем для генерации сводок)
        self.meeting_summary = MeetingSummary()
        logger.info("MeetingSummary initialized")

        # Consent Manager (для PDPA и других согласий)
        self.consent_manager = ConsentManager(memory=self.memory)
        logger.info("ConsentManager initialized")

        # Intent Classifier (всегда включен)
        self.intent_classifier = IntentClassifier(
            ai_client=self.ai_client,
            confidence_threshold=self.config.intent_classifier.confidence_threshold,
            use_llm=self.config.intent_classifier.use_llm,
        )
        logger.info("IntentClassifier initialized")

        # Web Search Tool (если включен)
        web_search_tool = None
        if self.config.web_search.enabled:
            web_search_tool = WebSearchTool(
                mcp_server_url=self.config.web_search.mcp_server_url,
                timeout=self.config.web_search.timeout,
                max_results=self.config.web_search.max_results,
                max_queries_per_conversation=self.config.web_search.max_queries_per_conversation,
            )
            logger.info("WebSearchTool initialized")

        # Tools (инструменты для работы с лидами)
        self.tools = Tools(memory=self.memory, web_search_tool=web_search_tool)
        logger.info("Tools initialized")

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
                        timezone_name=self.config.ai_server.timezone,  # Используем таймзону из конфига AI сервера
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

        # Загружаем базу знаний RAG если включено и настроено
        if self.rag_system and self.config.rag.auto_load_on_startup:
            try:
                logger.info("Loading RAG knowledge base...")
                loaded_count = await self.rag_system.load_knowledge_base()
                # Сообщение уже логируется в load_knowledge_base с детальной информацией
                if loaded_count == 0:
                    # Это не обязательно ошибка - документы могут быть уже загружены
                    logger.debug("No new chunks loaded (may already exist in collection)")
            except Exception as e:
                logger.warning(f"Failed to load RAG knowledge base: {e}", exc_info=True)

        # Регистрируем обработчики
        self._register_handlers()

        logger.info("Telegram client started and ready")

    def _register_handlers(self):
        """Зарегистрировать обработчики событий."""

        @self.client.on(events.NewMessage)
        async def handle_new_message(event: events.NewMessage.Event):
            """Обработчик новых сообщений."""
            # Логируем ВСЕ сообщения в самом начале, до любых проверок
            logger.info(
                f"🔔 EVENT RECEIVED: message_id={event.message.id}, "
                f"out={event.message.out}, "
                f"date={event.message.date}, "
                f"chat_id={event.chat_id}, "
                f"is_private={event.is_private}, "
                f"is_group={event.is_group}, "
                f"media={type(event.message.media).__name__ if event.message.media else 'None'}, "
                f"voice={bool(event.message.voice)}, "
                f"audio={bool(event.message.audio)}, "
                f"message_text={str(event.message.message)[:50] if event.message.message else 'None'}"
            )

            try:
                # Проверяем фильтры
                if not self._should_handle_message(event):
                    logger.info(
                        f"⏭️  Message filtered out: out={event.message.out}, "
                        f"is_private={event.is_private}, handle_private={self.config.telegram.handle_private_chats}, "
                        f"is_group={event.is_group}, handle_groups={self.config.telegram.handle_groups}"
                    )
                    return

                # Получаем информацию о сообщении
                sender = await event.get_sender()
                chat = await event.get_chat()
                message_text = event.message.message or ""

                # Проверяем, включен ли typing indicator и умное распределение
                smart_distribution = (
                    self.config.rate_limiting.smart_distribution
                    and self.config.rate_limiting.smart_distribution.enabled
                )
                typing_enabled = (
                    smart_distribution
                    and self.config.rate_limiting.smart_distribution.typing_indicator_enabled
                )

                # Определяем тип чата для умных лимитов
                chat_type = None
                chat_type_limit = None
                if event.is_private:
                    chat_type = "private"
                    chat_type_limit = self.config.rate_limiting.chat_type_limits.private
                elif event.is_group:
                    chat_type = "group"
                    chat_type_limit = self.config.rate_limiting.chat_type_limits.group
                elif event.is_channel:
                    chat_type = "channel"
                    chat_type_limit = self.config.rate_limiting.chat_type_limits.channel

                # Проверяем неподдерживаемые типы медиа (стикеры, фото, видео и т.д.) - игнорируем их
                is_sticker = event.message.sticker is not None
                is_photo = event.message.photo is not None
                is_video = event.message.video is not None
                is_gif = event.message.gif is not None
                is_video_note = event.message.video_note is not None
                is_contact = event.message.contact is not None
                is_location = event.message.geo is not None
                is_poll = event.message.poll is not None

                # Если это неподдерживаемый тип медиа - просто игнорируем без ответа (более естественно)
                if (
                    is_sticker
                    or is_photo
                    or is_video
                    or is_gif
                    or is_video_note
                    or is_contact
                    or is_location
                    or is_poll
                ):
                    logger.debug(
                        f"📎 Ignoring unsupported media type from {sender.id}: "
                        f"sticker={is_sticker}, photo={is_photo}, video={is_video}, "
                        f"gif={is_gif}, video_note={is_video_note}, contact={is_contact}, "
                        f"location={is_location}, poll={is_poll}"
                    )
                    return  # Игнорируем без ответа - более естественное поведение

                # Обработка голосовых сообщений
                # Проверяем голосовые сообщения через несколько способов для надежности
                is_voice_message = (
                    event.message.voice is not None
                    or event.message.audio is not None
                    or (event.message.media and hasattr(event.message.media, "voice"))
                    or (
                        event.message.media
                        and hasattr(event.message.media, "document")
                        and hasattr(event.message.media.document, "mime_type")
                        and "audio" in str(event.message.media.document.mime_type)
                    )
                )

                if is_voice_message:
                    logger.info(
                        f"🎤 Voice message detected from {sender.id}: "
                        f"voice={bool(event.message.voice)}, audio={bool(event.message.audio)}, "
                        f"media={type(event.message.media).__name__ if event.message.media else None}"
                    )
                    if self.voice_handler and self.voice_handler.enabled:
                        try:
                            transcription_start = time.time()
                            logger.info(f"🎤 Processing voice message from {sender.id}")
                            # Убеждаемся что директория существует
                            temp_audio_dir = Path("./temp_audio")
                            temp_audio_dir.mkdir(exist_ok=True)

                            # Получаем длительность аудио если доступна (для логирования)
                            audio_duration = None
                            if event.message.voice:
                                audio_duration = getattr(
                                    event.message.voice, "duration", None
                                )
                            elif event.message.audio:
                                audio_duration = getattr(
                                    event.message.audio, "duration", None
                                )

                            if audio_duration:
                                logger.info(
                                    f"🎤 Audio duration: {audio_duration} seconds"
                                )

                            # Скачиваем аудио файл
                            audio_path = await event.message.download_media(
                                file=str(temp_audio_dir)
                            )
                            audio_path = Path(audio_path)
                            logger.debug(f"Downloaded audio file to: {audio_path}")

                            # Конвертируем .oga в .ogg если нужно (Telegram использует .oga, но ASR сервер не принимает)
                            if audio_path.suffix.lower() == ".oga":
                                # .oga это технически .ogg с Opus кодеком, переименовываем
                                ogg_path = audio_path.with_suffix(".ogg")
                                audio_path.rename(ogg_path)
                                audio_path = ogg_path
                                logger.debug(f"Renamed .oga to .ogg: {audio_path}")

                            # Определяем язык для транскрибации из контекста пользователя
                            user_context_data = self.memory.get_user_context(sender.id)
                            asr_language = "ru"  # По умолчанию
                            if user_context_data:
                                try:
                                    context_dict = json.loads(user_context_data)
                                    extracted_lang = context_dict.get("lang", "ru")
                                    # Валидация: проверяем что это валидный код языка, а не intent или другое значение
                                    if extracted_lang in SUPPORTED_LANGUAGES:
                                        asr_language = extracted_lang
                                    else:
                                        logger.warning(
                                            f"Invalid language code in user context: '{extracted_lang}' "
                                            f"(expected one of {list(SUPPORTED_LANGUAGES.keys())}), using default 'ru'"
                                        )
                                        asr_language = "ru"
                                except (json.JSONDecodeError, ValueError) as e:
                                    logger.warning(
                                        f"Failed to parse user context for language: {e}, using default 'ru'"
                                    )

                            logger.debug(f"Using language code for ASR: {asr_language}")

                            # Транскрибируем с учетом языка пользователя
                            transcribed_text = (
                                await self.voice_handler.transcribe_voice(
                                    audio_path, language=asr_language, duration=audio_duration
                                )
                            )
                            transcription_time = time.time() - transcription_start
                            logger.info(
                                f"✅ Transcribed in {transcription_time:.2f}s: {transcribed_text[:100]}..."
                            )

                            # Используем транскрипт как текст сообщения
                            message_text = transcribed_text
                            logger.info(
                                f"✅ Voice transcription completed, message_text set: "
                                f"{len(message_text)} chars, continuing with AI processing..."
                            )

                            # Удаляем временный файл
                            try:
                                audio_path.unlink()
                            except Exception as e:
                                logger.warning(f"Failed to delete temp audio file: {e}")

                        except httpx.HTTPStatusError as e:
                            # Обработка HTTP ошибок от ASR сервера
                            error_detail = ""
                            try:
                                if e.response is not None:
                                    error_json = e.response.json()
                                    error_detail = error_json.get(
                                        "detail", e.response.text
                                    )
                            except Exception:
                                error_detail = (
                                    str(e.response.text) if e.response else str(e)
                                )

                            logger.error(
                                f"HTTP error from ASR server: {e.response.status_code if e.response else 'unknown'} - {error_detail}",
                                exc_info=True,
                            )

                            # Более информативное сообщение об ошибке
                            if e.response and e.response.status_code == 500:
                                await event.reply(
                                    "❌ Ошибка на стороне ASR сервера при распознавании голосового сообщения. "
                                    "Попробуйте позже или отправьте текстом."
                                )
                            elif e.response and e.response.status_code == 400:
                                await event.reply(
                                    "❌ Неверный формат голосового сообщения. Попробуйте отправить текстом."
                                )
                            else:
                                await event.reply(
                                    "❌ Ошибка при распознавании голосового сообщения. Попробуйте позже или отправьте текстом."
                                )
                            return
                        except httpx.TimeoutException as e:
                            logger.error(
                                f"Timeout transcribing voice message: {e}",
                                exc_info=True,
                            )
                            await event.reply(
                                "⏱️ Таймаут при распознавании голосового сообщения. Попробуйте позже или отправьте текстом."
                            )
                            return
                        except httpx.ReadTimeout as e:
                            logger.error(
                                f"Read timeout transcribing voice message: {e}",
                                exc_info=True,
                            )
                            await event.reply(
                                "⏱️ Сервер ASR не отвечает вовремя. Попробуйте позже или отправьте текстом."
                            )
                            return
                        except httpx.NetworkError as e:
                            logger.error(
                                f"Network error transcribing voice message: {e}",
                                exc_info=True,
                            )
                            await event.reply(
                                "🌐 Ошибка сети при подключении к ASR серверу. Проверьте интернет-соединение и попробуйте позже."
                            )
                            return
                        except Exception as e:
                            logger.error(
                                f"Unexpected error transcribing voice message: {e}",
                                exc_info=True,
                            )
                            await self.safe_reply(
                                event,
                                "Извините, не удалось распознать голосовое сообщение. Попробуйте отправить текстом.",
                            )
                            return
                    else:
                        await self.safe_reply(
                            event, "Обработка голосовых сообщений отключена."
                        )
                        return

                logger.info(
                    f"📨 New message from {sender.id} ({getattr(sender, 'username', 'N/A')}): "
                    f"{message_text[:100] if message_text else '(no text)'}..."
                )
                logger.debug(f"Full message content: {message_text}")
                logger.debug(f"Chat ID: {chat.id}, Chat type: {type(chat).__name__}")

                # Проверка глобального лимита перед обработкой
                if self.global_rate_limiter:
                    global_allowed, global_reason = (
                        self.global_rate_limiter.check_global_limit()
                    )
                    if not global_allowed:
                        logger.warning(f"Global rate limit exceeded: {global_reason}")
                        await self.safe_reply(event, global_reason)
                        return

                # Проверка rate limit с учетом типа чата (только для текстовых сообщений)
                if message_text:
                    # Используем лимит типа чата если он установлен, иначе базовый per-user лимит
                    messages_per_minute = (
                        chat_type_limit
                        if chat_type_limit
                        else self.config.rate_limiting.messages_per_minute
                    )
                    allowed, reason = self.rate_limiter.check_rate_limit(
                        sender.id, message_text, messages_per_minute=messages_per_minute
                    )
                    if not allowed:
                        # Если reason = None, значит сообщение слишком короткое (1 символ) - игнорируем без ответа
                        if reason is None:
                            logger.debug(
                                f"Ignoring very short message (1 char) from user {sender.id} without reply"
                            )
                            return
                        logger.warning(
                            f"Rate limit exceeded for user {sender.id} (chat_type={chat_type}): {reason}"
                        )
                        await self.safe_reply(event, reason)
                        return

                # Обработка команд Google Calendar (перед основной обработкой, без typing)
                if self.calendar and message_text.startswith("/"):
                    handled = await self._handle_calendar_command(event, message_text)
                    if handled:
                        return

                # Получаем username для дальнейшей обработки
                username = getattr(sender, "username", None)

                # Оборачиваем всю обработку в typing indicator (если включен)
                # Typing показывается автоматически во время всей обработки
                if typing_enabled:
                    # Используем async with для автоматического управления typing indicator
                    async with event.client.action(event.chat_id, "typing"):
                        await self._process_message_internal(
                            event,
                            sender,
                            chat,
                            message_text,
                            username,
                            chat_type,
                            chat_type_limit,
                            smart_distribution,
                        )
                else:
                    # Обработка без typing indicator (для обратной совместимости)
                    await self._process_message_internal(
                        event,
                        sender,
                        chat,
                        message_text,
                        username,
                        chat_type,
                        chat_type_limit,
                        smart_distribution,
                    )

            except Exception as e:
                logger.error(f"Error handling message: {e}", exc_info=True)

    async def _process_message_internal(
        self,
        event: events.NewMessage.Event,
        sender,
        chat,
        message_text: str,
        username: Optional[str],
        chat_type: Optional[str],
        chat_type_limit: Optional[int],
        smart_distribution: bool,
    ):
        """Внутренняя обработка сообщения (может быть обернута в typing indicator)."""
        try:
            # Извлекаем имя пользователя (first_name или full_name)
            user_first_name = getattr(sender, "first_name", None)
            user_last_name = getattr(sender, "last_name", None)
            user_full_name = None
            if user_first_name:
                user_full_name = (
                    f"{user_first_name} {user_last_name}".strip()
                    if user_last_name
                    else user_first_name
                )

                # Сохраняем имя пользователя в контексте если еще не сохранено
                if user_full_name:
                    user_context_data = self.memory.get_user_context(sender.id)
                    if user_context_data:
                        try:
                            context_dict = json.loads(user_context_data)
                            if "name" not in context_dict:
                                context_dict["name"] = user_full_name
                                self.memory.save_user_context(
                                    sender.id, json.dumps(context_dict)
                                )
                        except (json.JSONDecodeError, ValueError):
                            pass
                    else:
                        # Создаем новый контекст с именем
                        new_context = json.dumps({"name": user_full_name})
                        self.memory.save_user_context(sender.id, new_context)

                if message_text:
                    # Публикуем событие NEW_MESSAGE
                    if self.event_bus:
                        self.event_bus.publish(
                            Event(
                                name=EVENT_NEW_MESSAGE,
                                payload={
                                    "user_id": sender.id,
                                    "message": message_text,
                                    "username": username,
                                },
                                timestamp=time.time(),
                            )
                        )

                    # Записываем сообщение в rate limiter после успешной проверки
                    self.rate_limiter.record_message(sender.id, message_text)

                    saved_message = self.memory.save_message(
                        user_id=sender.id,
                        content=message_text,
                        role="user",
                        username=username,
                    )

                    # Добавляем сообщение в векторное хранилище (асинхронно, не блокируем)
                    if (
                        self.vector_memory
                        and self.vector_memory.enabled
                        and saved_message
                    ):
                        try:
                            await self.vector_memory.add_message(
                                message_id=saved_message.id,
                                user_id=sender.id,
                                conversation_id=saved_message.conversation_id,
                                content=message_text,
                                role="user",
                                timestamp=saved_message.timestamp.isoformat()
                                if saved_message.timestamp
                                else None,
                            )
                        except Exception as e:
                            logger.debug(
                                f"Could not add message to vector store (non-blocking): {e}"
                            )

                # Определяем язык сообщения
                detected_message_lang = (
                    detect_language(message_text) if message_text else None
                )

                # Получаем текущий язык из контекста
                user_context_data = self.memory.get_user_context(sender.id)
                current_lang = None
                if user_context_data:
                    try:
                        context_dict = json.loads(user_context_data)
                        current_lang = context_dict.get("lang")
                    except (json.JSONDecodeError, ValueError):
                        pass

                # Определяем язык для ответа (это уже нормализованный язык - только ru, en, zh, th)
                response_lang = should_respond_in_language(
                    detected_message_lang, current_lang
                )

                # Сохраняем язык в контексте только если он изменился или еще не установлен
                # Важно: сохраняем response_lang (нормализованный), а не detected_message_lang (может быть неподдерживаемым)
                if response_lang != current_lang:
                    logger.info(
                        f"Language detected: {response_lang} (was {current_lang}, detected: {detected_message_lang})"
                    )
                    if user_context_data:
                        try:
                            context_dict = json.loads(user_context_data)
                        except (json.JSONDecodeError, ValueError):
                            context_dict = {}
                    else:
                        context_dict = {}
                    context_dict["lang"] = (
                        response_lang  # Сохраняем нормализованный язык
                    )
                    user_context_data = json.dumps(context_dict)
                    self.memory.save_user_context(sender.id, user_context_data)

                # Автоматическое создание summary для старых сообщений (если нужно)
                if self.memory.auto_summarize and self.memory.ai_client:
                    try:
                        cutoff_id = self.memory.should_create_summary(sender.id)
                        if cutoff_id is not None:
                            logger.info(
                                f"Creating summary for user_id={sender.id}, cutoff_message_id={cutoff_id}"
                            )
                            await self.memory.summarize_old_messages(
                                sender.id, cutoff_id
                            )
                    except Exception as e:
                        logger.error(f"Error creating summary: {e}", exc_info=True)
                        # Продолжаем работу даже если summary не создался

                # Получаем контекст
                context = self.memory.get_context(sender.id)

                # Если включен векторный поиск - добавляем релевантные сообщения из истории
                if (
                    self.vector_memory
                    and self.vector_memory.enabled
                    and message_text
                    and len(message_text.split())
                    > 3  # Только для достаточно длинных запросов
                ):
                    try:
                        relevant_messages = await self.memory.get_relevant_context(
                            user_id=sender.id,
                            query=message_text,
                            limit=3,  # Добавляем 3 наиболее релевантных сообщения
                        )
                        # Добавляем релевантные сообщения в начало контекста (после summary если есть)
                        # Проверяем, есть ли уже summary (он всегда первый)
                        if relevant_messages:
                            if (
                                context
                                and context[0].get("role") == "system"
                                and "Резюме" in context[0].get("content", "")
                            ):
                                # Summary есть, добавляем после него
                                context = [context[0]] + relevant_messages + context[1:]
                            else:
                                # Summary нет, добавляем в начало
                                context = relevant_messages + context
                            logger.debug(
                                f"Added {len(relevant_messages)} relevant messages from vector search"
                            )
                    except Exception as e:
                        logger.debug(f"Vector search failed (non-blocking): {e}")

                # Определяем, является ли это первым сообщением в разговоре
                is_first_message = (
                    len(context) <= 1
                )  # Только системное сообщение или его нет

                # ВАЖНО: Определяем язык для ответа на основе ПОСЛЕДНЕГО сообщения пользователя
                # Используем detected_message_lang как приоритетный (язык текущего сообщения)
                # Если текущее сообщение не определено, используем response_lang из контекста
                language_for_response = (
                    detected_message_lang if detected_message_lang else response_lang
                )
                if (
                    language_for_response
                    and language_for_response in SUPPORTED_LANGUAGES
                ):
                    response_lang = language_for_response
                # Если язык не определен, оставляем response_lang как есть (может быть None или "ru")

                # Классификация намерений
                current_intent = None
                if user_context_data:
                    try:
                        context_dict = json.loads(user_context_data)
                        current_intent = context_dict.get("intent")
                    except (json.JSONDecodeError, ValueError):
                        pass

                if self.intent_classifier:
                    # Используем LLM-based классификацию с confidence scores
                    (
                        detected_intent,
                        confidence,
                    ) = await self.intent_classifier.classify_with_confidence(
                        message_text, current_intent
                    )
                    if detected_intent.value != current_intent or not current_intent:
                        if detected_intent.value != current_intent:
                            logger.info(
                                f"Intent detected: {current_intent} -> {detected_intent.value} "
                                f"(confidence={confidence:.2f})"
                            )
                            
                            # Публикуем событие INTENT_CHANGED
                            if self.event_bus:
                                self.event_bus.publish(
                                    Event(
                                        name=EVENT_INTENT_CHANGED,
                                        payload={
                                            "old_intent": current_intent,
                                            "new_intent": detected_intent.value,
                                            "confidence": confidence,
                                            "user_id": sender.id,
                                        },
                                        timestamp=time.time(),
                                    )
                                )

                        # Обновляем intent в контексте
                        if self.sales_flow and self.sales_flow.enabled:
                            if user_context_data:
                                user_context_data = self.sales_flow.update_intent(
                                    user_context_data, detected_intent.value
                                )
                            else:
                                user_context_data = self.sales_flow.update_intent(
                                    None, detected_intent.value
                                )
                        else:
                            # Если sales_flow отключен, обновляем напрямую
                            if user_context_data:
                                try:
                                    context_dict = json.loads(user_context_data)
                                except (json.JSONDecodeError, ValueError):
                                    context_dict = {}
                            else:
                                context_dict = {}
                            context_dict["intent"] = detected_intent.value
                            user_context_data = json.dumps(context_dict)

                        self.memory.save_user_context(sender.id, user_context_data)
                        current_intent = detected_intent.value

                # Проверяем и устанавливаем флаг представления (introduced)
                # Бот должен представляться только один раз в начале диалога
                # Это работает независимо от sales_flow
                is_introduced = False
                if user_context_data:
                    try:
                        context_dict = json.loads(user_context_data)
                        is_introduced = context_dict.get("introduced", False)
                    except (json.JSONDecodeError, ValueError):
                        pass

                # Работа со скриптом продаж
                current_stage = None

                if self.sales_flow and self.sales_flow.enabled:
                    current_stage = self.sales_flow.get_stage(user_context_data)
                    # Флаг introduced будет установлен ПОСЛЕ генерации ответа, чтобы промпт видел первое знакомство
                else:
                    # Если sales_flow отключен, устанавливаем флаг при первом сообщении
                    if not is_introduced and is_first_message:
                        if user_context_data:
                            try:
                                context_dict = json.loads(user_context_data)
                                context_dict["introduced"] = True
                                user_context_data = json.dumps(context_dict)
                                self.memory.save_user_context(
                                    sender.id, user_context_data
                                )
                            except (json.JSONDecodeError, ValueError):
                                # Создаем новый контекст с флагом
                                context_dict = {"introduced": True}
                                user_context_data = json.dumps(context_dict)
                                self.memory.save_user_context(
                                    sender.id, user_context_data
                                )
                        else:
                            # Создаем новый контекст с флагом
                            user_context_data = json.dumps({"introduced": True})
                            self.memory.save_user_context(sender.id, user_context_data)
                        is_introduced = True

                    # Специальная логика: если пользователь пишет приветствие - сбрасываем на GREETING
                    # НО только если это явное приветствие в начале сообщения или короткое сообщение
                    # Это предотвращает ложные срабатывания на слова типа "расскажи" (содержит "привет")
                    message_lower = message_text.lower().strip()
                    greeting_keywords = [
                        "привет",
                        "здравствуй",
                        "здравствуйте",
                        "добрый день",
                        "добрый вечер",
                        "доброе утро",
                        "начать",
                        # Английские приветствия
                        "hi",
                        "hello",
                        "hey",
                        "good morning",
                        "good afternoon",
                        "good evening",
                    ]
                    # Проверяем только если сообщение короткое (до 50 символов) или начинается с приветствия
                    is_short_message = len(message_text) <= 50
                    starts_with_greeting = any(
                        message_lower.startswith(keyword)
                        or message_lower.startswith(keyword + " ")
                        for keyword in greeting_keywords
                    )
                    # Также проверяем если сообщение состоит только из приветствия
                    is_only_greeting = any(
                        keyword == message_lower or message_lower == keyword + "!"
                        for keyword in greeting_keywords
                    )

                    if (
                        (
                            is_short_message
                            and any(
                                keyword in message_lower
                                for keyword in greeting_keywords
                            )
                        )
                        or starts_with_greeting
                        or is_only_greeting
                    ):
                        if current_stage != SalesStage.GREETING:
                            logger.info(
                                f"Greeting detected, resetting stage to GREETING (was {current_stage.value})"
                            )
                            current_stage = SalesStage.GREETING
                            user_context_data = self.sales_flow.update_stage(
                                user_context_data, current_stage
                            )
                            self.memory.save_user_context(sender.id, user_context_data)

                        # При приветствии сбрасываем intent на SMALL_TALK (если не было явных признаков другого intent)
                        if self.intent_classifier:
                            detected_intent = self.intent_classifier.classify(
                                message_text, None
                            )  # Без сохранения старого intent
                            if detected_intent.value != current_intent:
                                logger.info(
                                    f"Resetting intent to {detected_intent.value} on greeting (was {current_intent})"
                                )
                                if self.sales_flow and self.sales_flow.enabled:
                                    user_context_data = self.sales_flow.update_intent(
                                        user_context_data, detected_intent.value
                                    )
                                else:
                                    if user_context_data:
                                        try:
                                            context_dict = json.loads(user_context_data)
                                        except (json.JSONDecodeError, ValueError):
                                            context_dict = {}
                                    else:
                                        context_dict = {}
                                    context_dict["intent"] = detected_intent.value
                                    user_context_data = json.dumps(context_dict)
                                self.memory.save_user_context(
                                    sender.id, user_context_data
                                )
                                current_intent = detected_intent.value

                    # Определяем переход на следующий этап
                    new_stage = self.sales_flow.detect_stage_transition(
                        message_text, current_stage, is_first_message=is_first_message
                    )
                    if new_stage:
                        logger.info(
                            f"Sales flow: {current_stage.value} -> {new_stage.value}"
                        )
                        user_context_data = self.sales_flow.update_stage(
                            user_context_data, new_stage
                        )
                        self.memory.save_user_context(sender.id, user_context_data)
                        current_stage = new_stage
                        # Сбрасываем счетчик сообщений при переходе на другой этап
                        if user_context_data:
                            try:
                                context_dict = json.loads(user_context_data)
                                if current_stage != SalesStage.PRESENTATION:
                                    context_dict.pop(
                                        "presentation_messages_count", None
                                    )
                                user_context_data = json.dumps(context_dict)
                                self.memory.save_user_context(
                                    sender.id, user_context_data
                                )
                            except (json.JSONDecodeError, ValueError):
                                pass
                    else:
                        # Обновляем контекст если его нет
                        if not user_context_data:
                            user_context_data = self.sales_flow.update_stage(
                                None, current_stage
                            )
                            self.memory.save_user_context(sender.id, user_context_data)

                    # Счетчик сообщений на этапе PRESENTATION
                    presentation_messages_count = 0
                    if current_stage == SalesStage.PRESENTATION and new_stage is None:
                        # Получаем текущий счетчик
                        if user_context_data:
                            try:
                                context_dict = json.loads(user_context_data)
                                presentation_messages_count = context_dict.get(
                                    "presentation_messages_count", 0
                                )
                            except (json.JSONDecodeError, ValueError):
                                presentation_messages_count = 0

                        # Увеличиваем счетчик для текущего сообщения
                        presentation_messages_count += 1

                        # Сохраняем обновленный счетчик
                        if user_context_data:
                            try:
                                context_dict = json.loads(user_context_data)
                                context_dict["presentation_messages_count"] = (
                                    presentation_messages_count
                                )
                                user_context_data = json.dumps(context_dict)
                                self.memory.save_user_context(
                                    sender.id, user_context_data
                                )
                            except (json.JSONDecodeError, ValueError):
                                # Создаем новый контекст с счетчиком
                                try:
                                    context_dict = json.loads(user_context_data)
                                except (json.JSONDecodeError, ValueError):
                                    context_dict = {}
                                context_dict["presentation_messages_count"] = (
                                    presentation_messages_count
                                )
                                user_context_data = json.dumps(context_dict)
                                self.memory.save_user_context(
                                    sender.id, user_context_data
                                )

                    # Автоматическое извлечение слотов из сообщения (только для Sales/Real Estate)
                    if (
                        current_intent in ("SALES_AI", "REAL_ESTATE")
                        and self.sales_flow
                        and self.slot_extractor
                        and self.slot_extractor.enabled
                    ):
                        try:
                            # Получаем недостающие слоты перед извлечением
                            missing_slots = self.sales_flow.get_missing_slots(
                                user_context_data, current_intent
                            )
                            
                            if missing_slots:
                                # Извлекаем слоты с confidence
                                extracted_slots_list = await self.slot_extractor.extract_slots(
                                    message_text, current_intent, missing_slots
                                )
                                
                                # Обновляем контекст с извлеченными слотами
                                if extracted_slots_list:
                                    for slot_info in extracted_slots_list:
                                        field = slot_info.get("field")
                                        value = slot_info.get("value")
                                        confidence = slot_info.get("confidence", 0.7)
                                        source = slot_info.get("source", "llm")
                                        
                                        # Сохраняем слот с confidence через memory
                                        self.memory.update_slot_with_confidence(
                                            sender.id, field, value, confidence, source
                                        )
                                        
                                        # Публикуем событие SLOT_FOUND
                                        if self.event_bus:
                                            self.event_bus.publish(
                                                Event(
                                                    name=EVENT_SLOT_FOUND,
                                                    payload={
                                                        "field": field,
                                                        "value": value,
                                                        "confidence": confidence,
                                                        "source": source,
                                                        "user_id": sender.id,
                                                    },
                                                    timestamp=time.time(),
                                                )
                                            )
                                    
                                    # Обновляем user_context_data после сохранения слотов
                                    user_context_data = self.memory.get_user_context(sender.id)
                                    
                                    # Проверяем confidence и генерируем уточняющие вопросы
                                    low_conf_slots = self.sales_flow.get_low_confidence_slots(
                                        user_context_data, threshold=0.6
                                    )
                                    medium_conf_slots = self.sales_flow.get_medium_confidence_slots(
                                        user_context_data, threshold_min=0.6, threshold_max=0.8
                                    )
                                    
                                    # Проверяем согласие на сбор контактов (PDPA)
                                    if "contact" in [s["field"] for s in extracted_slots_list]:
                                        if (
                                            self.consent_manager
                                            and not self.consent_manager.check_consent(
                                                sender.id, ConsentManager.CONSENT_PDPA_PROFILE
                                            )
                                        ):
                                            # Запрашиваем согласие
                                            consent_message = self.consent_manager.request_consent(
                                                sender.id,
                                                ConsentManager.CONSENT_PDPA_PROFILE,
                                                "Для продолжения нужно ваше согласие на обработку персональных данных.",
                                            )
                                            if consent_message:
                                                # Сохраняем флаг что нужно запросить согласие
                                                if user_context_data:
                                                    try:
                                                        context_dict = json.loads(user_context_data)
                                                    except (json.JSONDecodeError, ValueError):
                                                        context_dict = {}
                                                else:
                                                    context_dict = {}
                                                context_dict["pending_consent"] = {
                                                    "type": ConsentManager.CONSENT_PDPA_PROFILE,
                                                    "message": consent_message,
                                                }
                                                user_context_data = json.dumps(context_dict)
                                                self.memory.save_user_context(sender.id, user_context_data)
                                    
                                    # Если есть слоты с низкой confidence - генерируем уточняющий вопрос
                                    if low_conf_slots and current_stage == SalesStage.NEEDS_DISCOVERY:
                                        # Берем первый слот с низкой confidence
                                        field_to_clarify = low_conf_slots[0]
                                        slots_with_conf = self.sales_flow.get_slots_with_confidence(
                                            user_context_data
                                        )
                                        slot_data = slots_with_conf.get(field_to_clarify, {})
                                        value = slot_data.get("value", "")
                                        
                                        # Генерируем уточняющий вопрос через LLM
                                        clarification_prompt = f"""Пользователь сказал: "{message_text}"

Я извлек информацию о поле "{field_to_clarify}": "{value}", но уверенность низкая.

Сгенерируй ОДИН короткий уточняющий вопрос для этого поля. Вопрос должен быть естественным и не навязчивым.

Примеры хороших вопросов:
- "Уточни, пожалуйста, какая именно задача отнимает больше всего времени?"
- "Правильно ли я понял, что у вас около 50 сотрудников?"
- "Можешь уточнить название компании?"

Вопрос (максимум 1 предложение):"""

                                        clarification_messages = [
                                            {"role": "user", "content": clarification_prompt}
                                        ]
                                        clarification_question = await self.ai_client.get_response(
                                            clarification_messages,
                                            temperature=0.5,
                                            max_tokens=100,
                                        )
                                        
                                        # Сохраняем уточняющий вопрос для добавления к ответу
                                        if clarification_question:
                                            # Добавим к response позже, после генерации основного ответа
                                            # Пока сохраняем в контекст для использования
                                            if user_context_data:
                                                try:
                                                    context_dict = json.loads(user_context_data)
                                                except (json.JSONDecodeError, ValueError):
                                                    context_dict = {}
                                            else:
                                                context_dict = {}
                                            context_dict["pending_clarification"] = {
                                                "field": field_to_clarify,
                                                "question": clarification_question.strip(),
                                            }
                                            user_context_data = json.dumps(context_dict)
                                            self.memory.save_user_context(sender.id, user_context_data)
                                    
                                    # Если есть слоты со средней confidence - мягко подтверждаем
                                    elif medium_conf_slots and current_stage == SalesStage.NEEDS_DISCOVERY:
                                        # Берем первый слот со средней confidence
                                        field_to_confirm = medium_conf_slots[0]
                                        slots_with_conf = self.sales_flow.get_slots_with_confidence(
                                            user_context_data
                                        )
                                        slot_data = slots_with_conf.get(field_to_confirm, {})
                                        value = slot_data.get("value", "")
                                        
                                        # Сохраняем подтверждение для добавления к ответу
                                        if user_context_data:
                                            try:
                                                context_dict = json.loads(user_context_data)
                                            except (json.JSONDecodeError, ValueError):
                                                context_dict = {}
                                        else:
                                            context_dict = {}
                                        context_dict["pending_confirmation"] = {
                                            "field": field_to_confirm,
                                            "value": value,
                                        }
                                        user_context_data = json.dumps(context_dict)
                                        self.memory.save_user_context(sender.id, user_context_data)
                            else:
                                # Используем старый метод для обратной совместимости
                                user_context_data = await self.sales_flow.auto_extract_slots(
                                    message_text, user_context_data, current_intent
                                )
                                self.memory.save_user_context(sender.id, user_context_data)

                        except Exception as e:
                            logger.error(
                                f"Error auto-extracting slots: {e}", exc_info=True
                            )
                            # Продолжаем работу даже если автоизвлечение не удалось

                    # Автоматический переход на CONSULTATION_OFFER после PRESENTATION
                    # Проверяем ПОСЛЕ извлечения слотов, чтобы использовать актуальные данные
                    if (
                        new_stage is None
                        and current_stage == SalesStage.PRESENTATION
                        and self.sales_flow
                        and self.meeting_summary
                    ):
                        # Получаем слоты для проверки готовности к встрече (после извлечения)
                        slots = self.sales_flow.get_slots(user_context_data)
                        is_ready = self.meeting_summary.is_ready_for_meeting(slots)

                        # Проверяем явный запрос на встречу
                        explicit_request = any(
                            keyword in message_text.lower()
                            for keyword in [
                                "созвониться",
                                "встретиться",
                                "поговорить",
                                "обсудить",
                                "консультация",
                                "встреча",
                                "созвон",
                            ]
                        )
                        
                        # Вычисляем fit_score
                        fit_score = self.sales_flow.compute_fit_score(user_context_data)
                        breakdown = self.sales_flow.get_fit_score_breakdown(user_context_data)
                        logger.info(
                            f"Fit score for user {sender.id}: {fit_score}/100 "
                            f"(breakdown: {breakdown['components']})"
                        )
                        
                        # Проверяем, нужно ли предложить консультацию
                        should_offer = self.sales_flow.should_offer_consultation(
                            user_context_data,
                            current_intent,
                            presentation_messages_count,
                            is_ready,
                            explicit_request=explicit_request,
                        )
                        
                        # Если fit_score < 60 и нет явного запроса - не предлагаем встречу
                        if fit_score < self.sales_flow.FIT_SCORE_THRESHOLD and not explicit_request:
                            should_offer = False
                            logger.info(
                                f"Not offering consultation: fit_score={fit_score} < threshold={self.sales_flow.FIT_SCORE_THRESHOLD}, "
                                f"explicit_request={explicit_request}"
                            )

                        if should_offer:
                            logger.info(
                                f"Auto-transitioning to CONSULTATION_OFFER: "
                                f"is_ready={is_ready}, messages_count={presentation_messages_count}"
                            )
                            new_stage = SalesStage.CONSULTATION_OFFER
                            user_context_data = self.sales_flow.update_stage(
                                user_context_data, new_stage
                            )
                            # Сбрасываем счетчик при переходе
                            if user_context_data:
                                try:
                                    context_dict = json.loads(user_context_data)
                                    context_dict.pop(
                                        "presentation_messages_count", None
                                    )
                                    user_context_data = json.dumps(context_dict)
                                except (json.JSONDecodeError, ValueError):
                                    pass
                            self.memory.save_user_context(sender.id, user_context_data)
                            current_stage = new_stage

                # Проверяем и запрашиваем недостающие слоты (только для Sales/Real Estate)
                slot_prompt_addition = ""
                if (
                    self.sales_flow
                    and self.sales_flow.enabled
                    and current_intent in ("SALES_AI", "REAL_ESTATE")
                ):
                    next_slot = self.sales_flow.get_next_slot_to_ask(
                        user_context_data, current_intent
                    )
                    if next_slot:
                        slot_prompt = self.sales_flow.get_slot_prompt(
                            next_slot, current_intent
                        )
                        if slot_prompt:
                            slot_prompt_addition = (
                                f"\n\nВАЖНО: Сейчас нужно выяснить: {slot_prompt} "
                                f"Используй этот вопрос естественно в диалоге, но не навязывай."
                            )

                # max_response_length убран - единственный лимит это лимит Telegram (4096 символов)

                # Модифицируем системный промпт для текущего этапа
                if (
                    self.sales_flow
                    and self.sales_flow.enabled
                    and current_stage is not None
                ):
                    stage_modifier = self.sales_flow.get_stage_prompt_modifier(
                        current_stage
                    )
                else:
                    stage_modifier = None

                # Добавляем инструкцию о представлении на основе флага introduced
                # Эта инструкция добавляется всегда, независимо от sales_flow
                introduction_instruction = ""
                if is_introduced:
                    introduction_instruction = "\n\n⚠️ ВАЖНО: Пользователь уже знает, что ты Александр из Scanovich.ai. НЕ повторяй эту информацию в ответе, просто общайся естественно. Не упоминай свое имя и компанию, если это не требуется по контексту."
                else:
                    introduction_instruction = "\n\n⚠️ ВАЖНО: Это первое знакомство с пользователем. Представься как Александр из Scanovich.ai при приветствии."

                # Формируем инструкции (будет добавлено ПОСЛЕ основного промпта)
                # Единственный лимит - лимит Telegram (4096 символов), который обрабатывается автоматически
                length_info = "\n\nВАЖНО: Отвечай ПОЛНОСТЬЮ и развернуто, не обрезай ответ. Если ответ превысит 4096 символов, система автоматически разобьет его на несколько сообщений. НЕ добавляй многоточие и НЕ обрезай ответ самостоятельно."

                # ВАЖНО: Добавляем инструкцию о языке ВСЕГДА на основе последнего сообщения
                language_instruction = ""
                if response_lang == "zh":
                    # Специальная инструкция для китайского - упрощенный китайский
                    language_instruction = "\n\n⚠️ ВАЖНО: Пользователь пишет на упрощенном китайском (Simplified Chinese). ОБЯЗАТЕЛЬНО отвечай ТОЛЬКО на упрощенном китайском языке. НЕ используй английский или русский язык. НЕ используй традиционный китайский (Traditional Chinese). Используй только упрощенный китайский (简体中文)."
                elif response_lang and response_lang in SUPPORTED_LANGUAGES:
                    lang_name = get_language_name(response_lang)
                    language_instruction = f"\n\n⚠️ ВАЖНО: Пользователь пишет на {lang_name} языке. ОБЯЗАТЕЛЬНО отвечай на {lang_name} языке. Не переключайся на другие языки, если пользователь пишет на конкретном языке."
                elif not response_lang or response_lang == "ru":
                    # По умолчанию русский язык
                    language_instruction = "\n\n⚠️ ВАЖНО: Пользователь пишет на русском языке. Отвечай на русском языке."

                # Формируем модификаторы для добавления ПОСЛЕ основного промпта
                if stage_modifier:
                    full_modifier = (
                        introduction_instruction
                        + language_instruction
                        + "\n\n"
                        + stage_modifier
                        + length_info
                        + slot_prompt_addition
                    )
                else:
                    full_modifier = (
                        introduction_instruction
                        + language_instruction
                        + length_info
                        + slot_prompt_addition
                    )

                # Обновляем или добавляем системное сообщение
                # ВАЖНО: Структура должна быть: Дата -> Основной промпт -> Модификаторы
                # Дата добавляется в ai_client.py в начало системного сообщения
                # Основной промпт должен быть ПЕРВЫМ в системном сообщении, модификаторы ПОСЛЕ него
                modified_context = context.copy()
                system_found = False
                main_prompt = self.ai_client.system_prompt or ""

                for msg in modified_context:
                    if msg.get("role") == "system":
                        content = msg.get("content", "")
                        # Проверяем, есть ли уже основной промпт
                        has_main_prompt = (
                            "Александр" in content
                            and "Scanovich.ai" in content
                            and "Принципы общения" in content
                        )

                        if has_main_prompt:
                            # Основной промпт уже есть - добавляем модификаторы ПОСЛЕ него
                            msg["content"] = content + "\n\n" + full_modifier
                        else:
                            # Основного промпта нет - добавляем его сначала, затем модификаторы
                            if main_prompt:
                                msg["content"] = main_prompt + "\n\n" + full_modifier
                            else:
                                msg["content"] = content + "\n\n" + full_modifier
                        system_found = True
                        break

                if not system_found:
                    # Системного сообщения нет - создаем с основным промптом и модификаторами
                    # Дата будет добавлена в ai_client.py в начало
                    if main_prompt:
                        system_content = main_prompt + "\n\n" + full_modifier
                    else:
                        system_content = full_modifier
                    modified_context.insert(
                        0, {"role": "system", "content": system_content}
                    )

                context = modified_context

                # Проверяем, нужен ли веб-поиск (по ключевым словам)
                web_search_results = None
                if (
                    self.tools
                    and self.tools.web_search_tool
                    and self.config.web_search.enabled
                ):
                    # Ключевые слова/фразы, которые требуют актуальных данных
                    search_triggers = [
                        "актуальн",
                        "новост",
                        "последн",
                        "сейчас",
                        "текущ",
                        "цены",
                        "стоимость",
                        "сколько стоит",
                        "тренд",
                        "статистика",
                        "данные",
                        "информация о",
                        "узнать о",
                        "найти",
                        "поиск",
                    ]

                    message_lower = message_text.lower()
                    needs_search = any(
                        trigger in message_lower for trigger in search_triggers
                    )

                    if needs_search:
                        logger.info(
                            f"🔍 Web search triggered for query: {message_text[:100]}"
                        )
                        try:
                            web_search_results = await self.tools.web_search(
                                query=message_text, user_id=sender.id
                            )
                            if web_search_results:
                                logger.info(
                                    f"✅ Web search completed: "
                                    f"{len(web_search_results.get('results', []))} results"
                                )
                                # Форматируем результаты для включения в контекст
                                formatted_results = (
                                    self.tools.web_search_tool.format_search_results(
                                        web_search_results
                                    )
                                )
                                if formatted_results:
                                    # Добавляем результаты поиска в контекст как системное сообщение
                                    context.append(
                                        {
                                            "role": "system",
                                            "content": f"Актуальная информация из интернета:\n\n{formatted_results}\n\nИспользуй эту информацию для ответа, но не повторяй источники дословно.",
                                        }
                                    )
                        except Exception as e:
                            logger.error(
                                f"Error performing web search: {e}", exc_info=True
                            )

                # Получаем динамические параметры генерации на основе intent и stage
                generation_params = {}
                if self.sales_flow and self.sales_flow.enabled and current_stage:
                    generation_params = self.sales_flow.get_generation_params(
                        current_stage, current_intent
                    )
                    logger.debug(
                        f"Using dynamic generation params for stage={current_stage.value}, "
                        f"intent={current_intent}: {generation_params}"
                    )

                # Генерируем ответ через AI
                try:
                    ai_request_start = time.time()
                    logger.info(
                        f"🤖 Sending {len(context)} messages to AI server for message_text: "
                        f"{message_text[:100] if message_text else '(empty)'}..."
                    )
                    used_max_tokens = generation_params.get("max_tokens") or self.config.ai_server.max_tokens
                    # max_tokens берется из generation_params если указан, иначе из config.yaml (8192)
                    # max_response_length убран - единственный лимит это лимит Telegram (4096 символов)
                    response = await self.ai_client.get_response(
                        context,
                        temperature=generation_params.get("temperature"),
                        max_tokens=generation_params.get("max_tokens"),  # Если None, используется из config.yaml
                        top_p=generation_params.get("top_p"),
                        frequency_penalty=generation_params.get("frequency_penalty"),
                        presence_penalty=generation_params.get("presence_penalty"),
                        rag_system=self.rag_system,
                    )
                    ai_request_time = time.time() - ai_request_start
                    stage_info = f", stage={current_stage.value}" if current_stage else ""
                    logger.info(
                        f"✅ AI response received in {ai_request_time:.2f}s ({len(response)} chars, "
                        f"max_tokens={used_max_tokens}{stage_info}): {response[:150]}..."
                    )
                    logger.debug(f"Full AI response: {response}")

                    # Рассчитываем оптимальный интервал перед отправкой (если включено умное распределение)
                    if smart_distribution and self.rate_limiter.enabled:
                        # Используем лимит типа чата если он установлен
                        messages_per_minute = (
                            chat_type_limit
                            if chat_type_limit
                            else self.config.rate_limiting.messages_per_minute
                        )
                        optimal_interval, needs_wait = (
                            self.rate_limiter.calculate_optimal_interval(
                                user_id=sender.id,
                                messages_per_minute=messages_per_minute,
                            )
                        )

                        if needs_wait and optimal_interval > 0:
                            logger.debug(
                                f"Waiting {optimal_interval:.2f}s before sending message "
                                f"(user_id={sender.id}, chat_type={chat_type})"
                            )
                            # Ждем оптимальный интервал (typing продолжает показываться если мы в контексте)
                            await asyncio.sleep(optimal_interval)

                    # Добавляем уточняющие вопросы, подтверждения или запросы согласия если есть
                    if user_context_data:
                        try:
                            context_dict = json.loads(user_context_data)
                            
                            # Обрабатываем запрос согласия (приоритет)
                            if "pending_consent" in context_dict:
                                consent_info = context_dict["pending_consent"]
                                consent_message = consent_info.get("message", "")
                                if consent_message:
                                    response = consent_message
                                    # Не удаляем pending_consent - ждем ответа пользователя
                            
                            # Добавляем уточняющий вопрос при низкой confidence
                            elif "pending_clarification" in context_dict:
                                clarification = context_dict["pending_clarification"]
                                response = f"{response}\n\n{clarification['question']}"
                                # Удаляем из контекста после использования
                                context_dict.pop("pending_clarification", None)
                                user_context_data = json.dumps(context_dict)
                                self.memory.save_user_context(sender.id, user_context_data)
                            
                            # Добавляем мягкое подтверждение при средней confidence
                            elif "pending_confirmation" in context_dict:
                                confirmation = context_dict["pending_confirmation"]
                                value = confirmation.get("value", "")
                                field = confirmation.get("field", "")
                                # Генерируем естественное подтверждение
                                confirmation_text = f"Верно ли, что {value}?"
                                response = f"{response}\n\n{confirmation_text}"
                                # Удаляем из контекста после использования
                                context_dict.pop("pending_confirmation", None)
                                user_context_data = json.dumps(context_dict)
                                self.memory.save_user_context(sender.id, user_context_data)
                        except (json.JSONDecodeError, ValueError):
                            pass
                    
                                    # Обрабатываем ответ на запрос согласия
                    if user_context_data:
                        try:
                            context_dict = json.loads(user_context_data)
                            
                            # Проверяем подтверждение предброни
                            if "last_event_id" in context_dict and self.calendar:
                                last_event_id = context_dict.get("last_event_id")
                                # Проверяем, является ли это предбронь (содержит [TENTATIVE] в названии)
                                try:
                                    event = self.calendar.service.events().get(
                                        calendarId="primary", eventId=last_event_id
                                    ).execute()
                                    if "[TENTATIVE]" in event.get("summary", ""):
                                        # Парсим ответ пользователя на подтверждение
                                        confirmation_keywords = [
                                            "да", "yes", "ок", "ok", "подтверждаю",
                                            "подтверждаем", "создать", "создай", "✅", "👍"
                                        ]
                                        if any(keyword in message_text.lower() for keyword in confirmation_keywords):
                                            # Подтверждаем предбронь
                                            self.calendar.confirm_tentative_event(last_event_id)
                                            logger.info(f"Tentative event confirmed: {last_event_id}")
                                            
                                            # Обновляем контекст
                                            context_dict["last_event_id"] = last_event_id
                                            user_context_data = json.dumps(context_dict)
                                            self.memory.save_user_context(sender.id, user_context_data)
                                            
                                            await self.safe_reply(
                                                event,
                                                "✅ Встреча подтверждена!"
                                            )
                                            if self.global_rate_limiter:
                                                self.global_rate_limiter.record_message()
                                            return
                                except Exception as e:
                                    logger.debug(f"Error checking tentative event: {e}")
                            
                            # Обрабатываем запрос согласия
                            if "pending_consent" in context_dict and self.consent_manager:
                                consent_info = context_dict["pending_consent"]
                                consent_type = consent_info.get("type")
                                
                                # Парсим ответ пользователя
                                consent_granted = self.consent_manager.parse_consent_response(
                                    message_text
                                )
                                
                                if consent_granted is not None:
                                    # Записываем согласие
                                    self.consent_manager.record_consent(
                                        sender.id, consent_type, consent_granted
                                    )
                                    
                                    # Публикуем событие
                                    if self.event_bus:
                                        self.event_bus.publish(
                                            Event(
                                                name=EVENT_CONSENT_GIVEN,
                                                payload={
                                                    "consent_type": consent_type,
                                                    "granted": consent_granted,
                                                    "user_id": sender.id,
                                                },
                                                timestamp=time.time(),
                                            )
                                        )
                                    
                                    # Удаляем из контекста
                                    context_dict.pop("pending_consent", None)
                                    user_context_data = json.dumps(context_dict)
                                    self.memory.save_user_context(sender.id, user_context_data)
                                    
                                    if consent_granted:
                                        response = "Спасибо! Продолжаем."
                                    else:
                                        response = "Понял. Без вашего согласия я не буду сохранять персональные данные."
                                    
                                    # Отправляем ответ о согласии и выходим (не генерируем основной ответ)
                                    await self.safe_reply(event, response)
                                    if self.global_rate_limiter:
                                        self.global_rate_limiter.record_message()
                                    return
                        except (json.JSONDecodeError, ValueError):
                            pass

                    # Устанавливаем флаг introduced ПОСЛЕ генерации ответа (чтобы промпт видел первое знакомство)
                    if not is_introduced and (
                        is_first_message or (current_stage and current_stage == SalesStage.GREETING)
                    ):
                        if user_context_data:
                            try:
                                context_dict = json.loads(user_context_data)
                                context_dict["introduced"] = True
                                user_context_data = json.dumps(context_dict)
                                self.memory.save_user_context(
                                    sender.id, user_context_data
                                )
                            except (json.JSONDecodeError, ValueError):
                                # Создаем новый контекст с флагом
                                context_dict = {"introduced": True}
                                user_context_data = json.dumps(context_dict)
                                self.memory.save_user_context(
                                    sender.id, user_context_data
                                )
                        else:
                            # Создаем новый контекст с флагом
                            user_context_data = json.dumps({"introduced": True})
                            self.memory.save_user_context(sender.id, user_context_data)
                        logger.debug(f"Flag 'introduced' set to True for user {sender.id}")

                    # Отправляем ответ
                    await self.safe_reply(event, response)
                    logger.info(f"✅ Reply sent to user {sender.id}")

                    # Записываем глобальное сообщение после успешной отправки
                    if self.global_rate_limiter:
                        self.global_rate_limiter.record_message()

                    # Сохраняем ответ ассистента
                    saved_response = self.memory.save_message(
                        user_id=sender.id,
                        content=response,
                        role="assistant",
                        username=username,
                    )

                    # Добавляем ответ ассистента в векторное хранилище (асинхронно, не блокируем)
                    if (
                        self.vector_memory
                        and self.vector_memory.enabled
                        and saved_response
                    ):
                        try:
                            await self.vector_memory.add_message(
                                message_id=saved_response.id,
                                user_id=sender.id,
                                conversation_id=saved_response.conversation_id,
                                content=response,
                                role="assistant",
                                timestamp=saved_response.timestamp.isoformat()
                                if saved_response.timestamp
                                else None,
                            )
                        except Exception as e:
                            logger.debug(
                                f"Could not add response to vector store (non-blocking): {e}"
                            )

                    # Автоматическое сохранение лида если заполнены ключевые слоты
                    if (
                        self.tools
                        and self.sales_flow
                        and self.sales_flow.enabled
                        and current_intent in ("SALES_AI", "REAL_ESTATE")
                    ):
                        try:
                            filled_slots = self.sales_flow.get_slots(user_context_data)
                            # Сохраняем лид если заполнено хотя бы 2 ключевых слота
                            key_slots = [
                                "goal",
                                "purpose",
                                "budget",
                                "budget_band",
                                "contact",
                            ]
                            filled_key_slots = [
                                slot for slot in key_slots if slot in filled_slots
                            ]

                            if len(filled_key_slots) >= 2:  # Минимум 2 ключевых слота
                                # Извлекаем имя из контекста или используем username
                                lead_name = username or filled_slots.get("name")

                                # Получаем текущий stage для заметок
                                current_stage_for_notes = None
                                if user_context_data:
                                    try:
                                        context_dict = json.loads(user_context_data)
                                        current_stage_for_notes = context_dict.get(
                                            "sales_stage", "unknown"
                                        )
                                    except (json.JSONDecodeError, ValueError):
                                        pass

                                result = self.tools.save_lead(
                                    user_id=sender.id,
                                    name=lead_name,
                                    lang=current_intent or "ru",
                                    contact=filled_slots.get("contact"),
                                    source="telegram",
                                    slots=filled_slots,
                                    notes=f"Intent: {current_intent}, Stage: {current_stage_for_notes or 'unknown'}",
                                )
                                if result.get("status") == "saved":
                                    logger.info(
                                        f"✅ Lead auto-saved for user_id={sender.id}"
                                    )
                        except Exception as e:
                            logger.error(f"Error auto-saving lead: {e}", exc_info=True)

                    # Автоматическое создание встреч при запросах на консультацию
                    if (
                        self.calendar
                        and self.calendar.auto_create_consultations
                        and self.calendar.detect_consultation_request(message_text)
                    ):
                        try:
                            # Получаем время сообщения от Telegram (UTC) и конвертируем в локальную таймзону
                            message_time_utc = (
                                event.message.date
                            )  # datetime в UTC от Telegram
                            message_time_local = message_time_utc.astimezone(
                                self.calendar.timezone
                            )

                            logger.debug(
                                f"Message time from Telegram: UTC={message_time_utc}, "
                                f"Local={message_time_local} (timezone: {self.calendar.timezone_name})"
                            )

                            # Проверяем запрос на перенос/отмену
                            reschedule_type, is_reschedule = (
                                self.calendar.detect_reschedule_request(message_text)
                            )

                            if is_reschedule:
                                # Обработка переноса или отмены
                                latest_event = self.calendar.find_latest_user_event(
                                    sender.id
                                )

                                if reschedule_type == "cancel":
                                    # Отмена встречи
                                    if latest_event:
                                        event_id = latest_event.get("id")
                                        self.calendar.delete_event(event_id)

                                        # Обновляем контекст пользователя
                                        if user_context_data:
                                            try:
                                                context_dict = json.loads(
                                                    user_context_data
                                                )
                                                context_dict.pop("last_event_id", None)
                                                context_dict.pop(
                                                    "last_event_time", None
                                                )
                                                self.memory.save_user_context(
                                                    sender.id, json.dumps(context_dict)
                                                )
                                            except (json.JSONDecodeError, ValueError):
                                                pass

                                        await self.safe_reply(
                                            event, "✅ Встреча отменена."
                                        )
                                        if self.global_rate_limiter:
                                            self.global_rate_limiter.record_message()
                                        logger.info(
                                            f"Event cancelled: {event_id} for user_id={sender.id}"
                                        )
                                    else:
                                        await self.safe_reply(
                                            event,
                                            "Не найдено запланированных встреч для отмены.",
                                        )
                                        if self.global_rate_limiter:
                                            self.global_rate_limiter.record_message()

                                elif reschedule_type == "reschedule":
                                    # Перенос встречи
                                    if latest_event:
                                        # Извлекаем новое время из сообщения
                                        extracted_time = (
                                            self.calendar.extract_time_from_message(
                                                message_text,
                                                reference_time=message_time_local,
                                            )
                                        )

                                        if extracted_time:
                                            # Валидируем время
                                            end_time = extracted_time + timedelta(
                                                minutes=self.calendar.default_consultation_duration_minutes
                                            )
                                            is_valid, error_msg = (
                                                self.calendar.validate_event_time(
                                                    extracted_time, end_time
                                                )
                                            )

                                            if not is_valid:
                                                await event.reply(f"❌ {error_msg}")
                                                return

                                            # Проверяем конфликты (исключаем текущее событие)
                                            event_id = latest_event.get("id")
                                            has_conflict, conflicts = (
                                                self.calendar.check_time_conflict(
                                                    extracted_time,
                                                    end_time,
                                                    exclude_event_id=event_id,
                                                )
                                            )

                                            if has_conflict:
                                                await event.reply(
                                                    "❌ На это время уже есть другая встреча. "
                                                    "Выберите другое время."
                                                )
                                                return

                                            # Обновляем встречу
                                            self.calendar.update_event(
                                                event_id, extracted_time, end_time
                                            )

                                            # Обновляем контекст пользователя
                                            if user_context_data:
                                                try:
                                                    context_dict = json.loads(
                                                        user_context_data
                                                    )
                                                    context_dict["last_event_id"] = (
                                                        event_id
                                                    )
                                                    context_dict["last_event_time"] = (
                                                        extracted_time.strftime(
                                                            "%Y-%m-%dT%H:%M:%S"
                                                        )
                                                    )
                                                    self.memory.save_user_context(
                                                        sender.id,
                                                        json.dumps(context_dict),
                                                    )
                                                except (
                                                    json.JSONDecodeError,
                                                    ValueError,
                                                ):
                                                    pass

                                            logger.info(
                                                f"✅ Event rescheduled: {event_id} to {extracted_time.strftime('%Y-%m-%d %H:%M')} "
                                                f"(local timezone: {self.calendar.timezone_name})"
                                            )
                                            await event.reply(
                                                f"✅ Встреча перенесена на {extracted_time.strftime('%d.%m в %H:%M')}!"
                                            )
                                        else:
                                            # Время не найдено - предлагаем слоты
                                            slots = (
                                                self.calendar.suggest_available_slots()
                                            )
                                            slots_text = "\n".join(
                                                f"• {slot}" for slot in slots
                                            )
                                            await event.reply(
                                                f"📅 На какое время перенести встречу?\n\n{slots_text}\n\n"
                                                "Напишите удобное время."
                                            )
                                    else:
                                        await event.reply(
                                            "Не найдено запланированных встреч для переноса. "
                                            "Создать новую встречу?"
                                        )
                            else:
                                # Обычное создание встречи
                                # Извлекаем время из сообщения или ответа, используя время от Telegram
                                extracted_time = (
                                    self.calendar.extract_time_from_message(
                                        message_text, reference_time=message_time_local
                                    )
                                )
                                if not extracted_time:
                                    extracted_time = (
                                        self.calendar.extract_time_from_message(
                                            response, reference_time=message_time_local
                                        )
                                    )

                                if extracted_time:
                                    # Валидируем время
                                    end_time = extracted_time + timedelta(
                                        minutes=self.calendar.default_consultation_duration_minutes
                                    )
                                    is_valid, error_msg = (
                                        self.calendar.validate_event_time(
                                            extracted_time, end_time
                                        )
                                    )

                                    if not is_valid:
                                        await event.reply(f"❌ {error_msg}")
                                        return

                                    # Проверяем конфликты
                                    has_conflict, conflicts = (
                                        self.calendar.check_time_conflict(
                                            extracted_time, end_time
                                        )
                                    )

                                    if has_conflict:
                                        await event.reply(
                                            "❌ На это время уже есть встреча. "
                                            "Выберите другое время."
                                        )
                                        return

                                    # Проверяем согласие на создание встречи
                                    if (
                                        self.consent_manager
                                        and not self.consent_manager.check_consent(
                                            sender.id, ConsentManager.CONSENT_CALENDAR_INVITE
                                        )
                                    ):
                                        # Запрашиваем согласие
                                        consent_message = self.consent_manager.request_consent(
                                            sender.id,
                                            ConsentManager.CONSENT_CALENDAR_INVITE,
                                            "Для создания встречи в календаре нужно ваше согласие.",
                                        )
                                        if consent_message:
                                            await self.safe_reply(event, consent_message)
                                            if self.global_rate_limiter:
                                                self.global_rate_limiter.record_message()
                                            return
                                    
                                    # Создаем предбронь на указанное время
                                    tentative_event_id = self.calendar.create_tentative_event(
                                        summary="Консультация Scanovich.ai",
                                        description="Консультация с пользователем Telegram",
                                        start_time=extracted_time,
                                        end_time=end_time,
                                        user_id=sender.id,
                                        tentative_until_minutes=15,
                                    )
                                    
                                    # Пока сохраняем tentative_event_id, подтвердим позже
                                    event_id = tentative_event_id

                                    # Сохраняем контекст встречи
                                    if user_context_data:
                                        try:
                                            context_dict = json.loads(user_context_data)
                                        except (json.JSONDecodeError, ValueError):
                                            context_dict = {}
                                    else:
                                        context_dict = {}
                                    context_dict["last_event_id"] = event_id
                                    context_dict["last_event_time"] = (
                                        extracted_time.strftime("%Y-%m-%dT%H:%M:%S")
                                    )

                                    # Генерируем и отправляем summary для встречи
                                    if self.meeting_summary and self.sales_flow:
                                        try:
                                            # Получаем слоты из контекста
                                            slots = self.sales_flow.get_slots(
                                                user_context_data
                                            )

                                            # Получаем историю диалога
                                            conversation_history = (
                                                self.memory.get_context(
                                                    sender.id, limit=100
                                                )
                                            )

                                            # Получаем текущий этап продаж
                                            current_stage_str = None
                                            if user_context_data:
                                                try:
                                                    context_data = json.loads(
                                                        user_context_data
                                                    )
                                                    current_stage_str = (
                                                        context_data.get("sales_stage")
                                                    )
                                                except (
                                                    json.JSONDecodeError,
                                                    ValueError,
                                                ):
                                                    pass

                                            # Получаем имя клиента
                                            client_name = slots.get("client_name")
                                            if not client_name and user_context_data:
                                                try:
                                                    context_data = json.loads(
                                                        user_context_data
                                                    )
                                                    client_name = context_data.get(
                                                        "name"
                                                    )
                                                except (
                                                    json.JSONDecodeError,
                                                    ValueError,
                                                ):
                                                    pass

                                            # Вычисляем fit_score для включения в сводку
                                            fit_score = self.sales_flow.compute_fit_score(
                                                user_context_data
                                            )
                                            
                                            # Добавляем fit_score в слоты для отчета
                                            slots["fit_score"] = fit_score
                                            
                                            # Генерируем мини-повестку
                                            mini_agenda = self.meeting_summary.generate_mini_agenda(
                                                slots, fit_score
                                            )
                                            
                                            # Генерируем полную сводку
                                            full_summary = self.meeting_summary.generate_full_summary(
                                                slots,
                                                conversation_history,
                                                current_stage_str,
                                            )

                                            # Генерируем отчет для владельца
                                            owner_report = self.meeting_summary.generate_owner_report(
                                                client_name,
                                                slots,
                                                conversation_history,
                                                current_stage_str,
                                            )
                                            
                                            # Проверяем согласие перед отправкой отчета
                                            if (
                                                self.consent_manager
                                                and not self.consent_manager.check_consent(
                                                    sender.id, ConsentManager.CONSENT_CALENDAR_INVITE
                                                )
                                            ):
                                                logger.warning(
                                                    f"Not sending meeting summary: consent not granted for user_id={sender.id}"
                                                )
                                                owner_report = None

                                            # Сохраняем summary в контекст
                                            context_dict["meeting_summary"] = full_summary
                                            context_dict["meeting_summary_json"] = (
                                                self.meeting_summary.generate_json_summary(slots)
                                            )
                                            context_dict["meeting_mini_agenda"] = mini_agenda
                                            context_dict["meeting_fit_score"] = fit_score

                                            # Отправляем отчет владельцу
                                            if owner_report:
                                                await self.send_summary_to_owner(
                                                    owner_report
                                                )
                                                logger.info(
                                                    f"Meeting summary sent to owner for user {sender.id}"
                                                )

                                            logger.info(
                                                f"Meeting summary generated for user {sender.id}"
                                            )
                                        except Exception as e:
                                            logger.error(
                                                f"Error generating meeting summary: {e}",
                                                exc_info=True,
                                            )
                                            # Не прерываем создание встречи при ошибке генерации summary

                                    self.memory.save_user_context(
                                        sender.id, json.dumps(context_dict)
                                    )

                                    # Проверяем, является ли это предбронь
                                    if user_context_data:
                                        try:
                                            context_dict = json.loads(user_context_data)
                                            last_event_id = context_dict.get("last_event_id")
                                            if last_event_id == tentative_event_id:
                                                # Это предбронь - нужно подтверждение
                                                # Публикуем событие TIME_PROPOSED
                                                if self.event_bus:
                                                    self.event_bus.publish(
                                                        Event(
                                                            name=EVENT_TIME_PROPOSED,
                                                            payload={
                                                                "time": extracted_time.isoformat(),
                                                                "event_id": tentative_event_id,
                                                                "user_id": sender.id,
                                                            },
                                                            timestamp=time.time(),
                                                        )
                                                    )
                                                
                                                logger.info(
                                                    f"✅ Tentative event created: {tentative_event_id} at {extracted_time.strftime('%Y-%m-%d %H:%M')} "
                                                    f"(local timezone: {self.calendar.timezone_name}, user_id={sender.id})"
                                                )
                                                # Отправляем пользователю сообщение с подтверждением
                                                await self.safe_reply(
                                                    event,
                                                    f"✅ Предбронь создана на {extracted_time.strftime('%d.%m в %H:%M')}!\n\n"
                                                    "Подтвердите встречу в течение 15 минут, иначе она будет автоматически отменена.",
                                                )
                                            else:
                                                # Подтверждаем предбронь
                                                if last_event_id:
                                                    self.calendar.confirm_tentative_event(last_event_id)
                                                
                                                logger.info(
                                                    f"✅ Consultation event created: {event_id} at {extracted_time.strftime('%Y-%m-%d %H:%M')} "
                                                    f"(local timezone: {self.calendar.timezone_name}, user_id={sender.id})"
                                                )
                                                # Отправляем пользователю сообщение с локальным временем
                                                await self.safe_reply(
                                                    event,
                                                    f"✅ Встреча создана на {extracted_time.strftime('%d.%m в %H:%M')}!",
                                                )
                                        except (json.JSONDecodeError, ValueError):
                                            # Если не удалось проверить - просто создаем обычное событие
                                            logger.info(
                                                f"✅ Consultation event created: {event_id} at {extracted_time.strftime('%Y-%m-%d %H:%M')} "
                                                f"(local timezone: {self.calendar.timezone_name}, user_id={sender.id})"
                                            )
                                            await self.safe_reply(
                                                event,
                                                f"✅ Встреча создана на {extracted_time.strftime('%d.%m в %H:%M')}!",
                                            )
                                    else:
                                        logger.info(
                                            f"✅ Consultation event created: {event_id} at {extracted_time.strftime('%Y-%m-%d %H:%M')} "
                                            f"(local timezone: {self.calendar.timezone_name}, user_id={sender.id})"
                                        )
                                        await self.safe_reply(
                                            event,
                                            f"✅ Встреча создана на {extracted_time.strftime('%d.%m в %H:%M')}!",
                                        )
                                    
                                    if self.global_rate_limiter:
                                        self.global_rate_limiter.record_message()
                                else:
                                    # Предлагаем доступные слоты с учетом таймзоны пользователя
                                    user_timezone = self.memory.get_user_timezone(sender.id)
                                    suggested_slots = self.calendar.suggest_time_slots(
                                        user_timezone=user_timezone, count=3
                                    )
                                    
                                    if suggested_slots:
                                        slots_text = "\n".join(
                                            f"• {slot.strftime('%d.%m в %H:%M')}" for slot in suggested_slots
                                        )
                                        await self.safe_reply(
                                            event,
                                            f"📅 Предлагаю следующие варианты времени:\n{slots_text}\n\n"
                                            "Напишите удобное время, и я создам встречу!",
                                        )
                                    else:
                                        # Fallback на старый метод
                                        slots = self.calendar.suggest_available_slots()
                                        slots_text = "\n".join(
                                            f"• {slot}" for slot in slots
                                        )
                                        await self.safe_reply(
                                            event,
                                            f"📅 Предлагаю следующие варианты времени:\n{slots_text}\n\n"
                                            "Напишите удобное время, и я создам встречу!",
                                        )
                                    if self.global_rate_limiter:
                                        self.global_rate_limiter.record_message()
                        except Exception as e:
                            logger.error(
                                f"Error handling consultation request: {e}",
                                exc_info=True,
                            )
                            await event.reply(
                                "❌ Произошла ошибка при обработке запроса на встречу. Попробуйте позже."
                            )

                except httpx.ReadTimeout as e:
                    # ReadTimeout должен обрабатываться ПЕРВЫМ, так как он является подклассом TimeoutException
                    logger.error(f"Read timeout from AI server: {e}", exc_info=True)
                    await event.reply(
                        "⏱️ AI сервер не успел сгенерировать ответ за отведенное время. Попробуйте позже или переформулируйте запрос."
                    )
                except httpx.TimeoutException as e:
                    # TimeoutException (включая ConnectTimeout) обрабатывается после ReadTimeout
                    logger.error(f"Timeout connecting to AI server: {e}", exc_info=True)
                    await event.reply(
                        "⏱️ Таймаут подключения к AI серверу. Сервер недоступен или перегружен. Попробуйте позже."
                    )
                except httpx.NetworkError as e:
                    logger.error(f"Network error: {e}", exc_info=True)
                    await event.reply(
                        "🌐 Ошибка сети при подключении к AI серверу. Проверьте интернет-соединение."
                    )
                except httpx.HTTPStatusError as e:
                    logger.error(
                        f"HTTP error from AI server: {e.response.status_code} - {e.response.text}",
                        exc_info=True,
                    )
                    # Пытаемся извлечь детали ошибки из ответа
                    error_detail = ""
                    try:
                        if e.response is not None:
                            error_json = e.response.json()
                            if "error" in error_json:
                                error_detail = error_json["error"].get("message", "")
                    except Exception:
                        error_detail = str(e.response.text) if e.response else ""
                    
                    if e.response.status_code == 404:
                        user_error = "❌ Ошибка подключения к AI серверу. Проверьте настройки (URL и модель)."
                    elif e.response.status_code == 400:
                        # Ошибка 400 обычно связана с превышением max_tokens или неверным форматом
                        if "max_tokens" in error_detail.lower() or "max_completion_tokens" in error_detail.lower():
                            user_error = (
                                "⚠️ Контекст сообщения слишком большой для обработки. "
                                "Попробуйте сократить сообщение или разбить его на части."
                            )
                        else:
                            user_error = f"❌ Ошибка запроса к AI серверу: {error_detail[:200] if error_detail else 'неверный формат запроса'}"
                    elif e.response.status_code >= 500:
                        user_error = (
                            "🔧 Ошибка на стороне AI сервера. Попробуйте позже."
                        )
                    else:
                        user_error = f"❌ Ошибка AI сервера (код {e.response.status_code}). Попробуйте позже."
                    await event.reply(user_error)
                except Exception as e:
                    logger.error(f"Error getting AI response: {e}", exc_info=True)
                    error_msg = str(e)
                    # Более информативное сообщение об ошибке
                    if "404" in error_msg or "Not Found" in error_msg:
                        user_error = (
                            "❌ Ошибка подключения к AI серверу. Проверьте настройки."
                        )
                    elif "timeout" in error_msg.lower() or "Timeout" in error_msg:
                        user_error = "⏱️ Таймаут при генерации ответа. Попробуйте позже."
                    else:
                        user_error = (
                            f"❌ Ошибка при генерации ответа: {error_msg[:100]}"
                        )

                    await event.reply(user_error)

        except Exception as e:
            logger.error(f"Error handling message: {e}", exc_info=True)

    def _split_long_message(self, message: str, max_length: int = 4000) -> List[str]:
        """
        Разбить длинное сообщение на части для отправки в Telegram.

        Telegram позволяет до 4096 символов, но используем 4000 для безопасности.
        Разбивает по предложениям/абзацам для лучшей читаемости.

        Args:
            message: Текст сообщения
            max_length: Максимальная длина одной части (по умолчанию 4000)

        Returns:
            Список частей сообщения
        """
        if len(message) <= max_length:
            return [message]

        parts = []
        # Разбиваем по абзацам (двойной перенос строки)
        paragraphs = message.split("\n\n")
        current_part = ""

        for paragraph in paragraphs:
            # Если текущий абзац + новый параграф помещается - добавляем
            if len(current_part) + len(paragraph) + 2 <= max_length:
                if current_part:
                    current_part += "\n\n" + paragraph
                else:
                    current_part = paragraph
            else:
                # Если текущий абзац не пуст - сохраняем его
                if current_part:
                    parts.append(current_part)
                    current_part = paragraph
                else:
                    # Абзац сам по себе слишком длинный - разбиваем по предложениям
                    if len(paragraph) > max_length:
                        sentences = re.split(r"([.!?]\s+)", paragraph)
                        temp_sentence = ""

                        for i in range(0, len(sentences), 2):
                            if i + 1 < len(sentences):
                                sentence = sentences[i] + sentences[i + 1]
                            else:
                                sentence = sentences[i]

                            if len(temp_sentence) + len(sentence) <= max_length:
                                temp_sentence += sentence
                            else:
                                if temp_sentence:
                                    parts.append(temp_sentence.strip())
                                temp_sentence = sentence
                                if len(temp_sentence) > max_length:
                                    # Даже одно предложение слишком длинное - обрезаем по словам
                                    words = temp_sentence.split()
                                    temp_sentence = ""
                                    for word in words:
                                        if (
                                            len(temp_sentence) + len(word) + 1
                                            <= max_length
                                        ):
                                            temp_sentence += (
                                                (" " + word) if temp_sentence else word
                                            )
                                        else:
                                            if temp_sentence:
                                                parts.append(temp_sentence.strip())
                                            temp_sentence = word

                        if temp_sentence:
                            current_part = temp_sentence.strip()
                    else:
                        current_part = paragraph

        # Добавляем последнюю часть
        if current_part:
            parts.append(current_part)

        return parts if parts else [message[:max_length]]

    async def safe_reply(
        self, event: events.NewMessage.Event, message: str, max_retries: int = 3
    ):
        """
        Безопасная отправка ответа с обработкой FloodWait и автоматическим разбиением длинных сообщений.

        Args:
            event: Событие сообщения
            message: Текст сообщения для отправки
            max_retries: Максимальное количество попыток
        """
        chat_type = None
        if event.is_private:
            chat_type = "private"
        elif event.is_group:
            chat_type = "group"
        elif hasattr(event, "is_channel") and event.is_channel:
            chat_type = "channel"

        # Разбиваем длинные сообщения на части (Telegram лимит 4096 символов)
        message_parts = self._split_long_message(message, max_length=4000)

        if len(message_parts) > 1:
            logger.info(
                f"Message split into {len(message_parts)} parts (total length: {len(message)} chars)"
            )

        # Отправляем каждую часть
        for part_index, part in enumerate(message_parts):
            for attempt in range(max_retries):
                try:
                    await event.reply(part)
                    logger.debug(
                        f"Message part {part_index + 1}/{len(message_parts)} sent successfully (attempt {attempt + 1})"
                    )
                    break
                except FloodWaitError as e:
                    wait_seconds = e.seconds
                    logger.warning(
                        f"FloodWait error: need to wait {wait_seconds} seconds (attempt {attempt + 1}/{max_retries}, part {part_index + 1}/{len(message_parts)})"
                    )

                    # Записываем FloodWait в историю
                    if self.global_rate_limiter:
                        self.global_rate_limiter.record_flood_wait(
                            wait_seconds, chat_type
                        )

                    # Критическое предупреждение при длинном ожидании
                    if wait_seconds > 60:
                        logger.critical(
                            f"CRITICAL FloodWait: {wait_seconds} seconds! "
                            f"This indicates potential account risk."
                        )

                    # Ждем указанное время + небольшая задержка для безопасности
                    await asyncio.sleep(wait_seconds + 1)

                    # Если это последняя попытка, не продолжаем
                    if attempt == max_retries - 1:
                        logger.error(
                            f"Failed to send message part {part_index + 1} after {max_retries} attempts due to FloodWait"
                        )
                        return
                except Exception as e:
                    logger.error(
                        f"Error sending message part {part_index + 1}: {e}",
                        exc_info=True,
                    )
                    if attempt == max_retries - 1:
                        logger.error(
                            f"Failed to send message part {part_index + 1} after {max_retries} attempts"
                        )
                        return
                    # Небольшая задержка перед повторной попыткой
                    await asyncio.sleep(2**attempt)  # Экспоненциальная задержка

            # Небольшая задержка между частями для избежания rate limits
            if part_index < len(message_parts) - 1:
                await asyncio.sleep(0.5)

    async def send_summary_to_owner(self, summary_text: str) -> bool:
        """
        Отправить summary владельцу в Telegram.

        Args:
            summary_text: Текст summary для отправки

        Returns:
            True если отправка успешна, False иначе
        """
        if not self.config.meeting_summary.send_to_owner:
            logger.debug("Sending summary to owner is disabled")
            return False

        owner_username = self.config.meeting_summary.owner_username
        if not owner_username:
            logger.warning("Owner username not configured")
            return False

        try:
            # Получаем entity по username
            # Убираем @ если есть
            username_clean = owner_username.lstrip("@")
            entity = await self.client.get_entity(username_clean)

            # Разбиваем длинные сообщения
            message_parts = self._split_long_message(summary_text, max_length=4000)

            # Отправляем каждую часть
            for part_index, part in enumerate(message_parts):
                try:
                    await self.client.send_message(entity, part)
                    logger.info(
                        f"Summary sent to owner {owner_username} (part {part_index + 1}/{len(message_parts)})"
                    )

                    # Небольшая задержка между частями
                    if part_index < len(message_parts) - 1:
                        await asyncio.sleep(0.5)
                except FloodWaitError as e:
                    wait_seconds = e.seconds
                    logger.warning(
                        f"FloodWait when sending summary to owner: {wait_seconds} seconds"
                    )
                    await asyncio.sleep(wait_seconds + 1)
                    # Повторная попытка
                    await self.client.send_message(entity, part)
                    logger.info(
                        f"Summary sent to owner after FloodWait (part {part_index + 1}/{len(message_parts)})"
                    )
                except Exception as e:
                    logger.error(f"Error sending summary to owner: {e}", exc_info=True)
                    return False

            return True
        except ValueError as e:
            logger.error(f"Owner username not found: {owner_username}. Error: {e}")
            return False
        except Exception as e:
            logger.error(f"Error sending summary to owner: {e}", exc_info=True)
            return False

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
            # Команда /calendar или /events - список событий
            if message_text.startswith(("/calendar", "/events")):
                events_list = self.calendar.list_events(max_results=10)
                if events_list:
                    response = "📅 Предстоящие события:\n\n"
                    for evt in events_list:
                        response += self.calendar.format_event(evt) + "\n"
                else:
                    response = "📅 Нет предстоящих событий."
                await self.safe_reply(event, response)
                if self.global_rate_limiter:
                    self.global_rate_limiter.record_message()
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

                self.calendar.create_event(summary=summary, description=description)
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

        # Закрываем компоненты в правильном порядке
        # Сначала закрываем AI клиент и voice handler
        if self.ai_client:
            await self.ai_client.close()

        if self.voice_handler:
            await self.voice_handler.close()

        # Закрываем базу данных перед закрытием Telethon клиента
        # Это предотвращает блокировки SQLite при сохранении состояния сессии
        if self.memory:
            try:
                self.memory.close()
            except Exception as e:
                logger.warning(f"Error closing memory: {e}", exc_info=True)

        # Закрываем Telethon клиент в последнюю очередь
        # Telethon пытается сохранить состояние в SQLite сессию, поэтому важно
        # закрыть все другие соединения с SQLite перед этим
        if self.client:
            try:
                await self.client.disconnect()
            except Exception as e:
                # Игнорируем ошибки "database is locked" при закрытии
                # так как они не критичны и не влияют на работу приложения
                if "database is locked" in str(e).lower():
                    logger.warning(
                        f"Database locked during disconnect (non-critical): {e}"
                    )
                else:
                    logger.error(
                        f"Error disconnecting Telegram client: {e}", exc_info=True
                    )

        logger.info("Client stopped")
