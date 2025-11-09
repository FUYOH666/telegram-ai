"""Скрипт продаж (Sales Flow) с state machine и управлением слотами."""

import json
import logging
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SalesStage(str, Enum):
    """Этапы скрипта продаж."""

    GREETING = "greeting"
    NEEDS_DISCOVERY = "needs_discovery"
    PRESENTATION = "presentation"
    OBJECTIONS = "objections"
    CONSULTATION_OFFER = "consultation_offer"
    SCHEDULING = "scheduling"
    SUMMARY = "summary"


class ObjectionType(str, Enum):
    """Типы возражений клиентов."""

    PRICE = "price"  # Цена/бюджет
    TIMING = "timing"  # Время/сроки
    NEED = "need"  # Необходимость/потребность
    TRUST = "trust"  # Доверие/репутация
    COMPETITOR = "competitor"  # Конкуренты
    OTHER = "other"  # Другие возражения


class SalesFlow:
    """Управление скриптом продаж с state machine и слотами."""

    # Обязательные слоты для Sales (AI-проекты)
    SALES_REQUIRED_SLOTS = {
        # Базовые слоты (приоритет 1)
        "client_name",  # Имя клиента
        "company_name",  # Название компании
        "contact",  # Контактная информация
        "company_size",  # Размер компании (количество сотрудников или категория)
        # Слоты о бизнесе (приоритет 2)
        "company_domain",  # Сфера деятельности компании (расширяем domain)
        "main_problems",  # Основные проблемы бизнеса
        "time_consuming_tasks",  # Задачи, отнимающие много времени у сотрудников
        "process_volume",  # Объем операций/обработки
        "employees_involved",  # Количество сотрудников, вовлеченных в процесс
        "current_time_cost",  # Текущие временные затраты
        "error_rate",  # Текущий уровень ошибок/переделок
        "business_revenue",  # Оборот компании
        "current_cost",  # Текущие затраты на процесс
        # Слоты о проекте (приоритет 3)
        "goal",  # Цель проекта
        "deadline",  # Сроки
        "budget_band",  # Бюджет/диапазон
        "data_access",  # Доступ к данным
        "success_metric",  # Критерий успеха
    }

    # Обязательные слоты для Real Estate
    REAL_ESTATE_REQUIRED_SLOTS = {
        "purpose",  # Цель (жить/инвест/аренда)
        "budget",  # Бюджет (USD/THB)
        "districts",  # Районы
        "property_type",  # Тип (кондо/вилла/земля)
        "beds",  # Спальни
        "sea_view",  # Море/вид
        "distance_to_sea",  # Расстояние до моря
        "title_status",  # Статус права (чанот/квота)
        "timeline",  # Сроки
        "contact",  # Контакт
    }

    # Промпты для запроса слотов Sales (открытые вопросы, естественный тон)
    SALES_SLOT_PROMPTS = {
        # Базовые (приоритет 1)
        "client_name": "Как тебя зовут?",
        "company_name": "Расскажи, какая у тебя компания? Как она называется?",
        "contact": "Как с тобой удобнее связаться? Можешь оставить телефон или email?",
        "company_size": "Сколько примерно сотрудников у вас в компании? Или это малый/средний/крупный бизнес?",
        # О бизнесе (приоритет 2)
        "company_domain": "В какой сфере работает твоя компания? Чем занимаетесь?",
        "main_problems": "Какие основные проблемы или задачи у вас сейчас? Что больше всего беспокоит?",
        "time_consuming_tasks": "Какие задачи отнимают больше всего времени у твоих сотрудников? Что можно автоматизировать?",
        "process_volume": "А сколько примерно операций у вас в день? Например, сколько документов обрабатываете, звонков принимаете, или запросов обрабатываете?",
        "employees_involved": "Сколько сотрудников обычно занимаются этой задачей?",
        "current_time_cost": "Сколько примерно времени в неделю или месяц уходит на эту задачу?",
        "error_rate": "А как часто бывают ошибки? Приходится ли переделывать работу?",
        "business_revenue": "Можешь поделиться примерным оборотом компании? Это поможет понять масштаб задачи.",
        "current_cost": "Сколько примерно сейчас уходит на этот процесс? Зарплаты сотрудников или какие-то инструменты?",
        # О проекте (приоритет 3)
        "goal": "Расскажи, какую главную задачу хочешь решить с помощью AI?",
        "deadline": "Есть ли у тебя ориентир по срокам? Когда хотелось бы увидеть результат?",
        "budget_band": "Рассматривал ли ты, какой бюджет готов вложить? Хотя бы порядок — диапазоном или разовый?",
        "data_access": "А с данными как? Есть ли доступ к ним или нужны интеграции?",
        "success_metric": "Как поймёшь, что проект успешен? Что будет главным показателем?",
        # Для обратной совместимости (старое поле domain)
        "domain": "В какой сфере работает твоя компания? Медицина, финансы, ритейл или что-то другое?",
    }

    # Промпты для запроса слотов Real Estate (открытые вопросы, естественный тон)
    REAL_ESTATE_SLOT_PROMPTS = {
        "purpose": "Расскажи, для чего ищешь недвижимость? Для себя жить, инвестировать или сдавать?",
        "budget": "Какой у тебя ориентир по бюджету? В THB или USD, можно диапазоном.",
        "districts": "Какие районы тебе интересны? Лаян, Найтон, Банг-Тао или другие?",
        "property_type": "Что больше нравится — кондо, вилла или земля? И сколько примерно спален нужно?",
        "beds": "Сколько спален планируешь?",
        "sea_view": "Важно ли видеть море из окна?",
        "distance_to_sea": "Какое расстояние до моря для тебя комфортно?",
        "title_status": "А как с правами? Чанот, квота кондо или аренда подходит?",
        "timeline": "Когда примерно планируешь покупку или просмотр?",
        "contact": "Как с тобой удобнее связаться?",
    }

    # Ключевые слова для переходов между этапами
    GREETING_KEYWORDS = [
        "привет",
        "здравствуй",
        "добрый",
        "здравствуйте",
        "начать",
        # Английские приветствия
        "hi",
        "hello",
        "hey",
        "good morning",
        "good afternoon",
        "good evening",
    ]
    NEEDS_KEYWORDS = [
        "нужно",
        "хочу",
        "интересно",
        "проблема",
        "задача",
        "помощь",
        "автоматизация",
    ]
    PRESENTATION_KEYWORDS = [
        "расскажи",
        "что",
        "как",
        "услуги",
        "решения",
        "возможности",
    ]
    OBJECTIONS_KEYWORDS = [
        "дорого",
        "не нужно",
        "не интересно",
        "позже",
        "думаю",
        "сомневаюсь",
    ]
    CONSULTATION_KEYWORDS = [
        "консультация",
        "встреча",
        "обсудить",
        "поговорить",
        "узнать больше",
    ]
    SCHEDULING_KEYWORDS = [
        "когда",
        "время",
        "договориться",
        "записаться",
        "встретиться",
    ]

    # Ключевые слова для классификации типов возражений
    PRICE_KEYWORDS = [
        "дорого", "дорогой", "дорогая", "дорогие",
        "бюджет", "стоимость", "цена", "стоит",
        "дешевле", "дешево", "не по карману",
        "expensive", "cost", "price", "budget",
        "too much", "afford",
    ]
    TIMING_KEYWORDS = [
        "позже", "не сейчас", "не время", "некогда",
        "потом", "в другой раз", "сейчас не готов",
        "later", "not now", "not ready", "timing",
        "too early", "too late",
    ]
    NEED_KEYWORDS = [
        "не нужно", "не нужен", "не нужна", "не нужны",
        "не интересно", "не интересен", "не интересна",
        "не требуется", "не требуется", "не актуально",
        "don't need", "not needed", "not interested",
        "not relevant", "not necessary",
    ]
    TRUST_KEYWORDS = [
        "сомневаюсь", "не уверен", "не уверена",
        "не доверяю", "не знаю", "не знаком",
        "риск", "опасно", "ненадежно",
        "doubt", "not sure", "don't trust",
        "risk", "unsure", "uncertain",
    ]
    COMPETITOR_KEYWORDS = [
        "конкурент", "конкуренты", "другая компания",
        "уже есть", "используем другое",
        "competitor", "other company", "already have",
        "using something else",
    ]

    # Шаблоны ответов на возражения
    OBJECTION_RESPONSE_TEMPLATES = {
        ObjectionType.PRICE: {
            "approach": "Понимаю, бюджет — важный фактор. Давайте посмотрим на ценность решения.",
            "examples": [
                "Понимаю, бюджет — важный фактор. Давайте посчитаем: если AI сэкономит 10 часов в неделю — сколько это стоит в деньгах?",
                "Я ценю вашу озабоченность по бюджету. Можем обсудить поэтапное внедрение — начать с малого и масштабировать по мере получения результатов.",
                "Давайте посмотрим на ROI: сколько сейчас уходит на ручную работу? AI может сократить эти затраты на 70-80%.",
            ],
        },
        ObjectionType.TIMING: {
            "approach": "Понимаю, сейчас может быть не самое подходящее время. Давайте обсудим оптимальные сроки.",
            "examples": [
                "Понимаю, сейчас может быть не самое подходящее время. Когда вы планируете вернуться к этому вопросу?",
                "Хорошо, давайте зафиксируем вашу задачу. Когда будете готовы обсудить — напишите, я подготовлю предложение.",
                "Ничего страшного. Можем просто созвониться на 15 минут, чтобы я понял вашу задачу и подготовил решение к нужному моменту.",
            ],
        },
        ObjectionType.NEED: {
            "approach": "Понимаю вашу точку зрения. Давайте разберемся, действительно ли это решение вам нужно.",
            "examples": [
                "Понимаю вашу точку зрения. Расскажите, какие задачи сейчас отнимают больше всего времени? Возможно, есть что-то, что можно автоматизировать.",
                "Хорошо, давайте разберемся. Какие процессы в вашей компании сейчас самые трудоемкие? Может быть, там есть место для оптимизации.",
                "Понятно. А если бы у вас была возможность сократить время на рутинные задачи на 70% — это было бы полезно?",
            ],
        },
        ObjectionType.TRUST: {
            "approach": "Понимаю ваши сомнения. Давайте обсудим, что поможет вам почувствовать уверенность.",
            "examples": [
                "Понимаю ваши сомнения. Могу показать примеры похожих проектов, которые мы реализовали. Это поможет понять, как это работает.",
                "Я ценю вашу осторожность. Давайте начнем с небольшого пилотного проекта — это позволит оценить результат без больших рисков.",
                "Понимаю, важно быть уверенным в решении. Можем обсудить ваши конкретные опасения — разберемся вместе.",
            ],
        },
        ObjectionType.COMPETITOR: {
            "approach": "Понимаю, вы рассматриваете разные варианты. Давайте обсудим, что важно для вас в решении.",
            "examples": [
                "Понимаю, вы рассматриваете разные варианты. Что для вас важнее всего в решении? Может быть, я смогу предложить что-то, что лучше подходит под ваши задачи.",
                "Хорошо, давайте сравним. Какие критерии для вас самые важные? Цена, качество, скорость внедрения, поддержка?",
                "Понятно. А что именно вас не устраивает в текущем решении? Может быть, есть конкретные задачи, которые оно не покрывает?",
            ],
        },
        ObjectionType.OTHER: {
            "approach": "Понимаю вашу озабоченность. Давайте разберемся вместе, как можно решить эту задачу.",
            "examples": [
                "Понимаю вашу озабоченность. Расскажите подробнее, что именно вас беспокоит? Давайте разберемся вместе.",
                "Хорошо, давайте обсудим. Что конкретно вызывает сомнения? Может быть, я смогу помочь разобраться.",
                "Понятно. Давайте разберемся по пунктам — что именно вас смущает? Вместе найдем решение.",
            ],
        },
    }

    def __init__(self, enabled: bool = True, slot_extractor=None, event_bus=None, ai_client=None):
        """
        Инициализация SalesFlow.

        Args:
            enabled: Включить скрипт продаж
            slot_extractor: Экземпляр SlotExtractor для автоматического извлечения слотов
            event_bus: Экземпляр EventBus для публикации событий (опционально)
            ai_client: Экземпляр AIClient для LLM-based классификации возражений (опционально)
        """
        self.enabled = enabled
        self.slot_extractor = slot_extractor
        self.event_bus = event_bus
        self.ai_client = ai_client
        
        # Подписываемся на события если event_bus доступен
        if self.event_bus:
            from .events import (
                EVENT_SLOT_FOUND,
                EVENT_SLOT_CORRECTION,
                EVENT_INTENT_CHANGED,
            )
            
            self.event_bus.subscribe(EVENT_SLOT_FOUND, self._handle_slot_found)
            self.event_bus.subscribe(EVENT_SLOT_CORRECTION, self._handle_slot_correction)
            self.event_bus.subscribe(EVENT_INTENT_CHANGED, self._handle_intent_changed)
        
        logger.info(f"SalesFlow initialized: enabled={enabled}, event_bus={'enabled' if event_bus else 'disabled'}, ai_client={'enabled' if ai_client else 'disabled'}")

    def get_stage(self, context_data: Optional[str]) -> SalesStage:
        """
        Получить текущий этап из контекста.

        Args:
            context_data: JSON строка с контекстом пользователя

        Returns:
            Текущий этап скрипта продаж
        """
        if not context_data:
            return SalesStage.GREETING

        try:
            data = json.loads(context_data)
            stage_str = data.get("sales_stage", "greeting")
            return SalesStage(stage_str)
        except (json.JSONDecodeError, ValueError):
            return SalesStage.GREETING

    def update_stage(self, context_data: Optional[str], new_stage: SalesStage) -> str:
        """
        Обновить этап в контексте.

        Args:
            context_data: Текущий JSON контекст
            new_stage: Новый этап

        Returns:
            Обновленный JSON контекст
        """
        if context_data:
            try:
                data = json.loads(context_data)
            except json.JSONDecodeError:
                data = {}
        else:
            data = {}

        data["sales_stage"] = new_stage.value
        # Обновляем missing_slots если есть slots
        if "slots" in data:
            self._update_missing_slots(data)
        return json.dumps(data)

    def detect_stage_transition(
        self, message: str, current_stage: SalesStage, is_first_message: bool = False
    ) -> Optional[SalesStage]:
        """
        Определить переход на следующий этап на основе сообщения.
        
        ВАЖНО: Переходы только ВПЕРЕД, никогда назад. Это гарантирует прогресс в диалоге
        и предотвращает повторные вопросы и "откаты" на предыдущие этапы.

        Args:
            message: Текст сообщения пользователя
            current_stage: Текущий этап
            is_first_message: Является ли это первым сообщением в разговоре

        Returns:
            Новый этап или None если переход не требуется
        """
        if not self.enabled:
            return None

        message_lower = message.lower()

        # Если это первое сообщение и оно похоже на приветствие - принудительно ставим GREETING
        if is_first_message and any(
            keyword in message_lower for keyword in self.GREETING_KEYWORDS
        ):
            return SalesStage.GREETING

        # Логика переходов - ТОЛЬКО ВПЕРЕД, НИКОГДА НАЗАД
        # Это гарантирует, что бот не будет "откатываться" на предыдущие этапы
        # и не будет задавать повторные вопросы
        
        if current_stage == SalesStage.GREETING:
            # Из GREETING можно перейти только в NEEDS_DISCOVERY или PRESENTATION
            if any(keyword in message_lower for keyword in self.NEEDS_KEYWORDS):
                return SalesStage.NEEDS_DISCOVERY
            if any(keyword in message_lower for keyword in self.PRESENTATION_KEYWORDS):
                return SalesStage.PRESENTATION

        elif current_stage == SalesStage.NEEDS_DISCOVERY:
            # Из NEEDS_DISCOVERY можно перейти только в PRESENTATION, OBJECTIONS или CONSULTATION_OFFER
            # НЕ возвращаемся в GREETING, даже если есть слова приветствия
            if any(keyword in message_lower for keyword in self.PRESENTATION_KEYWORDS):
                return SalesStage.PRESENTATION
            if any(keyword in message_lower for keyword in self.OBJECTIONS_KEYWORDS):
                return SalesStage.OBJECTIONS
            # Если пользователь явно просит консультацию - переходим сразу к предложению
            if any(keyword in message_lower for keyword in self.CONSULTATION_KEYWORDS):
                return SalesStage.CONSULTATION_OFFER

        elif current_stage == SalesStage.PRESENTATION:
            # Из PRESENTATION можно перейти только в OBJECTIONS, CONSULTATION_OFFER или SCHEDULING
            # НЕ возвращаемся в NEEDS_DISCOVERY, даже если есть слова "нужно", "хочу", "проблема"
            # Эти слова могут быть частью вопроса о решении, а не запросом на сбор информации
            if any(keyword in message_lower for keyword in self.OBJECTIONS_KEYWORDS):
                return SalesStage.OBJECTIONS
            if any(keyword in message_lower for keyword in self.CONSULTATION_KEYWORDS):
                return SalesStage.CONSULTATION_OFFER
            # Если пользователь спрашивает про время - переходим к согласованию
            if any(keyword in message_lower for keyword in self.SCHEDULING_KEYWORDS):
                return SalesStage.SCHEDULING

        elif current_stage == SalesStage.OBJECTIONS:
            # Из OBJECTIONS можно перейти только в CONSULTATION_OFFER или SCHEDULING
            if any(keyword in message_lower for keyword in self.CONSULTATION_KEYWORDS):
                return SalesStage.CONSULTATION_OFFER
            # Если пользователь спрашивает про время - переходим к согласованию
            if any(keyword in message_lower for keyword in self.SCHEDULING_KEYWORDS):
                return SalesStage.SCHEDULING

        elif current_stage == SalesStage.CONSULTATION_OFFER:
            # Из CONSULTATION_OFFER можно перейти только в SCHEDULING
            if any(keyword in message_lower for keyword in self.SCHEDULING_KEYWORDS):
                return SalesStage.SCHEDULING

        # После согласования времени (SCHEDULING) переход на SUMMARY обрабатывается отдельно
        # через проверку should_transition_to_summary() в client.py

        return None

    def get_stage_prompt_modifier(self, stage: SalesStage) -> str:
        """
        Получить модификатор системного промпта для этапа.

        Args:
            stage: Этап скрипта продаж

        Returns:
            Дополнительный текст для системного промпта
        """
        modifiers = {
            SalesStage.GREETING: (
                "КРИТИЧЕСКИ ВАЖНО: Сейчас этап приветствия. Твой ответ должен быть КОРОТКИМ - максимум 1-2 предложения (до 200 символов).\n\n"
                "Правила представления:\n"
                "- Представься как Александр из Scanovich.ai ТОЛЬКО если еще не представлялся этому пользователю (проверь флаг introduced в контексте)\n"
                "- Если уже представлялся - просто поприветствуй дружелюбно, без повторения представления\n"
                "- ВАЖНО: При первом знакомстве (когда флаг introduced отсутствует или False) ОБЯЗАТЕЛЬНО спроси имя пользователя вежливо\n\n"
                "Примеры хороших ответов (первое знакомство):\n"
                "- 'Привет! Я Александр из Scanovich.ai. Как вас зовут?'\n"
                "- 'Здравствуйте! Меня зовут Александр. А как вас зовут?'\n"
                "- 'Привет! Я Александр. Очень приятно познакомиться! Как вас зовут?'\n\n"
                "Примеры хороших ответов (уже знакомы):\n"
                "- 'Привет! Чем могу помочь?'\n"
                "- 'Привет! Как дела?'\n"
                "- Если знаешь имя: 'Привет, [имя]! Чем могу помочь?'\n\n"
                "Пример плохого ответа: длинное развернутое сообщение с подробным описанием компании или проектов.\n\n"
                "Дополнительные правила:\n"
                "- Если знаешь имя пользователя (из контекста) — используй его, но не в каждом сообщении\n"
                "- При первом знакомстве ВСЕГДА спроси имя вежливо\n"
                "- Спроси чем можешь помочь, но НЕ пиши длинные сообщения\n"
                "- На короткие сообщения отвечай коротко\n"
                "- ЗАПРЕЩЕНО упоминать услуги, проекты или любые детали до того, как пользователь спросит"
            ),
            SalesStage.NEEDS_DISCOVERY: (
                "Сейчас этап выявления потребностей. Используй консультативный подход для сбора информации о клиенте.\n\n"
                "Правила:\n"
                "- Задавай открытые вопросы вместо допроса ('Расскажи, какая у тебя ситуация?' вместо 'Укажи проблему')\n"
                "- Задавай по одному вопросу за раз, не перегружай пользователя\n"
                "- Проявляй эмпатию — покажи, что понимаешь проблему ('Понимаю, это действительно...')\n"
                "- Отзеркаливай значимые детали из ответов пользователя\n"
                "- Если знаешь имя пользователя — используй его периодически (не в каждом сообщении)\n"
                "- Собирай информацию естественно в процессе диалога: сначала базовые данные (имя, компания), потом о бизнесе (проблемы, метрики), затем о проекте\n"
                "- Если клиент не готов делиться некоторой информацией (например, финансовыми показателями) — не дави, но объясни, что это поможет лучше понять масштаб задачи\n"
                "- Отвечай ПОЛНОСТЬЮ и развернуто, раскрывай все аспекты, не обрезай ответ\n\n"
                "Правила уточнения при низкой уверенности:\n"
                "- Если уверенность в извлеченной информации < 0.6 — задай один короткий уточняющий вопрос\n"
                "- Если уверенность 0.6-0.8 — мягко подтверди ('Верно ли, что...?' или 'Правильно ли я понял, что...?')\n"
                "- Если уверенность ≥ 0.8 — используй информацию без уточнений\n"
                "- Не задавай несколько уточняющих вопросов подряд — один вопрос за раз\n\n"
                "Примеры естественных реакций:\n"
                "- 'Окей, понял. А расскажи, какая у вас сейчас ситуация с [проблема]?'\n"
                "- 'Понимаю, это боль многих компаний. Что чаще всего вызывает [проблема]?'\n"
                "- 'Спасибо за информацию! А можешь поделиться примерным оборотом компании? Это поможет лучше понять масштаб задачи.'\n"
                "- 'Верно ли, что у вас около 50 сотрудников?' (мягкое подтверждение)\n"
                "- 'Уточни, пожалуйста, какая именно задача отнимает больше всего времени?' (уточнение при низкой уверенности)\n\n"
                "ВАЖНО: Отвечай развернуто, раскрывай все детали, не обрезай ответ многоточием."
            ),
            SalesStage.PRESENTATION: (
                "Сейчас этап презентации услуг. Делай это естественно, как доверенный партнёр.\n\n"
                "Правила:\n"
                "- Сначала ссылайся на то, что сказал клиент ('Вы упоминали, что у вас...')\n"
                "- Покажи, как именно твоё решение решает его конкретную задачу\n"
                "- Говори от первого лица ('я разрабатываю', 'я внедрял')\n"
                "- Избегай общей маркетинговой болтовни — фокус на релевантности\n"
                "- Если запрос вне зоны твоих услуг — честно скажи ('Честно говоря, это больше задача для...')\n"
                "- Отвечай ПОЛНОСТЬЮ и развернуто, раскрывай все возможности и детали решения, не обрезай ответ\n"
                "- После презентации решения, если собрано достаточно информации (имя, компания, проблема, цель) или после 2-3 сообщений на этом этапе, естественно предложи встречу для обсуждения деталей\n\n"
                "Примеры естественных реакций:\n"
                "- 'Вы упоминали, что у вас слишком много ручной работы в отчётах — наше решение автоматизирует сбор данных и тем самым снимет эту нагрузку'\n"
                "- 'Я недавно делал похожий проект для [домен]. Там удалось сократить время обработки на 70%. Рассказать подробнее?'\n"
                "- После объяснения решения: 'Мне кажется, мы хорошо разобрались в вашей задаче. Предлагаю созвониться на 15 минут, чтобы обсудить детали и убедиться, что всё учтено. Когда удобно?'\n\n"
                "ВАЖНО: Отвечай развернуто, раскрывай все аспекты решения, не обрезай ответ многоточием. После презентации активно предлагай встречу."
            ),
            SalesStage.OBJECTIONS: (
                "Сейчас этап работы с возражениями. Работай как консультант, не как продавец.\n\n"
                "Правила:\n"
                "- НЕ спорь с клиентом — разбирай сомнения вместе с ним\n"
                "- Проявляй понимание и эмпатию ('Я ценю вашу озабоченность...')\n"
                "- Вставай на сторону клиента — пытайся найти компромисс\n"
                "- Предлагай варианты решения проблемы ('Давайте посмотрим, как можно...')\n\n"
                "Примеры естественных реакций:\n"
                "- 'Понимаю, бюджет — важный фактор. Давайте посмотрим: если AI сэкономит 10 часов в неделю — посчитаем окупаемость?'\n"
                "- 'Я ценю вашу озабоченность. Можем поэтапно внедрить, начать с малого — как вам такой вариант?'\n\n"
                "Длина ответа: 2-4 предложения максимум.\n\n"
                "ПРИМЕЧАНИЕ: Для более точных инструкций используй get_objection_prompt_modifier() с типом возражения."
            ),
            SalesStage.CONSULTATION_OFFER: (
                "Сейчас этап предложения консультации. Предлагай естественно, как логичный следующий шаг.\n\n"
                "Правила:\n"
                "- Предложи созвон мягко, обоснуй интересами клиента ('Мне кажется, мы хорошо разобрались в вашей ситуации. Предлагаю созвониться, чтобы обсудить детали...')\n"
                "- Не дави, не навязывай ('как вы на это смотрите?')\n"
                "- Будь конкретным, но гибким\n\n"
                "Примеры естественных реакций:\n"
                "- 'Давай созвонимся на 15 минут, когда удобно? Можем разобрать детали и убедиться, что всё учтено'\n"
                "- 'Мне кажется, мы хорошо разобрались. Предлагаю созвониться — как вам удобнее?'\n\n"
                "Длина ответа: 2-3 предложения максимум."
            ),
            SalesStage.SCHEDULING: (
                "Сейчас этап согласования времени встречи. Помоги выбрать удобное время.\n\n"
                "Правила:\n"
                "- Будь гибким и предложи несколько вариантов\n"
                "- Учитывай доступные слоты времени\n"
                "- Подтверди договоренность понятно\n\n"
                "Примеры естественных реакций:\n"
                "- 'Могу в четверг в 15:00 или в пятницу в 11:00. Что удобнее?'\n"
                "- 'Жду тебя в четверг в 15:00, скину Zoom'\n\n"
                "Длина ответа: 2-3 предложения максимум."
            ),
            SalesStage.SUMMARY: (
                "Сейчас этап формирования сводки для встречи. Ты собрал всю необходимую информацию о клиенте.\n\n"
                "Правила:\n"
                "- Подтверди, что информация собрана и встреча будет подготовлена\n"
                "- Предложи встречу с готовой сводкой\n"
                "- Будь дружелюбным и профессиональным\n\n"
                "Примеры естественных реакций:\n"
                "- 'Отлично! Я собрал всю информацию о вашей компании и задачах. Предлагаю созвониться, чтобы обсудить варианты решения.'\n"
                "- 'Спасибо за подробную информацию! Готовлю материалы для встречи. Когда удобно созвониться?'\n\n"
                "Длина ответа: 2-3 предложения максимум."
            ),
        }

        return modifiers.get(stage, "")

    def get_stage_max_length(self, stage: SalesStage) -> Optional[int]:
        """
        Получить максимальную длину ответа для этапа (в символах).
        
        DEPRECATED: Всегда возвращает None. Единственный лимит - лимит Telegram (4096 символов),
        который обрабатывается автоматически через _split_long_message.

        Args:
            stage: Этап скрипта продаж

        Returns:
            Всегда None - без ограничений по длине ответа
        """
        # Убраны все лимиты - единственный лимит это лимит Telegram (4096 символов)
        # который обрабатывается автоматически в _split_long_message
        return None

    def get_generation_params(
        self, stage: SalesStage, intent: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Получить параметры генерации для этапа и intent.

        Args:
            stage: Этап скрипта продаж
            intent: Тип намерения ("SALES_AI", "REAL_ESTATE", "SMALL_TALK")

        Returns:
            Словарь с параметрами генерации (temperature, top_p, frequency_penalty, presence_penalty).
            max_tokens не указывается - используется базовый из config.yaml (8192).
            Единственный лимит длины - лимит Telegram (4096 символов), обрабатывается автоматически.
        """
        # Базовые параметры по умолчанию
        # max_tokens убран - используется только базовый из config.yaml (8192)
        # Единственный лимит - лимит Telegram (4096 символов), который обрабатывается автоматически
        base_params = {
            "temperature": 0.3,
            "top_p": 0.9,
            "frequency_penalty": 0.3,
            "presence_penalty": 0.2,
        }

        # Настройки для SMALL_TALK (более креативно)
        if intent == "SMALL_TALK":
            base_params.update(
                {
                    "temperature": 0.6,
                    "frequency_penalty": 0.2,
                    "presence_penalty": 0.1,
                }
            )

        # Настройки по этапам для SALES_AI и REAL_ESTATE
        # max_tokens убран - используется только базовый из config.yaml
        if intent in ("SALES_AI", "REAL_ESTATE"):
            if stage == SalesStage.GREETING:
                base_params.update(
                    {
                        "temperature": 0.5,
                        "frequency_penalty": 0.2,
                        "presence_penalty": 0.1,
                    }
                )
            elif stage == SalesStage.NEEDS_DISCOVERY:
                base_params.update(
                    {
                        "temperature": 0.4,
                        "frequency_penalty": 0.3,
                        "presence_penalty": 0.2,
                    }
                )
            elif stage == SalesStage.PRESENTATION:
                base_params.update(
                    {
                        "temperature": 0.3,
                        "frequency_penalty": 0.3,
                        "presence_penalty": 0.2,
                    }
                )
            elif stage == SalesStage.OBJECTIONS:
                base_params.update(
                    {
                        "temperature": 0.35,
                        "frequency_penalty": 0.25,
                        "presence_penalty": 0.15,
                    }
                )
            elif stage == SalesStage.CONSULTATION_OFFER:
                base_params.update(
                    {
                        "temperature": 0.4,
                        "frequency_penalty": 0.2,
                        "presence_penalty": 0.1,
                    }
                )
            elif stage == SalesStage.SCHEDULING:
                base_params.update(
                    {
                        "temperature": 0.4,
                        "frequency_penalty": 0.2,
                        "presence_penalty": 0.1,
                    }
                )
            elif stage == SalesStage.SUMMARY:
                base_params.update(
                    {
                        "temperature": 0.4,
                        "frequency_penalty": 0.2,
                        "presence_penalty": 0.1,
                    }
                )

        return base_params

    def get_slots(self, context_data: Optional[str]) -> Dict[str, Any]:
        """
        Получить заполненные слоты из контекста.

        Args:
            context_data: JSON строка с контекстом пользователя

        Returns:
            Словарь заполненных слотов (старый формат для обратной совместимости)
        """
        if not context_data:
            return {}

        try:
            data = json.loads(context_data)
            slots = data.get("slots", {})
            
            # Преобразуем новый формат (с confidence) в старый (просто value)
            result = {}
            for field, slot_data in slots.items():
                if isinstance(slot_data, dict) and "value" in slot_data:
                    result[field] = slot_data["value"]
                else:
                    result[field] = slot_data
            
            return result
        except (json.JSONDecodeError, ValueError):
            return {}

    def get_slots_with_confidence(self, context_data: Optional[str]) -> Dict[str, Dict[str, Any]]:
        """
        Получить заполненные слоты с уверенностью из контекста.

        Args:
            context_data: JSON строка с контекстом пользователя

        Returns:
            Словарь слотов в формате:
            {
                "field": {
                    "value": "...",
                    "source": "llm",
                    "confidence": 0.9,
                    "updated_at": "..."
                },
                ...
            }
        """
        if not context_data:
            return {}

        try:
            data = json.loads(context_data)
            slots = data.get("slots", {})
            
            # Поддерживаем оба формата
            result = {}
            for field, slot_data in slots.items():
                if isinstance(slot_data, dict) and "value" in slot_data:
                    result[field] = slot_data
                else:
                    # Старый формат - преобразуем в новый
                    result[field] = {
                        "value": slot_data,
                        "source": "legacy",
                        "confidence": 0.7,
                        "updated_at": datetime.now().isoformat(),
                    }
            
            return result
        except (json.JSONDecodeError, ValueError):
            return {}

    def get_low_confidence_slots(
        self, context_data: Optional[str], threshold: float = 0.6
    ) -> List[str]:
        """
        Получить список слотов с низкой уверенностью.

        Args:
            context_data: JSON строка с контекстом пользователя
            threshold: Порог уверенности (по умолчанию 0.6)

        Returns:
            Список названий слотов с confidence < threshold
        """
        slots_with_conf = self.get_slots_with_confidence(context_data)
        low_confidence = []
        
        for field, slot_data in slots_with_conf.items():
            confidence = slot_data.get("confidence", 0.7)
            if confidence < threshold:
                low_confidence.append(field)
        
        return low_confidence

    def get_medium_confidence_slots(
        self,
        context_data: Optional[str],
        threshold_min: float = 0.6,
        threshold_max: float = 0.8,
    ) -> List[str]:
        """
        Получить список слотов со средней уверенностью (для мягкого подтверждения).

        Args:
            context_data: JSON строка с контекстом пользователя
            threshold_min: Минимальный порог уверенности (по умолчанию 0.6)
            threshold_max: Максимальный порог уверенности (по умолчанию 0.8)

        Returns:
            Список названий слотов с confidence в диапазоне [threshold_min, threshold_max)
        """
        slots_with_conf = self.get_slots_with_confidence(context_data)
        medium_confidence = []
        
        for field, slot_data in slots_with_conf.items():
            confidence = slot_data.get("confidence", 0.7)
            if threshold_min <= confidence < threshold_max:
                medium_confidence.append(field)
        
        return medium_confidence

    async def auto_extract_slots(
        self, message: str, context_data: Optional[str], intent: Optional[str] = None
    ) -> str:
        """
        Автоматически извлечь слоты из сообщения с помощью LLM и обновить контекст.

        Args:
            message: Сообщение пользователя
            context_data: Текущий JSON контекст
            intent: Тип намерения ("SALES_AI" или "REAL_ESTATE")

        Returns:
            Обновленный JSON контекст с заполненными слотами
        """
        if not self.slot_extractor or not self.slot_extractor.enabled:
            return context_data or "{}"

        if not intent:
            if context_data:
                try:
                    data = json.loads(context_data)
                    intent = data.get("intent", "SALES_AI")
                except (json.JSONDecodeError, ValueError):
                    intent = "SALES_AI"
            else:
                intent = "SALES_AI"

        # Получаем список недостающих слотов
        missing_slots = self.get_missing_slots(context_data, intent)
        if not missing_slots:
            # Все слоты уже заполнены
            return context_data or "{}"

        # Извлекаем слоты из сообщения (новый формат с confidence)
        extracted_slots_list = await self.slot_extractor.extract_slots(
            message, intent, missing_slots
        )

        if not extracted_slots_list:
            # Не удалось извлечь слоты
            return context_data or "{}"

        # Обновляем контекст с извлеченными слотами
        if context_data:
            try:
                data = json.loads(context_data)
            except json.JSONDecodeError:
                data = {}
        else:
            data = {}

        if "slots" not in data:
            data["slots"] = {}

        # Обновляем только те слоты, которые были извлечены
        for slot_info in extracted_slots_list:
            slot_name = slot_info.get("field")
            if slot_name and slot_name in missing_slots:
                # Сохраняем в новом формате с confidence
                data["slots"][slot_name] = {
                    "value": slot_info.get("value"),
                    "source": slot_info.get("source", "llm"),
                    "confidence": slot_info.get("confidence", 0.7),
                    "updated_at": datetime.now().isoformat(),
                }
                logger.info(
                    f"Auto-extracted slot '{slot_name}': {slot_info.get('value')} "
                    f"(confidence={slot_info.get('confidence', 0.7):.2f})"
                )

        # Обратная совместимость: если заполнен domain, но нет company_domain, копируем
        if "domain" in data.get("slots", {}) and "company_domain" not in data.get(
            "slots", {}
        ):
            data["slots"]["company_domain"] = data["slots"]["domain"]

        # Пересчитываем missing_slots
        self._update_missing_slots(data)

        return json.dumps(data)

    def update_slot(
        self, context_data: Optional[str], slot_name: str, slot_value: Any
    ) -> str:
        """
        Обновить один слот в контексте.

        Args:
            context_data: Текущий JSON контекст
            slot_name: Название слота
            slot_value: Значение слота

        Returns:
            Обновленный JSON контекст
        """
        if context_data:
            try:
                data = json.loads(context_data)
            except json.JSONDecodeError:
                data = {}
        else:
            data = {}

        if "slots" not in data:
            data["slots"] = {}

        data["slots"][slot_name] = slot_value
        # Пересчитываем missing_slots
        self._update_missing_slots(data)

        return json.dumps(data)

    def get_missing_slots(
        self, context_data: Optional[str], intent: Optional[str] = None
    ) -> List[str]:
        """
        Получить список незаполненных обязательных слотов.

        Args:
            context_data: JSON строка с контекстом пользователя
            intent: Тип намерения ("SALES_AI" или "REAL_ESTATE")

        Returns:
            Список названий незаполненных слотов
        """
        if not context_data:
            if intent == "REAL_ESTATE":
                return list(self.REAL_ESTATE_REQUIRED_SLOTS)
            return list(self.SALES_REQUIRED_SLOTS)

        try:
            data = json.loads(context_data)
            # Используем intent из контекста если не передан явно
            if not intent:
                intent = data.get("intent", "SALES_AI")

            filled_slots = set(data.get("slots", {}).keys())

            # Обратная совместимость: если заполнен domain, считаем что company_domain тоже заполнен
            if (
                intent != "REAL_ESTATE"
                and "domain" in filled_slots
                and "company_domain" not in filled_slots
            ):
                filled_slots.add("company_domain")

            if intent == "REAL_ESTATE":
                required_slots = self.REAL_ESTATE_REQUIRED_SLOTS
            else:
                required_slots = self.SALES_REQUIRED_SLOTS

            missing = required_slots - filled_slots
            return list(missing)
        except (json.JSONDecodeError, ValueError):
            if intent == "REAL_ESTATE":
                return list(self.REAL_ESTATE_REQUIRED_SLOTS)
            return list(self.SALES_REQUIRED_SLOTS)

    def get_slot_prompt(
        self, slot_name: str, intent: Optional[str] = None
    ) -> Optional[str]:
        """
        Получить промпт для запроса конкретного слота.

        Args:
            slot_name: Название слота
            intent: Тип намерения ("SALES_AI" или "REAL_ESTATE")

        Returns:
            Промпт для запроса слота или None если слот не найден
        """
        if intent == "REAL_ESTATE":
            prompts = self.REAL_ESTATE_SLOT_PROMPTS
        else:
            prompts = self.SALES_SLOT_PROMPTS

        return prompts.get(slot_name)

    def get_next_slot_to_ask(
        self, context_data: Optional[str], intent: Optional[str] = None
    ) -> Optional[str]:
        """
        Получить следующий слот для запроса.

        Args:
            context_data: JSON строка с контекстом пользователя
            intent: Тип намерения ("SALES_AI" или "REAL_ESTATE")

        Returns:
            Название следующего слота для запроса или None если все заполнены
        """
        missing_slots = self.get_missing_slots(context_data, intent)
        if not missing_slots:
            return None

        # Для REAL_ESTATE используем старую логику приоритетов
        if intent == "REAL_ESTATE":
            priority_slots = ["goal", "purpose", "budget", "budget_band", "contact"]
            for priority_slot in priority_slots:
                if priority_slot in missing_slots:
                    return priority_slot
            return missing_slots[0]

        # Для SALES_AI используем новую логику приоритетов: базовые → бизнес → проект
        # Приоритет 1: базовые слоты
        priority1_slots = ["client_name", "company_name", "contact", "company_size"]
        for priority_slot in priority1_slots:
            if priority_slot in missing_slots:
                return priority_slot

        # Приоритет 2: слоты о бизнесе
        priority2_slots = [
            "company_domain",
            "main_problems",
            "time_consuming_tasks",
            "process_volume",
            "employees_involved",
            "current_time_cost",
            "error_rate",
            "business_revenue",
            "current_cost",
        ]
        for priority_slot in priority2_slots:
            if priority_slot in missing_slots:
                return priority_slot

        # Приоритет 3: слоты о проекте
        priority3_slots = [
            "goal",
            "deadline",
            "budget_band",
            "data_access",
            "success_metric",
        ]
        for priority_slot in priority3_slots:
            if priority_slot in missing_slots:
                return priority_slot

        # Иначе возвращаем первый из недостающих (для обратной совместимости со старым "domain")
        return missing_slots[0]

    def _update_missing_slots(self, data: Dict) -> None:
        """
        Обновить список missing_slots в данных контекста.

        Args:
            data: Словарь данных контекста (изменяется на месте)
        """
        intent = data.get("intent", "SALES_AI")
        filled_slots = set(data.get("slots", {}).keys())

        # Обратная совместимость: если заполнен domain, считаем что company_domain тоже заполнен
        if (
            intent != "REAL_ESTATE"
            and "domain" in filled_slots
            and "company_domain" not in filled_slots
        ):
            filled_slots.add("company_domain")

        if intent == "REAL_ESTATE":
            required_slots = self.REAL_ESTATE_REQUIRED_SLOTS
        else:
            required_slots = self.SALES_REQUIRED_SLOTS

        missing = required_slots - filled_slots
        data["missing_slots"] = list(missing)

    def update_intent(self, context_data: Optional[str], intent: str) -> str:
        """
        Обновить intent в контексте.

        Args:
            context_data: Текущий JSON контекст
            intent: Тип намерения ("SALES_AI", "REAL_ESTATE", "SMALL_TALK")

        Returns:
            Обновленный JSON контекст
        """
        if context_data:
            try:
                data = json.loads(context_data)
            except json.JSONDecodeError:
                data = {}
        else:
            data = {}

        data["intent"] = intent
        # Пересчитываем missing_slots если есть slots
        if "slots" in data:
            self._update_missing_slots(data)

        return json.dumps(data)

    def should_transition_to_summary(
        self, context_data: Optional[str], intent: Optional[str] = None
    ) -> bool:
        """
        Проверить, нужно ли перейти на этап SUMMARY (все обязательные слоты заполнены).

        Args:
            context_data: JSON строка с контекстом пользователя
            intent: Тип намерения ("SALES_AI" или "REAL_ESTATE")

        Returns:
            True если все слоты заполнены и можно перейти на SUMMARY
        """
        if not self.enabled:
            return False

        missing_slots = self.get_missing_slots(context_data, intent)
        return len(missing_slots) == 0

    # Порог fit_score для предложения встречи
    FIT_SCORE_THRESHOLD = 60

    def compute_fit_score(self, context_data: Optional[str]) -> int:
        """
        Вычислить fit_score (0-100) на основе заполненных слотов.

        Формула:
        - Признанная проблема (main_problems заполнено): +20
        - Измеримый объём/ошибка (process_volume или error_rate заполнено): +20
        - Доступ к данным (data_access заполнено): +15
        - Лицо, принимающее решение (client_name + company_name заполнено): +15
        - Бюджет/вилка (budget_band заполнено): +20
        - Сроки (deadline заполнено): +10

        Args:
            context_data: JSON строка с контекстом пользователя

        Returns:
            Fit score от 0 до 100
        """
        slots = self.get_slots(context_data)
        score = 0

        # Признанная проблема
        if slots.get("main_problems"):
            score += 20

        # Измеримый объём/ошибка
        if slots.get("process_volume") or slots.get("error_rate"):
            score += 20

        # Доступ к данным
        if slots.get("data_access"):
            score += 15

        # Лицо, принимающее решение
        if slots.get("client_name") and slots.get("company_name"):
            score += 15

        # Бюджет/вилка
        if slots.get("budget_band"):
            score += 20

        # Сроки
        if slots.get("deadline"):
            score += 10

        return min(100, score)  # Ограничиваем максимум 100

    def get_fit_score_breakdown(self, context_data: Optional[str]) -> Dict[str, Any]:
        """
        Получить детальную разбивку fit_score для логирования/отладки.

        Args:
            context_data: JSON строка с контекстом пользователя

        Returns:
            Словарь с разбивкой:
            {
                "total_score": 65,
                "components": {
                    "problem": 20,
                    "metrics": 20,
                    "data_access": 15,
                    "decision_maker": 15,
                    "budget": 20,
                    "deadline": 0
                },
                "threshold": 60,
                "meets_threshold": True
            }
        """
        slots = self.get_slots(context_data)
        components = {}

        # Признанная проблема
        components["problem"] = 20 if slots.get("main_problems") else 0

        # Измеримый объём/ошибка
        components["metrics"] = 20 if (slots.get("process_volume") or slots.get("error_rate")) else 0

        # Доступ к данным
        components["data_access"] = 15 if slots.get("data_access") else 0

        # Лицо, принимающее решение
        components["decision_maker"] = 15 if (slots.get("client_name") and slots.get("company_name")) else 0

        # Бюджет/вилка
        components["budget"] = 20 if slots.get("budget_band") else 0

        # Сроки
        components["deadline"] = 10 if slots.get("deadline") else 0

        total_score = sum(components.values())

        return {
            "total_score": total_score,
            "components": components,
            "threshold": self.FIT_SCORE_THRESHOLD,
            "meets_threshold": total_score >= self.FIT_SCORE_THRESHOLD,
        }

    def should_offer_consultation(
        self,
        context_data: Optional[str],
        intent: Optional[str] = None,
        presentation_messages_count: int = 0,
        is_ready_for_meeting: bool = False,
        explicit_request: bool = False,
    ) -> bool:
        """
        Проверить, нужно ли автоматически предложить консультацию.

        Предложение встречи происходит если:
        - fit_score >= FIT_SCORE_THRESHOLD (60) ИЛИ есть явный запрос созвона
        - И текущий этап PRESENTATION
        - И собрано достаточно информации или было 2+ сообщений на PRESENTATION

        Args:
            context_data: JSON строка с контекстом пользователя
            intent: Тип намерения ("SALES_AI" или "REAL_ESTATE")
            presentation_messages_count: Количество сообщений на этапе PRESENTATION
            is_ready_for_meeting: True если собрано достаточно информации для встречи
            explicit_request: True если пользователь явно запросил встречу/созвон

        Returns:
            True если нужно предложить консультацию
        """
        if not self.enabled:
            return False

        # Проверяем текущий этап - должен быть PRESENTATION
        current_stage = self.get_stage(context_data)
        if current_stage != SalesStage.PRESENTATION:
            return False

        # Вычисляем fit_score
        fit_score = self.compute_fit_score(context_data)
        meets_fit_threshold = fit_score >= self.FIT_SCORE_THRESHOLD

        # Предлагаем встречу если:
        # 1. fit_score >= 60 ИЛИ есть явный запрос
        # 2. И (собрано достаточно информации ИЛИ было 2+ сообщений на PRESENTATION)
        should_offer = (meets_fit_threshold or explicit_request) and (
            is_ready_for_meeting or presentation_messages_count >= 2
        )

        if should_offer:
            breakdown = self.get_fit_score_breakdown(context_data)
            logger.info(
                f"Should offer consultation: fit_score={fit_score} "
                f"(threshold={self.FIT_SCORE_THRESHOLD}, explicit_request={explicit_request}, "
                f"breakdown={breakdown['components']})"
            )

        return should_offer

    def _handle_slot_found(self, event) -> None:
        """
        Обработчик события SLOT_FOUND.

        Args:
            event: Событие с информацией о найденном слоте
        """
        payload = event.payload
        field = payload.get("field")
        confidence = payload.get("confidence", 0.7)
        
        logger.debug(f"Handling SLOT_FOUND event: field={field}, confidence={confidence:.2f}")
        
        # Можно добавить дополнительную логику обработки здесь
        # Например, обновление missing_slots или проверка переходов

    def _handle_slot_correction(self, event) -> None:
        """
        Обработчик события SLOT_CORRECTION.

        Args:
            event: Событие с информацией об исправленном слоте
        """
        payload = event.payload
        field = payload.get("field")
        new_confidence = payload.get("confidence", 0.7)
        
        logger.debug(f"Handling SLOT_CORRECTION event: field={field}, new_confidence={new_confidence:.2f}")

    def _handle_intent_changed(self, event) -> None:
        """
        Обработчик события INTENT_CHANGED.

        Args:
            event: Событие с информацией об изменении намерения
        """
        payload = event.payload
        new_intent = payload.get("intent")
        
        logger.debug(f"Handling INTENT_CHANGED event: new_intent={new_intent}")

    async def classify_objection(self, message: str) -> ObjectionType:
        """
        Классифицировать тип возражения на основе сообщения.

        Args:
            message: Сообщение пользователя с возражением

        Returns:
            Тип возражения
        """
        if not message:
            return ObjectionType.OTHER

        message_lower = message.lower()

        # Подсчитываем совпадения по типам возражений
        price_score = sum(1 for keyword in self.PRICE_KEYWORDS if keyword in message_lower)
        timing_score = sum(1 for keyword in self.TIMING_KEYWORDS if keyword in message_lower)
        need_score = sum(1 for keyword in self.NEED_KEYWORDS if keyword in message_lower)
        trust_score = sum(1 for keyword in self.TRUST_KEYWORDS if keyword in message_lower)
        competitor_score = sum(1 for keyword in self.COMPETITOR_KEYWORDS if keyword in message_lower)

        # Находим тип с максимальным score
        scores = {
            ObjectionType.PRICE: price_score,
            ObjectionType.TIMING: timing_score,
            ObjectionType.NEED: need_score,
            ObjectionType.TRUST: trust_score,
            ObjectionType.COMPETITOR: competitor_score,
        }

        max_score = max(scores.values())
        if max_score > 0:
            # Возвращаем тип с максимальным score
            for objection_type, score in scores.items():
                if score == max_score:
                    logger.debug(f"Classified objection as {objection_type.value} (score={score})")
                    return objection_type

        # Если нет явных признаков - используем LLM если доступен
        if self.ai_client:
            try:
                return await self._classify_objection_with_llm(message)
            except Exception as e:
                logger.warning(f"Error in LLM-based objection classification: {e}")
                return ObjectionType.OTHER

        return ObjectionType.OTHER

    async def _classify_objection_with_llm(self, message: str) -> ObjectionType:
        """
        Классифицировать возражение через LLM.

        Args:
            message: Сообщение пользователя с возражением

        Returns:
            Тип возражения
        """
        if not self.ai_client:
            return ObjectionType.OTHER

        prompt = f"""Определи тип возражения клиента в следующем сообщении. Доступные типы:

1. PRICE - возражения по цене/бюджету (дорого, не по карману, бюджет)
2. TIMING - возражения по времени/срокам (позже, не сейчас, не время)
3. NEED - возражения по необходимости (не нужно, не интересно, не требуется)
4. TRUST - возражения по доверию (сомневаюсь, не уверен, риск)
5. COMPETITOR - упоминание конкурентов (уже есть решение, используем другое)
6. OTHER - другие возражения

Сообщение клиента: "{message}"

Верни ответ ТОЛЬКО в формате JSON, без дополнительного текста:
{{
  "type": "PRICE" | "TIMING" | "NEED" | "TRUST" | "COMPETITOR" | "OTHER",
  "confidence": 0.0-1.0
}}"""

        try:
            messages = [{"role": "user", "content": prompt}]
            response = await self.ai_client.get_response(
                messages,
                temperature=0.2,
                max_tokens=100,
            )

            # Парсим JSON ответ
            import json
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            response = response.strip()

            result = json.loads(response)
            objection_type_str = result.get("type", "OTHER")
            confidence = result.get("confidence", 0.5)

            try:
                objection_type = ObjectionType(objection_type_str.lower())
                logger.debug(
                    f"LLM classified objection as {objection_type.value} "
                    f"(confidence={confidence:.2f})"
                )
                return objection_type
            except ValueError:
                logger.warning(f"Unknown objection type from LLM: {objection_type_str}")
                return ObjectionType.OTHER

        except Exception as e:
            logger.warning(f"Error in LLM objection classification: {e}")
            return ObjectionType.OTHER

    def get_objection_history(self, context_data: Optional[str]) -> List[Dict[str, Any]]:
        """
        Получить историю возражений из контекста.

        Args:
            context_data: JSON строка с контекстом пользователя

        Returns:
            Список словарей с историей возражений:
            [{"type": str, "message": str, "timestamp": str}, ...]
        """
        if not context_data:
            return []

        try:
            data = json.loads(context_data)
            return data.get("objection_history", [])
        except (json.JSONDecodeError, ValueError):
            return []

    def add_objection_to_history(
        self, context_data: Optional[str], objection_type: ObjectionType, message: str
    ) -> str:
        """
        Добавить возражение в историю контекста.

        Args:
            context_data: Текущий JSON контекст
            objection_type: Тип возражения
            message: Сообщение пользователя с возражением

        Returns:
            Обновленный JSON контекст
        """
        if context_data:
            try:
                data = json.loads(context_data)
            except json.JSONDecodeError:
                data = {}
        else:
            data = {}

        if "objection_history" not in data:
            data["objection_history"] = []

        # Добавляем возражение в историю
        data["objection_history"].append(
            {
                "type": objection_type.value,
                "message": message[:200],  # Ограничиваем длину
                "timestamp": datetime.now().isoformat(),
            }
        )

        # Ограничиваем историю последними 10 возражениями
        data["objection_history"] = data["objection_history"][-10:]

        return json.dumps(data)

    def get_objection_count_by_type(
        self, context_data: Optional[str], objection_type: ObjectionType
    ) -> int:
        """
        Получить количество возражений определенного типа в истории.

        Args:
            context_data: JSON строка с контекстом пользователя
            objection_type: Тип возражения

        Returns:
            Количество возражений данного типа
        """
        history = self.get_objection_history(context_data)
        return sum(1 for obj in history if obj.get("type") == objection_type.value)

    def get_objection_prompt_modifier(
        self, context_data: Optional[str], objection_type: Optional[ObjectionType] = None
    ) -> str:
        """
        Получить улучшенный промпт-модификатор для этапа OBJECTIONS с учетом типа возражения.

        Args:
            context_data: JSON строка с контекстом пользователя
            objection_type: Тип возражения (если известен)

        Returns:
            Дополнительный текст для системного промпта
        """
        base_modifier = (
            "Сейчас этап работы с возражениями. Работай как консультант, не как продавец.\n\n"
            "Правила:\n"
            "- НЕ спорь с клиентом — разбирай сомнения вместе с ним\n"
            "- Проявляй понимание и эмпатию ('Я ценю вашу озабоченность...')\n"
            "- Вставай на сторону клиента — пытайся найти компромисс\n"
            "- Предлагай варианты решения проблемы ('Давайте посмотрим, как можно...')\n"
        )

        # Если тип возражения известен, добавляем специфичные инструкции
        if objection_type and objection_type in self.OBJECTION_RESPONSE_TEMPLATES:
            template = self.OBJECTION_RESPONSE_TEMPLATES[objection_type]
            base_modifier += f"\n\nТип возражения: {objection_type.value.upper()}\n"
            base_modifier += f"Подход: {template['approach']}\n\n"
            base_modifier += "Примеры хороших ответов:\n"
            for i, example in enumerate(template["examples"][:2], 1):  # Берем первые 2 примера
                base_modifier += f"{i}. {example}\n"

        # Проверяем историю возражений для эскалации
        history = self.get_objection_history(context_data)
        if objection_type:
            count = self.get_objection_count_by_type(context_data, objection_type)
            if count >= 2:
                base_modifier += (
                    f"\n\n⚠️ ВАЖНО: Это уже {count}-е возражение типа {objection_type.value}. "
                    "Клиент повторяет одно и то же возражение. Нужно изменить подход:\n"
                    "- Не повторяй те же аргументы\n"
                    "- Попробуй другой угол зрения или предложи конкретное действие\n"
                    "- Если возражение серьезное — предложи встречу для детального обсуждения\n"
                )

        base_modifier += "\nДлина ответа: 2-4 предложения максимум."

        return base_modifier
