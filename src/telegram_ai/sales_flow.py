"""Скрипт продаж (Sales Flow) с state machine и управлением слотами."""

import json
import logging
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

    def __init__(self, enabled: bool = True, slot_extractor=None):
        """
        Инициализация SalesFlow.

        Args:
            enabled: Включить скрипт продаж
            slot_extractor: Экземпляр SlotExtractor для автоматического извлечения слотов
        """
        self.enabled = enabled
        self.slot_extractor = slot_extractor
        logger.info(f"SalesFlow initialized: enabled={enabled}")

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

        # Логика переходов
        if current_stage == SalesStage.GREETING:
            if any(keyword in message_lower for keyword in self.NEEDS_KEYWORDS):
                return SalesStage.NEEDS_DISCOVERY
            if any(keyword in message_lower for keyword in self.PRESENTATION_KEYWORDS):
                return SalesStage.PRESENTATION

        elif current_stage == SalesStage.NEEDS_DISCOVERY:
            if any(keyword in message_lower for keyword in self.PRESENTATION_KEYWORDS):
                return SalesStage.PRESENTATION
            if any(keyword in message_lower for keyword in self.OBJECTIONS_KEYWORDS):
                return SalesStage.OBJECTIONS

        elif current_stage == SalesStage.PRESENTATION:
            if any(keyword in message_lower for keyword in self.OBJECTIONS_KEYWORDS):
                return SalesStage.OBJECTIONS
            if any(keyword in message_lower for keyword in self.CONSULTATION_KEYWORDS):
                return SalesStage.CONSULTATION_OFFER

        elif current_stage == SalesStage.OBJECTIONS:
            if any(keyword in message_lower for keyword in self.CONSULTATION_KEYWORDS):
                return SalesStage.CONSULTATION_OFFER

        elif current_stage == SalesStage.CONSULTATION_OFFER:
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
                "КРИТИЧЕСКИ ВАЖНО: Сейчас этап приветствия. Твой ответ должен быть КОРОТКИМ - максимум 1-2 предложения (до 150 символов).\n\n"
                "Примеры хороших ответов:\n"
                "- 'Привет! Я Александр из Scanovich.ai. Чем могу помочь?'\n"
                "- 'Привет! Меня зовут Александр. Как дела?'\n\n"
                "Пример плохого ответа: длинное развернутое сообщение с подробным описанием компании или проектов.\n\n"
                "Правила:\n"
                "- Поприветствуй пользователя дружелюбно, представься как Александр\n"
                "- Если знаешь имя пользователя (из контекста) — используй его, но не в каждом сообщении\n"
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
                "Примеры естественных реакций:\n"
                "- 'Окей, понял. А расскажи, какая у вас сейчас ситуация с [проблема]?'\n"
                "- 'Понимаю, это боль многих компаний. Что чаще всего вызывает [проблема]?'\n"
                "- 'Спасибо за информацию! А можешь поделиться примерным оборотом компании? Это поможет лучше понять масштаб задачи.'\n\n"
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
                "- Отвечай ПОЛНОСТЬЮ и развернуто, раскрывай все возможности и детали решения, не обрезай ответ\n\n"
                "Примеры естественных реакций:\n"
                "- 'Вы упоминали, что у вас слишком много ручной работы в отчётах — наше решение автоматизирует сбор данных и тем самым снимет эту нагрузку'\n"
                "- 'Я недавно делал похожий проект для [домен]. Там удалось сократить время обработки на 70%. Рассказать подробнее?'\n\n"
                "ВАЖНО: Отвечай развернуто, раскрывай все аспекты решения, не обрезай ответ многоточием."
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
                "Длина ответа: 2-4 предложения максимум."
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

        Args:
            stage: Этап скрипта продаж

        Returns:
            Максимальная длина ответа в символах или None если ограничения нет
        """
        max_lengths = {
            SalesStage.GREETING: 150,  # Очень коротко для приветствия
            SalesStage.NEEDS_DISCOVERY: None,  # Без лимита - для развернутых ответов на длинные транскрипты
            SalesStage.PRESENTATION: None,  # Без лимита - для полных презентаций (Telegram сам ограничит до 4096)
            SalesStage.OBJECTIONS: 2500,  # Увеличено для детальных ответов на возражения
            SalesStage.CONSULTATION_OFFER: 600,  # Умеренно увеличено для предложения
            SalesStage.SCHEDULING: 500,  # Умеренно для согласования
            SalesStage.SUMMARY: 400,  # Умеренно для этапа сводки
        }

        return max_lengths.get(stage, None)

    def get_generation_params(
        self, stage: SalesStage, intent: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Получить параметры генерации для этапа и intent.

        Args:
            stage: Этап скрипта продаж
            intent: Тип намерения ("SALES_AI", "REAL_ESTATE", "SMALL_TALK")

        Returns:
            Словарь с параметрами генерации (temperature, max_tokens, top_p, frequency_penalty, presence_penalty)
        """
        # Базовые параметры по умолчанию
        base_params = {
            "temperature": 0.3,
            "max_tokens": 300,
            "top_p": 0.9,
            "frequency_penalty": 0.3,
            "presence_penalty": 0.2,
        }

        # Настройки для SMALL_TALK (более креативно)
        if intent == "SMALL_TALK":
            base_params.update(
                {
                    "temperature": 0.6,
                    "max_tokens": 120,
                    "frequency_penalty": 0.2,
                    "presence_penalty": 0.1,
                }
            )

        # Настройки по этапам для SALES_AI и REAL_ESTATE
        if intent in ("SALES_AI", "REAL_ESTATE"):
            if stage == SalesStage.GREETING:
                base_params.update(
                    {
                        "temperature": 0.5,
                        "max_tokens": 80,
                        "frequency_penalty": 0.2,
                        "presence_penalty": 0.1,
                    }
                )
            elif stage == SalesStage.NEEDS_DISCOVERY:
                base_params.update(
                    {
                        "temperature": 0.4,
                        "max_tokens": 600,  # Увеличено с 150 до 600 для более подробных вопросов
                        "frequency_penalty": 0.3,
                        "presence_penalty": 0.2,
                    }
                )
            elif stage == SalesStage.PRESENTATION:
                base_params.update(
                    {
                        "temperature": 0.3,
                        "max_tokens": 2000,  # Значительно увеличено с 400 до 2000 для развернутых презентаций
                        "frequency_penalty": 0.3,
                        "presence_penalty": 0.2,
                    }
                )
            elif stage == SalesStage.OBJECTIONS:
                base_params.update(
                    {
                        "temperature": 0.35,
                        "max_tokens": 800,  # Увеличено с 300 до 800 для развернутых ответов на возражения
                        "frequency_penalty": 0.25,
                        "presence_penalty": 0.15,
                    }
                )
            elif stage == SalesStage.CONSULTATION_OFFER:
                base_params.update(
                    {
                        "temperature": 0.4,
                        "max_tokens": 200,
                        "frequency_penalty": 0.2,
                        "presence_penalty": 0.1,
                    }
                )
            elif stage == SalesStage.SCHEDULING:
                base_params.update(
                    {
                        "temperature": 0.4,
                        "max_tokens": 180,
                        "frequency_penalty": 0.2,
                        "presence_penalty": 0.1,
                    }
                )
            elif stage == SalesStage.SUMMARY:
                base_params.update(
                    {
                        "temperature": 0.4,
                        "max_tokens": 200,
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
            Словарь заполненных слотов
        """
        if not context_data:
            return {}

        try:
            data = json.loads(context_data)
            return data.get("slots", {})
        except (json.JSONDecodeError, ValueError):
            return {}

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

        # Извлекаем слоты из сообщения
        extracted_slots = await self.slot_extractor.extract_slots(
            message, intent, missing_slots
        )

        if not extracted_slots:
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
        for slot_name, slot_value in extracted_slots.items():
            if slot_name in missing_slots:  # Проверяем что слот действительно был нужен
                data["slots"][slot_name] = slot_value
                logger.info(f"Auto-extracted slot '{slot_name}': {slot_value}")

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
