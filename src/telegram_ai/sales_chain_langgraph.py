"""LangGraph state machine для скрипта продаж."""

import json
import logging
from typing import Annotated, Any, Dict, Literal, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from .sales_flow import ObjectionType, SalesFlow, SalesStage

logger = logging.getLogger(__name__)


class SalesChainState(TypedDict):
    """State схема для LangGraph графа скрипта продаж."""

    stage: SalesStage  # Текущий этап
    slots: Dict[str, Any]  # Заполненные слоты
    context_data: Optional[str]  # JSON строка с контекстом пользователя
    message: str  # Сообщение пользователя
    intent: Optional[str]  # Тип намерения (SALES_AI, REAL_ESTATE, SMALL_TALK)
    objection_type: Optional[ObjectionType]  # Тип возражения (если на этапе OBJECTIONS)
    next_stage: Optional[SalesStage]  # Следующий этап (определяется узлами)


class SalesChainLangGraph:
    """LangGraph state machine для управления скриптом продаж."""

    def __init__(self, sales_flow: SalesFlow):
        """
        Инициализация LangGraph графа.

        Args:
            sales_flow: Экземпляр SalesFlow для использования существующих методов
        """
        self.sales_flow = sales_flow
        self.graph = self._build_graph()
        logger.info("SalesChainLangGraph initialized")

    def _build_graph(self) -> StateGraph:
        """Построить LangGraph граф с узлами для каждого этапа."""
        workflow = StateGraph(SalesChainState)

        # Добавляем узлы для каждого этапа
        workflow.add_node("greeting", self._greeting_node)
        workflow.add_node("needs_discovery", self._needs_discovery_node)
        workflow.add_node("presentation", self._presentation_node)
        workflow.add_node("objections", self._objections_node)
        workflow.add_node("consultation_offer", self._consultation_offer_node)
        workflow.add_node("scheduling", self._scheduling_node)
        workflow.add_node("summary", self._summary_node)

        # Начальный узел будет определяться динамически в process_message
        # Используем условный entry point через START -> текущий этап
        workflow.add_conditional_edges(
            START,
            self._route_from_start,
            {
                "greeting": "greeting",
                "needs_discovery": "needs_discovery",
                "presentation": "presentation",
                "objections": "objections",
                "consultation_offer": "consultation_offer",
                "scheduling": "scheduling",
                "summary": "summary",
            },
        )

        # Добавляем условные переходы между узлами
        workflow.add_conditional_edges(
            "greeting",
            self._route_from_greeting,
            {
                "needs_discovery": "needs_discovery",
                "presentation": "presentation",
                "end": END,
            },
        )

        workflow.add_conditional_edges(
            "needs_discovery",
            self._route_from_needs_discovery,
            {
                "presentation": "presentation",
                "objections": "objections",
                "consultation_offer": "consultation_offer",
                "end": END,
            },
        )

        workflow.add_conditional_edges(
            "presentation",
            self._route_from_presentation,
            {
                "objections": "objections",
                "consultation_offer": "consultation_offer",
                "scheduling": "scheduling",
                "end": END,
            },
        )

        workflow.add_conditional_edges(
            "objections",
            self._route_from_objections,
            {
                "consultation_offer": "consultation_offer",
                "scheduling": "scheduling",
                "end": END,
            },
        )

        workflow.add_conditional_edges(
            "consultation_offer",
            self._route_from_consultation_offer,
            {
                "scheduling": "scheduling",
                "end": END,
            },
        )

        workflow.add_conditional_edges(
            "scheduling",
            self._route_from_scheduling,
            {
                "summary": "summary",
                "end": END,
            },
        )

        workflow.add_edge("summary", END)

        return workflow.compile()

    async def _greeting_node(self, state: SalesChainState) -> SalesChainState:
        """Узел для этапа GREETING."""
        logger.debug("Processing GREETING stage")
        # Используем существующий метод SalesFlow для определения перехода
        next_stage = self.sales_flow.detect_stage_transition(
            state["message"], SalesStage.GREETING, is_first_message=True
        )
        state["next_stage"] = next_stage
        state["stage"] = SalesStage.GREETING
        return state

    async def _needs_discovery_node(self, state: SalesChainState) -> SalesChainState:
        """Узел для этапа NEEDS_DISCOVERY."""
        logger.debug("Processing NEEDS_DISCOVERY stage")
        # Автоматически извлекаем слоты если доступен slot_extractor
        if self.sales_flow.slot_extractor and self.sales_flow.slot_extractor.enabled:
            # Обновляем контекст с извлеченными слотами
            state["context_data"] = await self.sales_flow.auto_extract_slots(
                state["message"], state["context_data"], state["intent"]
            )

        # Определяем следующий этап
        next_stage = self.sales_flow.detect_stage_transition(
            state["message"], SalesStage.NEEDS_DISCOVERY, is_first_message=False
        )
        state["next_stage"] = next_stage
        state["stage"] = SalesStage.NEEDS_DISCOVERY
        return state

    async def _presentation_node(self, state: SalesChainState) -> SalesChainState:
        """Узел для этапа PRESENTATION."""
        logger.debug("Processing PRESENTATION stage")
        next_stage = self.sales_flow.detect_stage_transition(
            state["message"], SalesStage.PRESENTATION, is_first_message=False
        )
        state["next_stage"] = next_stage
        state["stage"] = SalesStage.PRESENTATION
        return state

    async def _objections_node(self, state: SalesChainState) -> SalesChainState:
        """Узел для этапа OBJECTIONS."""
        logger.debug("Processing OBJECTIONS stage")
        # Классифицируем возражение
        objection_type = await self.sales_flow.classify_objection(state["message"])

        state["objection_type"] = objection_type

        # Добавляем возражение в историю
        state["context_data"] = self.sales_flow.add_objection_to_history(
            state["context_data"], objection_type, state["message"]
        )

        # Определяем следующий этап
        next_stage = self.sales_flow.detect_stage_transition(
            state["message"], SalesStage.OBJECTIONS, is_first_message=False
        )
        state["next_stage"] = next_stage
        state["stage"] = SalesStage.OBJECTIONS
        return state

    async def _consultation_offer_node(self, state: SalesChainState) -> SalesChainState:
        """Узел для этапа CONSULTATION_OFFER."""
        logger.debug("Processing CONSULTATION_OFFER stage")
        next_stage = self.sales_flow.detect_stage_transition(
            state["message"], SalesStage.CONSULTATION_OFFER, is_first_message=False
        )
        state["next_stage"] = next_stage
        state["stage"] = SalesStage.CONSULTATION_OFFER
        return state

    async def _scheduling_node(self, state: SalesChainState) -> SalesChainState:
        """Узел для этапа SCHEDULING."""
        logger.debug("Processing SCHEDULING stage")
        # Проверяем, нужно ли перейти на SUMMARY (все слоты заполнены)
        if self.sales_flow.should_transition_to_summary(
            state["context_data"], state["intent"]
        ):
            state["next_stage"] = SalesStage.SUMMARY
        else:
            state["next_stage"] = None
        state["stage"] = SalesStage.SCHEDULING
        return state

    async def _summary_node(self, state: SalesChainState) -> SalesChainState:
        """Узел для этапа SUMMARY."""
        logger.debug("Processing SUMMARY stage")
        state["next_stage"] = None
        state["stage"] = SalesStage.SUMMARY
        return state

    def _route_from_start(self, state: SalesChainState) -> str:
        """Маршрутизация из START на основе текущего этапа."""
        current_stage = state.get("stage", SalesStage.GREETING)
        stage_to_node = {
            SalesStage.GREETING: "greeting",
            SalesStage.NEEDS_DISCOVERY: "needs_discovery",
            SalesStage.PRESENTATION: "presentation",
            SalesStage.OBJECTIONS: "objections",
            SalesStage.CONSULTATION_OFFER: "consultation_offer",
            SalesStage.SCHEDULING: "scheduling",
            SalesStage.SUMMARY: "summary",
        }
        return stage_to_node.get(current_stage, "greeting")

    def _route_from_greeting(self, state: SalesChainState) -> str:
        """Маршрутизация из GREETING."""
        next_stage = state.get("next_stage")
        if next_stage == SalesStage.NEEDS_DISCOVERY:
            return "needs_discovery"
        elif next_stage == SalesStage.PRESENTATION:
            return "presentation"
        else:
            return "end"

    def _route_from_needs_discovery(self, state: SalesChainState) -> str:
        """Маршрутизация из NEEDS_DISCOVERY."""
        next_stage = state.get("next_stage")
        if next_stage == SalesStage.PRESENTATION:
            return "presentation"
        elif next_stage == SalesStage.OBJECTIONS:
            return "objections"
        elif next_stage == SalesStage.CONSULTATION_OFFER:
            return "consultation_offer"
        else:
            return "end"

    def _route_from_presentation(self, state: SalesChainState) -> str:
        """Маршрутизация из PRESENTATION."""
        next_stage = state.get("next_stage")
        if next_stage == SalesStage.OBJECTIONS:
            return "objections"
        elif next_stage == SalesStage.CONSULTATION_OFFER:
            return "consultation_offer"
        elif next_stage == SalesStage.SCHEDULING:
            return "scheduling"
        else:
            return "end"

    def _route_from_objections(self, state: SalesChainState) -> str:
        """Маршрутизация из OBJECTIONS."""
        next_stage = state.get("next_stage")
        if next_stage == SalesStage.CONSULTATION_OFFER:
            return "consultation_offer"
        elif next_stage == SalesStage.SCHEDULING:
            return "scheduling"
        else:
            return "end"

    def _route_from_consultation_offer(self, state: SalesChainState) -> str:
        """Маршрутизация из CONSULTATION_OFFER."""
        next_stage = state.get("next_stage")
        if next_stage == SalesStage.SCHEDULING:
            return "scheduling"
        else:
            return "end"

    def _route_from_scheduling(self, state: SalesChainState) -> str:
        """Маршрутизация из SCHEDULING."""
        next_stage = state.get("next_stage")
        if next_stage == SalesStage.SUMMARY:
            return "summary"
        else:
            return "end"

    async def process_message(
        self, message: str, context_data: Optional[str], intent: Optional[str] = None, is_first_message: bool = False
    ) -> Dict[str, Any]:
        """
        Обработать сообщение через LangGraph граф.

        Args:
            message: Сообщение пользователя
            context_data: JSON строка с контекстом пользователя
            intent: Тип намерения (SALES_AI, REAL_ESTATE, SMALL_TALK)
            is_first_message: Является ли это первым сообщением в разговоре

        Returns:
            Словарь с результатами обработки:
            {
                "stage": SalesStage,
                "context_data": str,
                "objection_type": Optional[ObjectionType],
                "next_stage": Optional[SalesStage],
                ...
            }
        """
        # Определяем текущий этап из контекста
        current_stage = self.sales_flow.get_stage(context_data)
        if not current_stage:
            current_stage = SalesStage.GREETING

        # Получаем слоты из контекста
        slots = self.sales_flow.get_slots(context_data)

        # Создаем начальное состояние
        initial_state: SalesChainState = {
            "stage": current_stage,
            "slots": slots,
            "context_data": context_data,
            "message": message,
            "intent": intent,
            "objection_type": None,
            "next_stage": None,
        }

        # Запускаем граф - он начнет с текущего этапа благодаря _route_from_start
        try:
            final_state = await self.graph.ainvoke(initial_state)
            logger.debug(f"LangGraph processed: {current_stage.value} -> {final_state.get('next_stage', 'no change')}")
        except Exception as e:
            logger.error(f"Error processing message through LangGraph: {e}", exc_info=True)
            # Fallback: используем простую state machine
            next_stage = self.sales_flow.detect_stage_transition(
                message, current_stage, is_first_message=is_first_message
            )
            if next_stage:
                final_state = {
                    "stage": next_stage,
                    "context_data": self.sales_flow.update_stage(context_data, next_stage),
                    "slots": slots,
                    "message": message,
                    "intent": intent,
                    "objection_type": None,
                    "next_stage": next_stage,
                }
            else:
                final_state = {
                    **initial_state,
                    "next_stage": None,
                }

        # Обновляем контекст с новым этапом если он изменился
        if final_state.get("next_stage") and final_state["next_stage"] != current_stage:
            final_state["context_data"] = self.sales_flow.update_stage(
                final_state.get("context_data", context_data), final_state["next_stage"]
            )

        return final_state

