"""Интеграция с Google Calendar API."""

import logging
from datetime import datetime, timedelta
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

    def __init__(self, credentials_path: str, token_path: str):
        """
        Инициализация Google Calendar клиента.

        Args:
            credentials_path: Путь к файлу credentials.json
            token_path: Путь к файлу token.json для сохранения токена
        """
        self.credentials_path = Path(credentials_path)
        self.token_path = Path(token_path)
        self.service = None

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

        self.service = build("calendar", "v3", credentials=creds)
        logger.info("Google Calendar authenticated successfully")

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

