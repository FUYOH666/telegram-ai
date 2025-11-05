"""Интеграция с Google Calendar API."""

import logging
import re
from datetime import datetime, timedelta, time
from pathlib import Path
from typing import List, Optional

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
    ):
        """
        Инициализация Google Calendar клиента.

        Args:
            credentials_path: Путь к файлу credentials.json
            token_path: Путь к файлу token.json для сохранения токена
            auto_create_consultations: Автоматически создавать встречи при запросах
            default_consultation_duration_minutes: Длительность консультации по умолчанию (минуты)
            available_slots: Доступные слоты времени (например, ["09:00", "10:00", "14:00"])
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
    ) -> str:
        """
        Создать событие в календаре.

        Args:
            summary: Название события
            description: Описание события
            start_time: Время начала (по умолчанию через час)
            end_time: Время окончания (по умолчанию через 2 часа)
            location: Место проведения

        Returns:
            ID созданного события

        Raises:
            HttpError: При ошибке API
        """
        if start_time is None:
            start_time = datetime.utcnow() + timedelta(hours=1)

        if end_time is None:
            end_time = start_time + timedelta(hours=1)

        event = {
            "summary": summary,
            "description": description,
            "start": {
                "dateTime": start_time.isoformat() + "Z",
                "timeZone": "UTC",
            },
            "end": {
                "dateTime": end_time.isoformat() + "Z",
                "timeZone": "UTC",
            },
        }

        if location:
            event["location"] = location

        try:
            event = (
                self.service.events()
                .insert(calendarId="primary", body=event)
                .execute()
            )
            logger.info(f"Event created: {event.get('id')} - {summary}")
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
            time_min = datetime.utcnow()

        try:
            events_result = (
                self.service.events()
                .list(
                    calendarId="primary",
                    timeMin=time_min.isoformat() + "Z",
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

    def extract_time_from_message(self, message: str) -> Optional[datetime]:
        """
        Извлечь время из сообщения.

        Args:
            message: Текст сообщения

        Returns:
            datetime объект с временем или None если время не найдено
        """
        # Паттерны для поиска времени
        time_patterns = [
            r"(\d{1,2}):(\d{2})",  # "14:30", "9:00"
            r"в (\d{1,2}):(\d{2})",  # "в 14:30"
            r"(\d{1,2}) часов",  # "14 часов"
            r"в (\d{1,2}) часов",  # "в 14 часов"
        ]

        now = datetime.now()
        today = now.date()

        for pattern in time_patterns:
            match = re.search(pattern, message.lower())
            if match:
                try:
                    if ":" in match.group(0):
                        # Формат "14:30"
                        hour = int(match.group(1))
                        minute = int(match.group(2))
                    else:
                        # Формат "14 часов"
                        hour = int(match.group(1))
                        minute = 0

                    if 0 <= hour < 24 and 0 <= minute < 60:
                        extracted_time = datetime.combine(today, time(hour, minute))
                        # Если время уже прошло сегодня, предлагаем на завтра
                        if extracted_time < now:
                            extracted_time += timedelta(days=1)
                        return extracted_time
                except (ValueError, IndexError):
                    continue

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


