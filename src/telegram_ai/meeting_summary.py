"""Генерация сводки для встречи с клиентом на основе собранных слотов."""

import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MeetingSummary:
    """Генерация структурированной сводки для встречи с клиентом."""

    def __init__(self):
        """Инициализация MeetingSummary."""
        logger.info("MeetingSummary initialized")

    def generate_summary(self, slots: Dict[str, Any]) -> str:
        """
        Сформировать текстовую сводку из собранных слотов.

        Args:
            slots: Словарь с заполненными слотами

        Returns:
            Текстовая сводка о клиенте и его потребностях
        """
        if not slots:
            return "Информация о клиенте не собрана."

        summary_parts = []

        # Базовая информация
        summary_parts.append("=== ИНФОРМАЦИЯ О КЛИЕНТЕ ===")
        if slots.get("client_name"):
            summary_parts.append(f"Имя: {slots['client_name']}")
        if slots.get("company_name"):
            summary_parts.append(f"Компания: {slots['company_name']}")
        if slots.get("contact"):
            summary_parts.append(f"Контакты: {slots['contact']}")
        if slots.get("company_size"):
            summary_parts.append(f"Размер компании: {slots['company_size']}")

        # Информация о бизнесе
        if any(
            slots.get(key)
            for key in [
                "company_domain",
                "domain",
                "main_problems",
                "time_consuming_tasks",
            ]
        ):
            summary_parts.append("\n=== О БИЗНЕСЕ ===")
            if slots.get("company_domain") or slots.get("domain"):
                domain = slots.get("company_domain") or slots.get("domain")
                summary_parts.append(f"Сфера деятельности: {domain}")
            if slots.get("main_problems"):
                summary_parts.append(f"Основные проблемы: {slots['main_problems']}")
            if slots.get("time_consuming_tasks"):
                summary_parts.append(
                    f"Задачи, отнимающие время: {slots['time_consuming_tasks']}"
                )

        # Метрики бизнеса
        if any(
            slots.get(key)
            for key in [
                "process_volume",
                "employees_involved",
                "current_time_cost",
                "error_rate",
                "business_revenue",
                "current_cost",
            ]
        ):
            summary_parts.append("\n=== МЕТРИКИ И ПОКАЗАТЕЛИ ===")
            if slots.get("process_volume"):
                summary_parts.append(f"Объем операций: {slots['process_volume']}")
            if slots.get("employees_involved"):
                summary_parts.append(
                    f"Сотрудников в процессе: {slots['employees_involved']}"
                )
            if slots.get("current_time_cost"):
                summary_parts.append(
                    f"Текущие временные затраты: {slots['current_time_cost']}"
                )
            if slots.get("error_rate"):
                summary_parts.append(f"Уровень ошибок: {slots['error_rate']}")
            if slots.get("business_revenue"):
                summary_parts.append(f"Оборот компании: {slots['business_revenue']}")
            if slots.get("current_cost"):
                summary_parts.append(
                    f"Текущие затраты на процесс: {slots['current_cost']}"
                )

        # Информация о проекте
        if any(
            slots.get(key)
            for key in ["goal", "deadline", "budget_band", "data_access", "success_metric"]
        ):
            summary_parts.append("\n=== О ПРОЕКТЕ ===")
            if slots.get("goal"):
                summary_parts.append(f"Цель проекта: {slots['goal']}")
            if slots.get("deadline"):
                summary_parts.append(f"Сроки: {slots['deadline']}")
            if slots.get("budget_band"):
                summary_parts.append(f"Бюджет: {slots['budget_band']}")
            if slots.get("data_access"):
                summary_parts.append(f"Доступ к данным: {slots['data_access']}")
            if slots.get("success_metric"):
                summary_parts.append(
                    f"Критерий успеха: {slots['success_metric']}"
                )

        summary_text = "\n".join(summary_parts)
        logger.info(f"Generated meeting summary: {len(summary_parts)} sections")
        return summary_text

    def generate_mini_agenda(self, slots: Dict[str, Any], fit_score: int) -> str:
        """
        Сформировать мини-повестку встречи на основе собранных слотов и fit_score.

        Args:
            slots: Словарь с заполненными слотами
            fit_score: Fit score (0-100)

        Returns:
            Текстовая мини-повестка встречи
        """
        agenda_parts = []
        
        # Заголовок
        agenda_parts.append("📋 Повестка встречи:")
        
        # Основные темы на основе собранных слотов
        if slots.get("main_problems"):
            agenda_parts.append(f"• Обсуждение проблемы: {slots['main_problems']}")
        
        if slots.get("goal"):
            agenda_parts.append(f"• Цель проекта: {slots['goal']}")
        
        if slots.get("process_volume") or slots.get("error_rate"):
            metrics = []
            if slots.get("process_volume"):
                metrics.append(f"объем: {slots['process_volume']}")
            if slots.get("error_rate"):
                metrics.append(f"ошибки: {slots['error_rate']}")
            if metrics:
                agenda_parts.append(f"• Метрики: {', '.join(metrics)}")
        
        if slots.get("budget_band"):
            agenda_parts.append(f"• Бюджет: {slots['budget_band']}")
        
        if slots.get("deadline"):
            agenda_parts.append(f"• Сроки: {slots['deadline']}")
        
        # Fit score для контекста
        if fit_score < 60:
            agenda_parts.append(f"\n⚠️ Fit score: {fit_score}/100 (ниже порога 60)")
            agenda_parts.append("Рекомендуется уточнить недостающую информацию на встрече.")
        else:
            agenda_parts.append(f"\n✅ Fit score: {fit_score}/100")
        
        agenda_text = "\n".join(agenda_parts)
        logger.info(f"Generated mini agenda with fit_score={fit_score}")
        return agenda_text

    def generate_json_summary(self, slots: Dict[str, Any]) -> Dict[str, Any]:
        """
        Сформировать JSON структуру сводки для автоматической обработки.

        Args:
            slots: Словарь с заполненными слотами

        Returns:
            Словарь с структурированной информацией о клиенте
        """
        if not slots:
            return {}

        summary = {
            "client_info": {
                "client_name": slots.get("client_name"),
                "company_name": slots.get("company_name"),
                "contact": slots.get("contact"),
                "company_size": slots.get("company_size"),
            },
            "business_info": {
                "company_domain": slots.get("company_domain") or slots.get("domain"),
                "main_problems": slots.get("main_problems"),
                "time_consuming_tasks": slots.get("time_consuming_tasks"),
            },
            "metrics": {
                "process_volume": slots.get("process_volume"),
                "employees_involved": slots.get("employees_involved"),
                "current_time_cost": slots.get("current_time_cost"),
                "error_rate": slots.get("error_rate"),
                "business_revenue": slots.get("business_revenue"),
                "current_cost": slots.get("current_cost"),
            },
            "project_info": {
                "goal": slots.get("goal"),
                "deadline": slots.get("deadline"),
                "budget_band": slots.get("budget_band"),
                "data_access": slots.get("data_access"),
                "success_metric": slots.get("success_metric"),
            },
        }

        # Убираем None значения из вложенных словарей
        for section in summary.values():
            if isinstance(section, dict):
                section.update({k: v for k, v in section.items() if v is not None})

        logger.info("Generated JSON meeting summary")
        return summary

    def is_ready_for_meeting(
        self, slots: Dict[str, Any], required_slots: Optional[set] = None
    ) -> bool:
        """
        Проверить, достаточно ли информации для встречи.

        Args:
            slots: Словарь с заполненными слотами
            required_slots: Множество обязательных слотов (если None, проверяет базовые)

        Returns:
            True если собрана минимальная информация для встречи
        """
        if not slots:
            return False

        # Базовые обязательные слоты для встречи
        if required_slots is None:
            minimal_required = {
                "client_name",
                "company_name",
                "contact",
                "main_problems",
                "goal",
            }
        else:
            minimal_required = required_slots

        # Проверяем наличие хотя бы минимальных обязательных слотов
        filled_slots = set(slots.keys())
        missing = minimal_required - filled_slots

        # Если есть хотя бы 3 из 5 базовых слотов - считаем готовым
        return len(missing) <= 2

    def analyze_conversation_history(
        self, conversation_history: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """
        Проанализировать историю диалога для извлечения ключевой информации.

        Args:
            conversation_history: Список сообщений [{"role": "user/assistant", "content": "..."}]

        Returns:
            Словарь с анализом: темы, тон, статистика, возражения, интересы
        """
        if not conversation_history:
            return {
                "total_messages": 0,
                "duration_days": 0,
                "top_themes": [],
                "tone": "neutral",
                "objections": [],
                "interests": [],
            }

        # Подсчет статистики
        total_messages = len(conversation_history)
        user_messages = [msg for msg in conversation_history if msg.get("role") == "user"]
        assistant_messages = [
            msg for msg in conversation_history if msg.get("role") == "assistant"
        ]

        # Определение длительности (если есть timestamp в сообщениях)
        duration_days = 0
        if conversation_history:
            # Попытка определить длительность по содержимому или использовать контекст
            # В реальности это можно улучшить, добавив timestamp в сообщения
            duration_days = max(1, total_messages // 20)  # Примерная оценка

        # Извлечение ключевых тем из сообщений пользователя
        user_content = " ".join([msg.get("content", "") for msg in user_messages])
        top_themes = self._extract_themes(user_content)

        # Определение тона
        tone = self._detect_tone(conversation_history)

        # Извлечение возражений
        objections = self._extract_objections(conversation_history)

        # Извлечение интересов
        interests = self._extract_interests(conversation_history)

        return {
            "total_messages": total_messages,
            "user_messages_count": len(user_messages),
            "assistant_messages_count": len(assistant_messages),
            "duration_days": duration_days,
            "top_themes": top_themes,
            "tone": tone,
            "objections": objections,
            "interests": interests,
        }

    def _extract_themes(self, text: str, max_themes: int = 3) -> List[str]:
        """Извлечь ключевые темы из текста."""
        # Простое извлечение ключевых слов/фраз
        # В реальности можно использовать LLM для более точного извлечения
        keywords = [
            "автоматизация",
            "обработка документов",
            "интеграция",
            "сокращение времени",
            "ошибки",
            "ручная работа",
            "AI",
            "машинное обучение",
            "чат-бот",
            "анализ",
            "прогнозирование",
            "распознавание",
        ]

        found_themes = []
        text_lower = text.lower()

        for keyword in keywords:
            if keyword in text_lower:
                found_themes.append(keyword)

        # Если тем мало, добавляем общие
        if len(found_themes) < max_themes:
            if "ai" in text_lower or "искусственный интеллект" in text_lower:
                found_themes.append("AI решения")
            if "автоматизация" in text_lower:
                found_themes.append("автоматизация процессов")

        return found_themes[:max_themes] if found_themes else ["обсуждение проекта"]

    def _detect_tone(self, conversation_history: List[Dict[str, str]]) -> str:
        """Определить тон общения (положительный/нейтральный/негативный)."""
        negative_keywords = [
            "дорого",
            "не нужно",
            "не интересно",
            "сомневаюсь",
            "проблема",
            "ошибка",
            "не работает",
        ]
        positive_keywords = [
            "интересно",
            "хорошо",
            "отлично",
            "давай",
            "хочу",
            "нужно",
            "помоги",
            "заинтересован",
        ]

        user_content = " ".join(
            [
                msg.get("content", "").lower()
                for msg in conversation_history
                if msg.get("role") == "user"
            ]
        )

        negative_count = sum(1 for word in negative_keywords if word in user_content)
        positive_count = sum(1 for word in positive_keywords if word in user_content)

        if negative_count > positive_count:
            return "негативный"
        elif positive_count > negative_count:
            return "положительный"
        else:
            return "нейтральный"

    def _extract_objections(self, conversation_history: List[Dict[str, str]]) -> List[str]:
        """Извлечь возражения из истории диалога."""
        objection_keywords = [
            "дорого",
            "не нужно",
            "не интересно",
            "сомневаюсь",
            "не уверен",
            "позже",
            "подумаю",
            "бюджет",
        ]

        objections = []
        user_content = " ".join(
            [
                msg.get("content", "")
                for msg in conversation_history
                if msg.get("role") == "user"
            ]
        )

        for keyword in objection_keywords:
            if keyword in user_content.lower():
                # Извлекаем предложение с возражением (упрощенно)
                sentences = user_content.split(".")
                for sentence in sentences:
                    if keyword in sentence.lower():
                        objections.append(sentence.strip())

        return objections[:3]  # Максимум 3 возражения

    def _extract_interests(self, conversation_history: List[Dict[str, str]]) -> List[str]:
        """Извлечь интересы клиента из истории диалога."""
        interest_keywords = [
            "хочу",
            "нужно",
            "интересно",
            "давай",
            "можно",
            "как",
            "что",
            "расскажи",
        ]

        interests = []
        user_content = " ".join(
            [
                msg.get("content", "")
                for msg in conversation_history
                if msg.get("role") == "user"
            ]
        )

        # Извлекаем вопросы и запросы
        sentences = user_content.split(".")
        for sentence in sentences:
            sentence_lower = sentence.lower()
            if any(keyword in sentence_lower for keyword in interest_keywords):
                if len(sentence.strip()) > 10:  # Только значимые предложения
                    interests.append(sentence.strip())

        return interests[:5]  # Максимум 5 интересов

    def generate_recommendations(
        self,
        slots: Dict[str, Any],
        conversation_analysis: Dict[str, Any],
        sales_stage: Optional[str] = None,
    ) -> List[str]:
        """
        Сформировать рекомендации для встречи на основе собранной информации.

        Args:
            slots: Словарь с заполненными слотами
            conversation_analysis: Результат analyze_conversation_history()
            sales_stage: Текущий этап продаж

        Returns:
            Список рекомендаций для встречи
        """
        recommendations = []

        # Рекомендации на основе проблем
        if slots.get("main_problems"):
            problems = str(slots["main_problems"])
            if "время" in problems.lower() or "часов" in problems.lower():
                recommendations.append(
                    "Акцент на ROI: показать экономию времени и сокращение затрат"
                )
            if "ошибк" in problems.lower() or "передел" in problems.lower():
                recommendations.append(
                    "Подготовить примеры повышения точности и снижения ошибок"
                )

        # Рекомендации на основе метрик
        if slots.get("current_time_cost"):
            recommendations.append(
                f"Обсудить конкретную экономию: {slots['current_time_cost']} можно автоматизировать"
            )

        if slots.get("error_rate"):
            recommendations.append(
                f"Показать как снизить уровень ошибок: {slots['error_rate']} → минимум"
            )

        # Рекомендации на основе возражений
        if conversation_analysis.get("objections"):
            if any("бюджет" in obj.lower() or "дорого" in obj.lower() for obj in conversation_analysis["objections"]):
                recommendations.append(
                    "Обсудить поэтапное внедрение и окупаемость инвестиций"
                )

        # Рекомендации на основе этапа продаж
        if sales_stage == "objections":
            recommendations.append(
                "Детально разобрать возражения и предложить варианты решения"
            )

        # Рекомендации на основе интеграций
        if slots.get("data_access") and "интеграц" in str(slots.get("data_access", "")).lower():
            recommendations.append(
                "Подготовить примеры интеграций с существующими системами"
            )

        # Общие рекомендации если мало конкретных
        if not recommendations:
            if slots.get("goal"):
                recommendations.append(
                    f"Сфокусироваться на цели проекта: {slots['goal']}"
                )
            recommendations.append(
                "Подготовить кейсы из похожих проектов в той же сфере"
            )

        return recommendations

    def generate_full_summary(
        self,
        slots: Dict[str, Any],
        conversation_history: List[Dict[str, str]],
        sales_stage: Optional[str] = None,
    ) -> str:
        """
        Сформировать полную сводку включая историю диалога и рекомендации.

        Args:
            slots: Словарь с заполненными слотами
            conversation_history: История диалога
            sales_stage: Текущий этап продаж

        Returns:
            Полная текстовую сводку
        """
        summary_parts = []

        # Базовая сводка из слотов
        base_summary = self.generate_summary(slots)
        summary_parts.append(base_summary)

        # Анализ истории диалога
        if conversation_history:
            analysis = self.analyze_conversation_history(conversation_history)
            summary_parts.append("\n=== ЧТО ОБСУЖДАЛОСЬ ===")
            summary_parts.append(f"Количество сообщений: {analysis['total_messages']}")
            if analysis["duration_days"] > 0:
                summary_parts.append(
                    f"Длительность диалога: {analysis['duration_days']} дней"
                )
            if analysis["top_themes"]:
                themes_text = ", ".join([f"«{theme}»" for theme in analysis["top_themes"]])
                summary_parts.append(f"Топ темы: {themes_text}")

            # Анализ возражений
            if analysis["objections"]:
                summary_parts.append("\n=== ВОЗРАЖЕНИЯ ===")
                for objection in analysis["objections"]:
                    summary_parts.append(f"• {objection}")

            # Интересы
            if analysis["interests"]:
                summary_parts.append("\n=== ИНТЕРЕСЫ ===")
                for interest in analysis["interests"][:3]:  # Максимум 3
                    summary_parts.append(f"• {interest}")

        # Рекомендации
        if conversation_history:
            analysis_for_recs = analysis if conversation_history else {}
            recommendations = self.generate_recommendations(
                slots, analysis_for_recs, sales_stage
            )
            if recommendations:
                summary_parts.append("\n=== РЕКОМЕНДОВАННЫЕ АКЦЕНТЫ ДЛЯ ВСТРЕЧИ ===")
                for rec in recommendations:
                    summary_parts.append(f"• {rec}")
        else:
            # Рекомендации без истории диалога
            recommendations = self.generate_recommendations(slots, {}, sales_stage)
            if recommendations:
                summary_parts.append("\n=== РЕКОМЕНДОВАННЫЕ АКЦЕНТЫ ДЛЯ ВСТРЕЧИ ===")
                for rec in recommendations:
                    summary_parts.append(f"• {rec}")

        return "\n".join(summary_parts)

    def generate_owner_report(
        self,
        client_name: Optional[str],
        slots: Dict[str, Any],
        conversation_history: List[Dict[str, str]],
        sales_stage: Optional[str] = None,
    ) -> str:
        """
        Сформировать отчет для владельца в структурированном формате.

        Args:
            client_name: Имя клиента
            slots: Словарь с заполненными слотами
            conversation_history: История диалога
            sales_stage: Текущий этап продаж

        Returns:
            Отчет в формате для владельца
        """
        report_parts = []

        # Заголовок
        client_display = client_name or slots.get("client_name") or "Клиент"
        report_parts.append(f"📊 Summary встречи с {client_display}\n")

        # Анализ истории
        if conversation_history:
            analysis = self.analyze_conversation_history(conversation_history)
            report_parts.append(f"— Количество сообщений: {analysis['total_messages']}")
            if analysis["duration_days"] > 0:
                report_parts.append(f"— Длительность диалога: {analysis['duration_days']} дней")

            # Топ темы
            if analysis["top_themes"]:
                themes_text = ", ".join([f"«{theme}»" for theme in analysis["top_themes"]])
                report_parts.append(f"— Топ-3 темы: {themes_text}")

        # Основные проблемы из слотов
        problems_list = []
        if slots.get("main_problems"):
            problems_list.append(slots["main_problems"])
        if slots.get("time_consuming_tasks"):
            problems_list.append(slots["time_consuming_tasks"])
        if slots.get("current_time_cost"):
            problems_list.append(f"временные затраты: {slots['current_time_cost']}")
        if slots.get("error_rate"):
            problems_list.append(f"уровень ошибок: {slots['error_rate']}")

        if problems_list:
            problems_text = ", ".join(problems_list[:3])  # Максимум 3
            report_parts.append(f"— Основные проблемы: {problems_text}")
        
        # Fit score (если доступен)
        if "fit_score" in slots or hasattr(self, "_last_fit_score"):
            fit_score = slots.get("fit_score") or getattr(self, "_last_fit_score", None)
            if fit_score is not None:
                report_parts.append(f"— Fit score: {fit_score}/100")

        # Тон общения
        if conversation_history:
            analysis = self.analyze_conversation_history(conversation_history)
            tone = analysis["tone"]
            tone_display = {
                "positive": "положительный (клиент заинтересован)",
                "положительный": "положительный (клиент заинтересован)",
                "negative": "негативный",
                "негативный": "негативный",
                "neutral": "нейтральный",
                "нейтральный": "нейтральный",
            }.get(tone, tone)
            report_parts.append(f"— Тон: {tone_display}")

        # Возражения
        if conversation_history:
            analysis = self.analyze_conversation_history(conversation_history)
            if analysis.get("objections"):
                objections_text = ", ".join(analysis["objections"][:2])  # Максимум 2
                report_parts.append(f"— Возражения: {objections_text}")
            elif sales_stage == "objections":
                report_parts.append("— Возражения: были обсуждены, готов рассмотреть варианты")

        # Рекомендации
        if conversation_history:
            analysis = self.analyze_conversation_history(conversation_history)
            recommendations = self.generate_recommendations(slots, analysis, sales_stage)
            if recommendations:
                report_parts.append("— Рекомендации для встречи:")
                for rec in recommendations:
                    report_parts.append(f"  • {rec}")
        
        # Проверка согласия на создание встречи
        if "consents" in slots or hasattr(self, "_check_consent"):
            # Если есть информация о согласиях, проверяем calendar_invite
            consents = slots.get("consents", {})
            if isinstance(consents, dict):
                calendar_consent = consents.get("calendar_invite", {})
                if isinstance(calendar_consent, dict) and not calendar_consent.get("granted", False):
                    report_parts.append("\n⚠️ Согласие на создание встречи не получено")
                    return "\n".join(report_parts)

        return "\n".join(report_parts)

