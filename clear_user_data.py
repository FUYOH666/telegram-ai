#!/usr/bin/env python3
"""Скрипт для очистки всех данных пользователя из базы данных.

Использование:
    python clear_user_data.py <user_id>
    
Пример:
    python clear_user_data.py 123456789
"""

import sys
from pathlib import Path

# Добавляем src в путь для импорта
sys.path.insert(0, str(Path(__file__).parent / "src"))

from telegram_ai.config import Config
from telegram_ai.memory import Memory


def list_users():
    """Показать список всех пользователей в базе данных."""
    config_path = Path(__file__).parent / "config.yaml"
    config = Config.from_yaml(str(config_path))
    
    memory = Memory(
        db_path=config.memory.db_path,
        context_window=config.memory.context_window,
        max_history_days=config.memory.max_history_days,
    )
    
    session = memory._get_session()
    try:
        from telegram_ai.memory import Conversation, Message
        
        conversations = session.query(Conversation).all()
        
        if not conversations:
            print("В базе данных нет пользователей.")
            return
        
        print("\nПользователи в базе данных:")
        print("-" * 60)
        for conv in conversations:
            messages_count = (
                session.query(Message)
                .filter(Message.conversation_id == conv.id)
                .count()
            )
            print(f"User ID: {conv.user_id}")
            print(f"  Username: {conv.username or 'N/A'}")
            print(f"  Messages: {messages_count}")
            print(f"  Created: {conv.created_at}")
            print()
    finally:
        session.close()


def clear_user_data(user_id: int):
    """Очистить все данные пользователя."""
    config_path = Path(__file__).parent / "config.yaml"
    config = Config.from_yaml(str(config_path))
    
    memory = Memory(
        db_path=config.memory.db_path,
        context_window=config.memory.context_window,
        max_history_days=config.memory.max_history_days,
    )
    
    print(f"\n🧹 Очистка данных для user_id={user_id}...")
    
    deleted_counts = memory.delete_user_data(user_id)
    
    print("\n✅ Данные успешно удалены:")
    print(f"  Сообщений: {deleted_counts['messages']}")
    print(f"  Разговоров: {deleted_counts['conversations']}")
    print(f"  Контекстов: {deleted_counts['user_context']}")
    print(f"  Rate limit записей: {deleted_counts['rate_limits']}")
    print("\n💡 Теперь диалог с этим пользователем начнется с чистого листа.")


def main():
    """Главная функция."""
    if len(sys.argv) < 2:
        print("Использование:")
        print("  python clear_user_data.py <user_id>  - очистить данные пользователя")
        print("  python clear_user_data.py --list     - показать список пользователей")
        sys.exit(1)
    
    if sys.argv[1] == "--list":
        list_users()
        return
    
    try:
        user_id = int(sys.argv[1])
    except ValueError:
        print(f"❌ Ошибка: '{sys.argv[1]}' не является валидным user_id (должно быть число)")
        sys.exit(1)
    
    # Подтверждение
    print(f"\n⚠️  ВНИМАНИЕ: Вы собираетесь удалить ВСЕ данные для user_id={user_id}")
    print("   Это включает:")
    print("   - Все сообщения")
    print("   - Историю разговора")
    print("   - Контекст пользователя")
    print("   - Rate limit записи")
    print("\n   Это действие нельзя отменить!")
    
    confirm = input("\nПродолжить? (yes/no): ").strip().lower()
    if confirm not in ("yes", "y", "да", "д"):
        print("Отменено.")
        sys.exit(0)
    
    clear_user_data(user_id)


if __name__ == "__main__":
    main()

