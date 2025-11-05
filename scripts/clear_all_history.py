#!/usr/bin/env python3
"""Утилита для полной очистки истории всех собеседников."""

import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.telegram_ai.config import Config
from src.telegram_ai.memory import (
    Memory,
    Conversation,
    Message,
    UserContext,
    RateLimit,
    ConversationSummary,
    GlobalRateLimit,
    FloodWaitHistory,
)


def clear_all_history(confirm: bool = False):
    """
    Очистить всю историю всех собеседников.
    
    Args:
        confirm: Если False, требует подтверждения перед очисткой
    """
    config_path = Path(__file__).parent.parent / "config.yaml"
    config = Config.from_yaml(str(config_path))
    
    memory = Memory(
        db_path=config.memory.db_path,
        context_window=config.memory.context_window,
        max_history_days=config.memory.max_history_days,
    )
    
    session = memory.SessionLocal()
    try:
        # Собираем статистику перед удалением
        conversations_count = session.query(Conversation).count()
        messages_count = session.query(Message).count()
        user_contexts_count = session.query(UserContext).count()
        rate_limits_count = session.query(RateLimit).count()
        summaries_count = session.query(ConversationSummary).count()
        flood_wait_count = session.query(FloodWaitHistory).count()
        
        print("\n📊 Текущая статистика БД:")
        print(f"   - Разговоров: {conversations_count}")
        print(f"   - Сообщений: {messages_count}")
        print(f"   - Контекстов пользователей: {user_contexts_count}")
        print(f"   - Rate limit записей: {rate_limits_count}")
        print(f"   - Резюме разговоров: {summaries_count}")
        print(f"   - Записей FloodWait: {flood_wait_count}")
        
        if not confirm:
            print("\n⚠️  ВНИМАНИЕ: Это действие удалит ВСЮ историю всех собеседников!")
            print("   После очистки они будут общаться с ботом как с нуля.")
            response = input("\n❓ Продолжить? (yes/no): ").strip().lower()
            if response not in ("yes", "y", "да", "д"):
                print("❌ Очистка отменена.")
                return
        
        print("\n🗑️  Начинаю очистку...")
        
        # Удаляем в правильном порядке (сначала зависимые таблицы)
        deleted_messages = session.query(Message).delete()
        deleted_summaries = session.query(ConversationSummary).delete()
        deleted_conversations = session.query(Conversation).delete()
        deleted_contexts = session.query(UserContext).delete()
        deleted_rate_limits = session.query(RateLimit).delete()
        deleted_flood_wait = session.query(FloodWaitHistory).delete()
        
        # Сбрасываем глобальный rate limit (но не удаляем запись)
        global_limit = session.query(GlobalRateLimit).filter(GlobalRateLimit.id == 1).first()
        if global_limit:
            global_limit.message_count_minute = 0
            global_limit.message_count_hour = 0
            global_limit.blocked_until = None
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            global_limit.window_start_minute = now
            global_limit.window_start_hour = now
            global_limit.last_message_time = now
        
        session.commit()
        
        print("\n✅ Очистка завершена:")
        print(f"   - Удалено сообщений: {deleted_messages}")
        print(f"   - Удалено резюме: {deleted_summaries}")
        print(f"   - Удалено разговоров: {deleted_conversations}")
        print(f"   - Удалено контекстов: {deleted_contexts}")
        print(f"   - Удалено rate limit записей: {deleted_rate_limits}")
        print(f"   - Удалено записей FloodWait: {deleted_flood_wait}")
        print(f"   - Глобальный rate limit сброшен")
        print("\n✨ Теперь все собеседники будут общаться с ботом как с нуля!")
        
    except Exception as e:
        session.rollback()
        print(f"\n❌ Ошибка при очистке: {e}")
        raise
    finally:
        session.close()
        memory.close()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--yes":
        clear_all_history(confirm=True)
    else:
        clear_all_history(confirm=False)

