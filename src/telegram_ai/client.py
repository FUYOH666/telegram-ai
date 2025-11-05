"""Telegram User Client через Telethon для личного аккаунта."""

import json
import logging
import time
from datetime import timedelta
from pathlib import Path
from typing import Optional

import httpx
from telethon import TelegramClient, events

from .ai_client import AIClient
from .calendar import GoogleCalendar
from .config import Config
from .intent_classifier import IntentClassifier
from .memory import Memory
from .rate_limiter import RateLimiter
from .sales_flow import SalesFlow, SalesStage
from .tools import Tools
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
        self.voice_handler: Optional[VoiceHandler] = None
        self.sales_flow: Optional[SalesFlow] = None
        self.intent_classifier: Optional[IntentClassifier] = None
        self.tools: Optional[Tools] = None

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

        # Intent Classifier (всегда включен)
        self.intent_classifier = IntentClassifier()
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
                            transcription_start = time.time()
                            logger.info(f"🎤 Voice message received from {sender.id}")
                            # Скачиваем аудио файл
                            audio_path = await event.message.download_media(file="./temp_audio/")
                            audio_path = Path(audio_path)

                            # Конвертируем .oga в .ogg если нужно (Telegram использует .oga, но ASR сервер не принимает)
                            if audio_path.suffix.lower() == ".oga":
                                # .oga это технически .ogg с Opus кодеком, переименовываем
                                ogg_path = audio_path.with_suffix(".ogg")
                                audio_path.rename(ogg_path)
                                audio_path = ogg_path
                                logger.debug(f"Renamed .oga to .ogg: {audio_path}")

                            # Транскрибируем
                            transcribed_text = await self.voice_handler.transcribe_voice(
                                audio_path, language="ru"
                            )
                            transcription_time = time.time() - transcription_start
                            logger.info(f"✅ Transcribed in {transcription_time:.2f}s: {transcribed_text[:100]}...")

                            # Используем транскрипт как текст сообщения
                            message_text = transcribed_text

                            # Удаляем временный файл
                            try:
                                audio_path.unlink()
                            except Exception as e:
                                logger.warning(f"Failed to delete temp audio file: {e}")

                        except httpx.TimeoutException as e:
                            logger.error(f"Timeout transcribing voice message: {e}", exc_info=True)
                            await event.reply("⏱️ Таймаут при распознавании голосового сообщения. Попробуйте позже или отправьте текстом.")
                            return
                        except httpx.ReadTimeout as e:
                            logger.error(f"Read timeout transcribing voice message: {e}", exc_info=True)
                            await event.reply("⏱️ Сервер ASR не отвечает вовремя. Попробуйте позже или отправьте текстом.")
                            return
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
                                self.memory.save_user_context(sender.id, json.dumps(context_dict))
                        except (json.JSONDecodeError, ValueError):
                            pass
                    else:
                        # Создаем новый контекст с именем
                        new_context = json.dumps({"name": user_full_name})
                        self.memory.save_user_context(sender.id, new_context)
                
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

                # Определяем, является ли это первым сообщением в разговоре
                is_first_message = len(context) <= 1  # Только системное сообщение или его нет

                # Классификация намерений
                user_context_data = self.memory.get_user_context(sender.id)
                current_intent = None
                if user_context_data:
                    try:
                        context_dict = json.loads(user_context_data)
                        current_intent = context_dict.get("intent")
                    except (json.JSONDecodeError, ValueError):
                        pass

                if self.intent_classifier:
                    detected_intent = self.intent_classifier.classify(
                        message_text, current_intent
                    )
                    if detected_intent.value != current_intent or not current_intent:
                        if detected_intent.value != current_intent:
                            logger.info(f"Intent detected: {current_intent} -> {detected_intent.value}")
                        
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

                # Работа со скриптом продаж
                max_response_length = None
                
                if self.sales_flow and self.sales_flow.enabled:
                    current_stage = self.sales_flow.get_stage(user_context_data)
                    
                    # Специальная логика: если пользователь пишет "привет" - всегда сбрасываем на GREETING
                    # (независимо от истории, это сигнал начала нового диалога)
                    message_lower = message_text.lower().strip()
                    greeting_keywords = ["привет", "здравствуй", "здравствуйте", "добрый", "начать"]
                    if any(keyword in message_lower for keyword in greeting_keywords):
                        if current_stage != SalesStage.GREETING:
                            logger.info(f"Greeting detected, resetting stage to GREETING (was {current_stage.value})")
                            current_stage = SalesStage.GREETING
                            user_context_data = self.sales_flow.update_stage(user_context_data, current_stage)
                            self.memory.save_user_context(sender.id, user_context_data)
                    
                    # Определяем переход на следующий этап
                    new_stage = self.sales_flow.detect_stage_transition(
                        message_text, current_stage, is_first_message=is_first_message
                    )
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

                    # Проверяем и запрашиваем недостающие слоты (только для Sales/Real Estate)
                    slot_prompt_addition = ""
                    if current_intent in ("SALES_AI", "REAL_ESTATE"):
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

                    # Получаем максимальную длину ответа для текущего этапа
                    max_response_length = self.sales_flow.get_stage_max_length(current_stage)
                    
                    # Модифицируем системный промпт для текущего этапа
                    stage_modifier = self.sales_flow.get_stage_prompt_modifier(current_stage)
                    if stage_modifier and context:
                        # Добавляем информацию о максимальной длине в модификатор
                        length_info = ""
                        if max_response_length:
                            length_info = f"\n\nМАКСИМАЛЬНАЯ ДЛИНА ОТВЕТА: {max_response_length} символов. Строго соблюдай это ограничение."
                        
                        # Добавляем модификатор как системное сообщение
                        modified_context = context.copy()
                        # Обновляем или добавляем системное сообщение
                        system_found = False
                        for msg in modified_context:
                            if msg.get("role") == "system":
                                full_modifier = stage_modifier + length_info + slot_prompt_addition
                                msg["content"] = full_modifier + "\n\n" + msg.get("content", "")
                                system_found = True
                                break
                        if not system_found:
                            full_modifier = stage_modifier + length_info + slot_prompt_addition
                            modified_context.insert(0, {"role": "system", "content": full_modifier})
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
                        logger.info(f"🔍 Web search triggered for query: {message_text[:100]}")
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
                                formatted_results = self.tools.web_search_tool.format_search_results(
                                    web_search_results
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
                            logger.error(f"Error performing web search: {e}", exc_info=True)

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
                    logger.info(f"🤖 Sending {len(context)} messages to AI server...")
                    response = await self.ai_client.get_response(
                        context,
                        max_response_length=max_response_length,
                        temperature=generation_params.get("temperature"),
                        max_tokens=generation_params.get("max_tokens"),
                        top_p=generation_params.get("top_p"),
                        frequency_penalty=generation_params.get("frequency_penalty"),
                        presence_penalty=generation_params.get("presence_penalty"),
                    )
                    ai_request_time = time.time() - ai_request_start
                    logger.info(f"✅ AI response received in {ai_request_time:.2f}s ({len(response)} chars): {response[:150]}...")
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
                            key_slots = ["goal", "purpose", "budget", "budget_band", "contact"]
                            filled_key_slots = [slot for slot in key_slots if slot in filled_slots]
                            
                            if len(filled_key_slots) >= 2:  # Минимум 2 ключевых слота
                                # Извлекаем имя из контекста или используем username
                                lead_name = username or filled_slots.get("name")
                                
                                # Получаем текущий stage для заметок
                                current_stage_for_notes = None
                                if user_context_data:
                                    try:
                                        context_dict = json.loads(user_context_data)
                                        current_stage_for_notes = context_dict.get("sales_stage", "unknown")
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
                                    logger.info(f"✅ Lead auto-saved for user_id={sender.id}")
                        except Exception as e:
                            logger.error(f"Error auto-saving lead: {e}", exc_info=True)

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
                                    description="Консультация с пользователем Telegram",
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

                except httpx.TimeoutException as e:
                    logger.error(f"Timeout connecting to AI server: {e}", exc_info=True)
                    await event.reply("⏱️ Таймаут подключения к AI серверу. Сервер недоступен или перегружен. Попробуйте позже.")
                except httpx.ReadTimeout as e:
                    logger.error(f"Read timeout from AI server: {e}", exc_info=True)
                    await event.reply("⏱️ AI сервер не успел сгенерировать ответ за отведенное время. Попробуйте позже или переформулируйте запрос.")
                except httpx.NetworkError as e:
                    logger.error(f"Network error: {e}", exc_info=True)
                    await event.reply("🌐 Ошибка сети при подключении к AI серверу. Проверьте интернет-соединение.")
                except httpx.HTTPStatusError as e:
                    logger.error(f"HTTP error from AI server: {e.response.status_code} - {e.response.text}", exc_info=True)
                    if e.response.status_code == 404:
                        user_error = "❌ Ошибка подключения к AI серверу. Проверьте настройки (URL и модель)."
                    elif e.response.status_code >= 500:
                        user_error = "🔧 Ошибка на стороне AI сервера. Попробуйте позже."
                    else:
                        user_error = f"❌ Ошибка AI сервера (код {e.response.status_code}). Попробуйте позже."
                    await event.reply(user_error)
                except Exception as e:
                    logger.error(f"Error getting AI response: {e}", exc_info=True)
                    error_msg = str(e)
                    # Более информативное сообщение об ошибке
                    if "404" in error_msg or "Not Found" in error_msg:
                        user_error = "❌ Ошибка подключения к AI серверу. Проверьте настройки."
                    elif "timeout" in error_msg.lower() or "Timeout" in error_msg:
                        user_error = "⏱️ Таймаут при генерации ответа. Попробуйте позже."
                    else:
                        user_error = f"❌ Ошибка при генерации ответа: {error_msg[:100]}"
                    
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

                self.calendar.create_event(
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

