#!/usr/bin/env python3
"""Утилита для сброса блокировок rate limiting."""

import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.telegram_ai.config import Config
from src.telegram_ai.memory import Memory, RateLimit, GlobalRateLimit


def reset_user_blocks(user_id: int = None):
    """Сбросить блокировки для пользователя или всех пользователей."""
    config_path = Path(__file__).parent.parent / "config.yaml"
    config = Config.from_yaml(str(config_path))
    
    memory = Memory(
        db_path=config.memory.db_path,
        context_window=config.memory.context_window,
        max_history_days=config.memory.max_history_days,
    )
    
    session = memory.SessionLocal()
    try:
        if user_id:
            rate_limit = session.query(RateLimit).filter(RateLimit.user_id == user_id).first()
            if rate_limit:
                rate_limit.blocked_until = None
                rate_limit.message_count_minute = 0
                rate_limit.message_count_hour = 0
                rate_limit.repeated_messages = 0
                session.commit()
                print(f"✅ Сброшена блокировка для пользователя {user_id}")
            else:
                print(f"ℹ️  Пользователь {user_id} не найден или не заблокирован")
        else:
            # Сбрасываем все блокировки
            blocked_users = session.query(RateLimit).filter(RateLimit.blocked_until != None).all()
            count = 0
            for rate_limit in blocked_users:
                rate_limit.blocked_until = None
                rate_limit.message_count_minute = 0
                rate_limit.message_count_hour = 0
                rate_limit.repeated_messages = 0
                count += 1
            session.commit()
            print(f"✅ Сброшено блокировок: {count}")
    finally:
        session.close()


def reset_global_block():
    """Сбросить глобальную блокировку."""
    config_path = Path(__file__).parent.parent / "config.yaml"
    config = Config.from_yaml(str(config_path))
    
    memory = Memory(
        db_path=config.memory.db_path,
        context_window=config.memory.context_window,
        max_history_days=config.memory.max_history_days,
    )
    
    session = memory.SessionLocal()
    try:
        global_limit = session.query(GlobalRateLimit).filter(GlobalRateLimit.id == 1).first()
        if global_limit and global_limit.blocked_until:
            global_limit.blocked_until = None
            global_limit.message_count_minute = 0
            global_limit.message_count_hour = 0
            session.commit()
            print("✅ Сброшена глобальная блокировка")
        else:
            print("ℹ️  Глобальная блокировка не найдена или не активна")
    finally:
        session.close()


def show_status():
    """Показать текущий статус блокировок."""
    config_path = Path(__file__).parent.parent / "config.yaml"
    config = Config.from_yaml(str(config_path))
    
    memory = Memory(
        db_path=config.memory.db_path,
        context_window=config.memory.context_window,
        max_history_days=config.memory.max_history_days,
    )
    
    session = memory.SessionLocal()
    try:
        from datetime import datetime, timezone
        
        # Проверяем глобальную блокировку
        global_limit = session.query(GlobalRateLimit).filter(GlobalRateLimit.id == 1).first()
        if global_limit and global_limit.blocked_until:
            now = datetime.now(timezone.utc)
            blocked_until = global_limit.blocked_until
            if blocked_until.tzinfo is None:
                blocked_until = blocked_until.replace(tzinfo=timezone.utc)
            if blocked_until > now:
                remaining = int((blocked_until - now).total_seconds() / 60) + 1
                print(f"⚠️  Глобальная блокировка активна: осталось {remaining} минут")
            else:
                print("✅ Глобальная блокировка не активна")
        else:
            print("✅ Глобальная блокировка не активна")
        
        # Проверяем пользовательские блокировки
        blocked_users = session.query(RateLimit).filter(RateLimit.blocked_until != None).all()
        if blocked_users:
            now = datetime.now(timezone.utc)
            active_blocks = []
            for rate_limit in blocked_users:
                blocked_until = rate_limit.blocked_until
                if blocked_until.tzinfo is None:
                    blocked_until = blocked_until.replace(tzinfo=timezone.utc)
                if blocked_until > now:
                    remaining = int((blocked_until - now).total_seconds() / 60) + 1
                    active_blocks.append((rate_limit.user_id, remaining))
            
            if active_blocks:
                print(f"\n⚠️  Активные блокировки пользователей:")
                for user_id, remaining in active_blocks:
                    print(f"   - Пользователь {user_id}: осталось {remaining} минут")
            else:
                print("\n✅ Активных блокировок пользователей нет")
        else:
            print("\n✅ Активных блокировок пользователей нет")
    finally:
        session.close()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        command = sys.argv[1]
        if command == "reset-all":
            reset_user_blocks()
            reset_global_block()
        elif command == "reset-global":
            reset_global_block()
        elif command == "reset-user" and len(sys.argv) > 2:
            user_id = int(sys.argv[2])
            reset_user_blocks(user_id)
        elif command == "status":
            show_status()
        else:
            print("Использование:")
            print("  python scripts/reset_rate_limits.py status          - показать статус блокировок")
            print("  python scripts/reset_rate_limits.py reset-all        - сбросить все блокировки")
            print("  python scripts/reset_rate_limits.py reset-global    - сбросить глобальную блокировку")
            print("  python scripts/reset_rate_limits.py reset-user ID  - сбросить блокировку пользователя")
    else:
        show_status()

