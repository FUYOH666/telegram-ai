"""LangChain цепочка для скрипта продаж (будет реализована с LangGraph)."""

from typing import Dict, Any, Optional

logger = None  # Будет инициализирован при использовании


class SalesChain:
    """LangChain цепочка для управления скриптом продаж."""

    def __init__(self, ai_client, sales_flow):
        """
        Инициализация Sales Chain.

        Args:
            ai_client: Клиент для AI сервера
            sales_flow: Экземпляр SalesFlow для управления этапами
        """
        self.ai_client = ai_client
        self.sales_flow = sales_flow
        # TODO: Реализовать LangGraph state machine для sales flow

    async def process_message(self, message: str, context: Dict[str, Any]) -> str:
        """
        Обработать сообщение через sales chain.

        Args:
            message: Сообщение пользователя
            context: Контекст диалога

        Returns:
            Ответ бота
        """
        # Временная реализация - будет заменена на LangGraph
        # Используем существующий sales_flow для обратной совместимости
        return "Sales chain будет реализована с LangGraph"

