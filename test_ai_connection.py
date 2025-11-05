"""Скрипт для тестирования подключения к AI серверу."""

import asyncio
import logging
from src.telegram_ai.ai_client import AIClient
from src.telegram_ai.config import Config

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

async def test_ai_connection():
    """Тест подключения к AI серверу."""
    print("🔍 Тестирование подключения к AI серверу...")
    
    # Загружаем конфигурацию
    config = Config.from_yaml("config.yaml")
    
    # Создаем AI клиент
    client = AIClient(
        base_url=config.ai_server.base_url,
        model=config.ai_server.model,
        api_key=config.ai_server.api_key,
        timeout=config.ai_server.timeout,
        max_retries=config.ai_server.max_retries,
        max_tokens=config.ai_server.max_tokens,
    )
    
    print(f"📡 Подключение к: {config.ai_server.base_url}")
    print(f"🤖 Модель: {config.ai_server.model}")
    print()
    
    # Тестовое сообщение
    test_messages = [
        {"role": "user", "content": "Привет! Как дела?"}
    ]
    
    try:
        print("📤 Отправка тестового сообщения...")
        response = await client.get_response(test_messages)
        print(f"✅ Ответ получен:")
        print(f"   {response}")
        print()
        print("✅ Подключение работает!")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(test_ai_connection())

