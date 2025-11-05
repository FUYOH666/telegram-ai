"""Интеграция с Google Calendar API."""

import logging
import re
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import List, Optional, Tuple

import pytz
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

# Scopes для Google Calendar API
SCOPES = ["https://www.googleapis.com/auth/calendar"]


class GoogleCalendar:
    """Клиент для работы с Google Calendar API."""

    def __init__(
        self,
        credentials_path: str,
        token_path: str,
        auto_create_consultations: bool = True,
        default_consultation_duration_minutes: int = 60,
        available_slots: Optional[List[str]] = None,
        timezone_name: str = "Europe/Moscow",
    ):
        """
        Инициализация Google Calendar клиента.

        Args:
            credentials_path: Путь к файлу credentials.json
            token_path: Путь к файлу token.json для сохранения токена
            auto_create_consultations: Автоматически создавать встречи при запросах
            default_consultation_duration_minutes: Длительность консультации по умолчанию (минуты)
            available_slots: Доступные слоты времени (например, ["09:00", "10:00", "14:00"])
            timezone_name: Название часового пояса (например, "Europe/Moscow")
        """
        self.credentials_path = Path(credentials_path)
        self.token_path = Path(token_path)
        self.service = None
        self.auto_create_consultations = auto_create_consultations
        self.default_consultation_duration_minutes = default_consultation_duration_minutes
        self.available_slots = available_slots or [
            "09:00",
            "10:00",
            "11:00",
            "14:00",
            "15:00",
            "16:00",
        ]
        self.timezone_name = timezone_name
        try:
            self.timezone = pytz.timezone(timezone_name)
        except pytz.exceptions.UnknownTimeZoneError:
            logger.warning(f"Unknown timezone: {timezone_name}, using UTC")
            self.timezone = pytz.UTC

        # Создаем директорию для токенов если её нет
        self.token_path.parent.mkdir(parents=True, exist_ok=True)

        # Аутентификация
        self._authenticate()

    def _authenticate(self):
        """Аутентификация в Google Calendar API."""
        creds = None

        # Загружаем сохраненный токен если есть
        if self.token_path.exists():
            creds = Credentials.from_authorized_user_file(str(self.token_path), SCOPES)

        # Если нет валидных credentials, запрашиваем авторизацию
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not self.credentials_path.exists():
                    raise FileNotFoundError(
                        f"Credentials file not found: {self.credentials_path}. "
                        "Please download it from Google Cloud Console."
                    )

                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self.credentials_path), SCOPES
                )
                creds = flow.run_local_server(port=0)

            # Сохраняем credentials для следующего запуска
            with open(self.token_path, "w") as token:
                token.write(creds.to_json())
            logger.info(f"Google Calendar token saved to: {self.token_path}")

        self.service = build("calendar", "v3", credentials=creds)
        logger.info("✅ Google Calendar authenticated successfully")

    def create_event(
        self,
        summary: str,
        description: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        location: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> str:
        """
        Создать событие в календаре.

        Args:
            summary: Название события
            description: Описание события
            start_time: Время начала (по умолчанию через час)
            end_time: Время окончания (по умолчанию через 2 часа)
            location: Место проведения
            user_id: ID пользователя Telegram (для связи с событием)

        Returns:
            ID созданного события

        Raises:
            HttpError: При ошибке API
        """
        if start_time is None:
            # Дефолтное время: через час от текущего момента в локальной таймзоне
            now_local = datetime.now(self.timezone)
            start_time = now_local + timedelta(hours=1)
        else:
            # Если переданное время naive (без таймзоны), считаем его локальным временем
            if start_time.tzinfo is None:
                start_time = self.timezone.localize(start_time)

        if end_time is None:
            end_time = start_time + timedelta(minutes=self.default_consultation_duration_minutes)
        else:
            # Если переданное время naive (без таймзоны), считаем его локальным временем
            if end_time.tzinfo is None:
                end_time = self.timezone.localize(end_time)

        # Google Calendar API ожидает время в формате ISO 8601 с указанием таймзоны
        # Форматируем время: убираем таймзону из ISO строки, так как timeZone указывается отдельно
        start_iso = start_time.strftime("%Y-%m-%dT%H:%M:%S")
        end_iso = end_time.strftime("%Y-%m-%dT%H:%M:%S")

        event = {
            "summary": summary,
            "description": description,
            "start": {
                "dateTime": start_iso,
                "timeZone": self.timezone_name,
            },
            "end": {
                "dateTime": end_iso,
                "timeZone": self.timezone_name,
            },
        }

        if location:
            event["location"] = location
        
        # Добавляем user_id в описание для связи с пользователем
        if user_id is not None:
            if description:
                description = f"{description}\nuser_id:{user_id}"
            else:
                description = f"user_id:{user_id}"
        
        if description:
            event["description"] = description

        try:
            event = (
                self.service.events()
                .insert(calendarId="primary", body=event)
                .execute()
            )
            logger.info(f"Event created: {event.get('id')} - {summary} (user_id={user_id})")
            return event.get("id")
        except HttpError as e:
            logger.error(f"Error creating event: {e}")
            raise

    def list_events(
        self, max_results: int = 10, time_min: Optional[datetime] = None
    ) -> List[dict]:
        """
        Получить список предстоящих событий.

        Args:
            max_results: Максимальное количество событий
            time_min: Минимальное время (по умолчанию сейчас)

        Returns:
            Список событий
        """
        if time_min is None:
            time_min = datetime.now(self.timezone)
        else:
            # Если переданное время naive, локализуем его
            if time_min.tzinfo is None:
                time_min = self.timezone.localize(time_min)
            else:
                time_min = time_min.astimezone(self.timezone)

        try:
            # Конвертируем в UTC для Google Calendar API
            time_min_utc = time_min.astimezone(pytz.UTC)
            time_min_str = time_min_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
            
            events_result = (
                self.service.events()
                .list(
                    calendarId="primary",
                    timeMin=time_min_str,
                    maxResults=max_results,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )

            events = events_result.get("items", [])
            logger.debug(f"Retrieved {len(events)} events")
            return events

        except HttpError as e:
            logger.error(f"Error listing events: {e}")
            raise

    def format_event(self, event: dict) -> str:
        """
        Форматировать событие для вывода.

        Args:
            event: Событие из API

        Returns:
            Отформатированная строка
        """
        start = event["start"].get("dateTime", event["start"].get("date"))
        summary = event.get("summary", "No title")

        return f"📅 {summary} - {start}"

    def find_user_events(
        self, user_id: int, time_min: Optional[datetime] = None
    ) -> List[dict]:
        """
        Найти события пользователя.

        Args:
            user_id: ID пользователя Telegram
            time_min: Минимальное время (по умолчанию сейчас)

        Returns:
            Список событий пользователя
        """
        if time_min is None:
            time_min = datetime.now(self.timezone)
        else:
            # Если переданное время naive, локализуем его
            if time_min.tzinfo is None:
                time_min = self.timezone.localize(time_min)
            else:
                time_min = time_min.astimezone(self.timezone)

        try:
            # Конвертируем в UTC для Google Calendar API
            time_min_utc = time_min.astimezone(pytz.UTC)
            # Форматируем время для API (ISO 8601 с Z в конце)
            time_min_str = time_min_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
            
            # Получаем все события начиная с time_min
            events_result = (
                self.service.events()
                .list(
                    calendarId="primary",
                    timeMin=time_min_str,
                    maxResults=50,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )

            events = events_result.get("items", [])
            
            # Фильтруем по user_id в описании
            user_events = []
            user_id_str = f"user_id:{user_id}"
            
            for event in events:
                description = event.get("description", "")
                if user_id_str in description:
                    user_events.append(event)
            
            logger.debug(f"Found {len(user_events)} events for user_id={user_id}")
            return user_events

        except HttpError as e:
            logger.error(f"Error finding user events: {e}")
            raise

    def find_latest_user_event(self, user_id: int) -> Optional[dict]:
        """
        Найти последнее будущее событие пользователя.

        Args:
            user_id: ID пользователя Telegram

        Returns:
            Последнее событие пользователя или None
        """
        events = self.find_user_events(user_id)
        if not events:
            return None
        
        # События уже отсортированы по времени, берем первое (самое раннее)
        return events[0]

    def update_event(
        self,
        event_id: str,
        new_start_time: datetime,
        new_end_time: Optional[datetime] = None,
    ) -> dict:
        """
        Обновить событие (перенести на новое время).

        Args:
            event_id: ID события
            new_start_time: Новое время начала
            new_end_time: Новое время окончания (по умолчанию вычисляется из длительности)

        Returns:
            Обновленное событие

        Raises:
            HttpError: При ошибке API
        """
        try:
            # Получаем текущее событие
            event = (
                self.service.events()
                .get(calendarId="primary", eventId=event_id)
                .execute()
            )

            # Если переданное время naive, локализуем его
            if new_start_time.tzinfo is None:
                new_start_time = self.timezone.localize(new_start_time)
            else:
                new_start_time = new_start_time.astimezone(self.timezone)

            if new_end_time is None:
                # Вычисляем длительность из старого события
                old_start_str = event["start"].get("dateTime")
                old_end_str = event["end"].get("dateTime")
                if old_start_str and old_end_str:
                    old_start = datetime.fromisoformat(old_start_str.replace("Z", "+00:00"))
                    old_end = datetime.fromisoformat(old_end_str.replace("Z", "+00:00"))
                    duration = old_end - old_start
                    new_end_time = new_start_time + duration
                else:
                    new_end_time = new_start_time + timedelta(
                        minutes=self.default_consultation_duration_minutes
                    )
            else:
                if new_end_time.tzinfo is None:
                    new_end_time = self.timezone.localize(new_end_time)
                else:
                    new_end_time = new_end_time.astimezone(self.timezone)

            # Форматируем время для Google Calendar API
            start_iso = new_start_time.strftime("%Y-%m-%dT%H:%M:%S")
            end_iso = new_end_time.strftime("%Y-%m-%dT%H:%M:%S")

            # Обновляем время
            event["start"] = {
                "dateTime": start_iso,
                "timeZone": self.timezone_name,
            }
            event["end"] = {
                "dateTime": end_iso,
                "timeZone": self.timezone_name,
            }

            # Обновляем событие
            updated_event = (
                self.service.events()
                .update(calendarId="primary", eventId=event_id, body=event)
                .execute()
            )

            logger.info(
                f"Event updated: {event_id} - new time: {start_iso} "
                f"(local timezone: {self.timezone_name})"
            )
            return updated_event

        except HttpError as e:
            logger.error(f"Error updating event: {e}")
            raise

    def delete_event(self, event_id: str) -> bool:
        """
        Удалить событие.

        Args:
            event_id: ID события

        Returns:
            True если удалено успешно

        Raises:
            HttpError: При ошибке API
        """
        try:
            self.service.events().delete(
                calendarId="primary", eventId=event_id
            ).execute()
            logger.info(f"Event deleted: {event_id}")
            return True
        except HttpError as e:
            logger.error(f"Error deleting event: {e}")
            raise

    def check_time_conflict(
        self, start_time: datetime, end_time: datetime, exclude_event_id: Optional[str] = None
    ) -> Tuple[bool, List[dict]]:
        """
        Проверить конфликт времени с существующими событиями.

        Args:
            start_time: Время начала
            end_time: Время окончания
            exclude_event_id: ID события для исключения из проверки (при обновлении)

        Returns:
            Tuple (has_conflict, conflicting_events)
        """
        # Локализуем время если нужно
        if start_time.tzinfo is None:
            start_time = self.timezone.localize(start_time)
        else:
            start_time = start_time.astimezone(self.timezone)

        if end_time.tzinfo is None:
            end_time = self.timezone.localize(end_time)
        else:
            end_time = end_time.astimezone(self.timezone)

        try:
            # Получаем события на период +/- 1 день для проверки
            check_start = start_time - timedelta(days=1)
            check_end = end_time + timedelta(days=1)

            # Конвертируем в UTC для Google Calendar API
            check_start_utc = check_start.astimezone(pytz.UTC)
            check_end_utc = check_end.astimezone(pytz.UTC)
            
            events_result = (
                self.service.events()
                .list(
                    calendarId="primary",
                    timeMin=check_start_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    timeMax=check_end_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    maxResults=50,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )

            events = events_result.get("items", [])
            conflicting_events = []

            for event in events:
                # Пропускаем исключенное событие
                if exclude_event_id and event.get("id") == exclude_event_id:
                    continue

                event_start_str = event["start"].get("dateTime")
                event_end_str = event["end"].get("dateTime")

                if not event_start_str or not event_end_str:
                    continue

                # Парсим время события
                event_start = datetime.fromisoformat(event_start_str.replace("Z", "+00:00"))
                event_end = datetime.fromisoformat(event_end_str.replace("Z", "+00:00"))

                # Конвертируем в локальную таймзону для сравнения
                event_start = event_start.astimezone(self.timezone)
                event_end = event_end.astimezone(self.timezone)

                # Проверяем пересечение интервалов
                if not (end_time <= event_start or start_time >= event_end):
                    conflicting_events.append(event)

            has_conflict = len(conflicting_events) > 0
            if has_conflict:
                logger.debug(
                    f"Time conflict detected: {start_time} - {end_time} "
                    f"conflicts with {len(conflicting_events)} events"
                )

            return (has_conflict, conflicting_events)

        except HttpError as e:
            logger.error(f"Error checking time conflict: {e}")
            # В случае ошибки считаем что конфликта нет (fail-safe)
            return (False, [])

    def validate_event_time(
        self, start_time: datetime, end_time: datetime
    ) -> Tuple[bool, Optional[str]]:
        """
        Валидировать время события.

        Args:
            start_time: Время начала
            end_time: Время окончания

        Returns:
            Tuple (is_valid, error_message)
        """
        # Локализуем время если нужно
        if start_time.tzinfo is None:
            start_time = self.timezone.localize(start_time)
        else:
            start_time = start_time.astimezone(self.timezone)

        if end_time.tzinfo is None:
            end_time = self.timezone.localize(end_time)
        else:
            end_time = end_time.astimezone(self.timezone)

        now = datetime.now(self.timezone)

        # Проверка: время должно быть в будущем
        if start_time < now:
            return (False, "Время начала должно быть в будущем")

        # Проверка: end_time должно быть после start_time
        if end_time <= start_time:
            return (False, "Время окончания должно быть после времени начала")

        # Проверка: минимальный интервал (2 часа до начала)
        min_interval = timedelta(hours=2)
        if start_time < now + min_interval:
            hours = min_interval.seconds // 3600
            return (
                False,
                f"Встречу можно создать минимум за {hours} часа до начала",
            )

        # Проверка: рабочие часы (опционально, можно добавить в конфиг)
        # Пока пропускаем эту проверку

        return (True, None)

    def detect_consultation_request(self, message: str) -> bool:
        """
        Распознать запрос на консультацию в сообщении.

        Args:
            message: Текст сообщения

        Returns:
            True если обнаружен запрос на консультацию
        """
        message_lower = message.lower()

        consultation_keywords = [
            "консультация",
            "консультацию",
            "встреча",
            "встречу",
            "встретиться",
            "обсудить",
            "поговорить",
            "записаться",
            "запись",
            "когда можем",
            "хочу встретиться",
            "можно встретиться",
            "хочу консультацию",
        ]

        return any(keyword in message_lower for keyword in consultation_keywords)

    def detect_reschedule_request(self, message: str) -> Tuple[Optional[str], bool]:
        """
        Распознать запрос на перенос или отмену встречи.

        Args:
            message: Текст сообщения

        Returns:
            Tuple (request_type, is_request) где:
            - request_type: "reschedule" | "cancel" | None
            - is_request: True если это запрос на изменение встречи
        """
        message_lower = message.lower()

        reschedule_keywords = [
            "перенести",
            "перенос",
            "перенеси",
            "изменить",
            "изменение",
            "измени",
            "переместить",
            "перемести",
            "перенесем",
            "перенесём",
        ]

        cancel_keywords = [
            "отменить",
            "отмена",
            "отмены",
            "отмени",
            "удалить",
            "удалить встречу",
            "отменить встречу",
            "отменяем",
            "отменяем встречу",
        ]

        if any(keyword in message_lower for keyword in cancel_keywords):
            return ("cancel", True)
        elif any(keyword in message_lower for keyword in reschedule_keywords):
            return ("reschedule", True)

        return (None, False)

    def extract_time_from_message(
        self, message: str, reference_time: Optional[datetime] = None
    ) -> Optional[datetime]:
        """
        Извлечь время из сообщения.

        Args:
            message: Текст сообщения
            reference_time: Базовое время для вычисления относительных дат (по умолчанию текущее время)
                          Должно быть datetime с таймзоной или naive datetime (будет локализован)

        Returns:
            datetime объект с временем (naive datetime в локальной таймзоне) или None если время не найдено
        """
        message_lower = message.lower()
        
        # Используем переданное время или текущее время
        if reference_time is None:
            now = datetime.now(self.timezone)
        else:
            # Если переданное время naive, локализуем его
            if reference_time.tzinfo is None:
                now = self.timezone.localize(reference_time)
            else:
                # Конвертируем в локальную таймзону
                now = reference_time.astimezone(self.timezone)
        
        # Словарь дней недели (0=понедельник, 6=воскресенье)
        weekday_names = {
            "понедельник": 0, "понедельника": 0, "в понедельник": 0,
            "вторник": 1, "вторника": 1, "во вторник": 1,
            "среда": 2, "среды": 2, "в среду": 2,
            "четверг": 3, "четверга": 3, "в четверг": 3,
            "пятница": 4, "пятницы": 4, "в пятницу": 4,
            "суббота": 5, "субботы": 5, "в субботу": 5,
            "воскресенье": 6, "воскресенья": 6, "в воскресенье": 6,
        }
        
        # Проверяем дни недели
        target_weekday = None
        for weekday_word, weekday_num in weekday_names.items():
            if weekday_word in message_lower:
                target_weekday = weekday_num
                logger.debug(f"Found weekday: {weekday_word} (weekday={weekday_num})")
                break
        
        # Определяем целевую дату
        target_date = None
        days_offset = 0
        
        # Контекстные даты
        if "послезавтра" in message_lower:
            target_date = (now + timedelta(days=2)).date()
            days_offset = 2
        elif any(word in message_lower for word in ["завтра", "tomorrow"]):
            target_date = (now + timedelta(days=1)).date()
            days_offset = 1
        elif "сегодня" in message_lower:
            target_date = now.date()
            days_offset = 0
        elif target_weekday is not None:
            # Вычисляем ближайший день недели
            current_weekday = now.weekday()
            if target_weekday > current_weekday:
                days_offset = target_weekday - current_weekday
            elif target_weekday < current_weekday:
                days_offset = 7 - current_weekday + target_weekday
            else:
                # Сегодня этот день недели, но время может быть уже прошло - проверим позже
                days_offset = 0
            target_date = (now + timedelta(days=days_offset)).date()
        else:
            # Относительные даты
            relative_match = re.search(r"через\s+(\d+)\s+(день|дня|дней|недел|недели|недель|месяц|месяца|месяцев)", message_lower)
            if relative_match:
                num = int(relative_match.group(1))
                unit = relative_match.group(2)
                if "недел" in unit:
                    days_offset = num * 7
                elif "месяц" in unit:
                    days_offset = num * 30  # Приблизительно
                else:
                    days_offset = num
                target_date = (now + timedelta(days=days_offset)).date()
                logger.debug(f"Found relative date: через {num} {unit} (days_offset={days_offset})")
            else:
                # По умолчанию - сегодня
                target_date = now.date()
                days_offset = 0

        # Паттерны для поиска времени
        time_patterns = [
            r"(\d{1,2}):(\d{2})",  # "14:30", "9:00"
            r"в (\d{1,2}):(\d{2})",  # "в 14:30"
            r"(\d{1,2}) часов",  # "14 часов"
            r"в (\d{1,2}) часов",  # "в 14 часов"
        ]

        extracted_hour = None
        extracted_minute = 0

        # Парсинг времени
        for pattern in time_patterns:
            match = re.search(pattern, message_lower)
            if match:
                try:
                    if ":" in match.group(0):
                        # Формат "14:30"
                        extracted_hour = int(match.group(1))
                        extracted_minute = int(match.group(2))
                    else:
                        # Формат "14 часов"
                        extracted_hour = int(match.group(1))
                        extracted_minute = 0

                    if 0 <= extracted_hour < 24 and 0 <= extracted_minute < 60:
                        break
                except (ValueError, IndexError):
                    continue
        
        # Улучшенный парсинг времени (если не найдено число)
        if extracted_hour is None:
            if "полдень" in message_lower or "в полдень" in message_lower:
                extracted_hour = 12
                extracted_minute = 0
            elif "полночь" in message_lower or "в полночь" in message_lower:
                extracted_hour = 0
                extracted_minute = 0
            elif "утром" in message_lower or "утра" in message_lower:
                extracted_hour = 10  # Дефолтное утреннее время
                extracted_minute = 0
            elif "вечером" in message_lower or "вечера" in message_lower:
                extracted_hour = 18  # Дефолтное вечернее время
                extracted_minute = 0
            elif "днем" in message_lower or "дня" in message_lower:
                extracted_hour = 14  # Дефолтное дневное время
                extracted_minute = 0

        # Если время найдено, создаем datetime
        if extracted_hour is not None:
            extracted_time = self.timezone.localize(
                datetime.combine(target_date, time(extracted_hour, extracted_minute))
            )
            # Если время уже прошло сегодня (и не указана будущая дата), предлагаем на завтра
            if days_offset == 0 and extracted_time < now:
                extracted_time = self.timezone.localize(
                    datetime.combine(target_date + timedelta(days=1), time(extracted_hour, extracted_minute))
                )
                logger.debug(f"Time already passed today, moving to tomorrow")
            
            logger.debug(
                f"Extracted time from message: {extracted_time} "
                f"(date={target_date}, time={extracted_hour}:{extracted_minute:02d}, "
                f"local timezone: {self.timezone_name})"
            )
            return extracted_time.replace(tzinfo=None)  # Возвращаем naive datetime для совместимости
        
        # Если найдена дата, но время не указано - используем первое доступное время (10:00)
        if target_date != now.date() or days_offset > 0:
            default_hour = 10
            default_minute = 0
            extracted_time = self.timezone.localize(
                datetime.combine(target_date, time(default_hour, default_minute))
            )
            logger.debug(
                f"Found date without time, using default {default_hour}:{default_minute:02d} "
                f"for date {target_date}"
            )
            return extracted_time.replace(tzinfo=None)  # Возвращаем naive datetime для совместимости

        return None

    def suggest_available_slots(self, days_ahead: int = 7) -> List[str]:
        """
        Предложить доступные слоты времени.

        Args:
            days_ahead: На сколько дней вперед искать слоты

        Returns:
            Список строк с предложениями слотов времени
        """
        suggestions = []
        now = datetime.now()
        today = now.date()

        # Получаем существующие события на ближайшие дни
        existing_events = self.list_events(
            max_results=50, time_min=datetime.combine(today, time.min)
        )

        # Создаем множество занятых временных слотов
        busy_slots = set()
        for event in existing_events:
            start_str = event["start"].get("dateTime")
            if start_str:
                event_start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                busy_slots.add((event_start.date(), event_start.hour))

        # Предлагаем слоты на ближайшие дни
        for day_offset in range(days_ahead):
            check_date = today + timedelta(days=day_offset)
            date_label = "сегодня" if day_offset == 0 else (
                "завтра" if day_offset == 1 else check_date.strftime("%d.%m")
            )

            for slot_time in self.available_slots:
                hour, minute = map(int, slot_time.split(":"))
                slot_datetime = datetime.combine(check_date, time(hour, minute))

                # Пропускаем если время уже прошло сегодня
                if day_offset == 0 and slot_datetime < now:
                    continue

                # Пропускаем если слот занят
                if (check_date, hour) in busy_slots:
                    continue

                suggestions.append(f"{date_label} в {slot_time}")

                # Ограничиваем количество предложений
                if len(suggestions) >= 5:
                    return suggestions

        return suggestions if suggestions else ["Завтра в 10:00", "Завтра в 14:00"]


