"""Точка входа в приложение."""

import asyncio
import logging
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import httpx

from .config import Config

# Создаем директорию для логов
logs_dir = Path("logs")
logs_dir.mkdir(exist_ok=True)

# Имя файла лога с датой
log_file = logs_dir / f"telegram-ai-{datetime.now().strftime('%Y%m%d')}.log"

# Настройка логирования - и в консоль, и в файл
logging.basicConfig(
    level=logging.DEBUG,  # DEBUG для детального логирования
    format="%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),  # Консоль
        logging.FileHandler(log_file, encoding="utf-8"),  # Файл
    ],
)

logger = logging.getLogger(__name__)
logger.info(f"Logging initialized. Log file: {log_file}")


async def main():
    """Основная функция приложения."""
    try:
        # Загружаем конфигурацию
        config_path = Path(__file__).parent.parent.parent / "config.yaml"
        config = Config.from_yaml(str(config_path))

        # Валидируем конфигурацию
        config.validate()

        # Проверяем доступность AI сервера
        try:
            await config.validate_ai_server()
        except ValueError as e:
            logger.error(f"AI server validation failed: {e}")
            print(f"\n❌ Ошибка проверки AI сервера:\n{e}\n")
            sys.exit(1)
        except Exception as e:
            logger.warning(f"Could not validate AI server (non-critical): {e}")

        # Проверяем, не запущен ли уже другой экземпляр
        import subprocess
        try:
            result = subprocess.run(
                ["ps", "aux"],
                capture_output=True,
                text=True,
                timeout=2.0,
            )
            if result.returncode == 0:
                # Ищем процессы, связанные с telegram-ai, но исключаем текущий процесс
                lines = result.stdout.split("\n")
                telegram_ai_processes = [
                    line for line in lines
                    if "telegram-ai" in line.lower() or "src.telegram_ai.main" in line
                    if str(os.getpid()) not in line  # Исключаем текущий процесс
                ]
                if len(telegram_ai_processes) > 0:
                    logger.warning(
                        f"Found {len(telegram_ai_processes)} potentially running instance(s). "
                        "If you get 'database is locked' error, stop other instances first."
                    )
        except Exception as e:
            # Игнорируем ошибки проверки процессов (может не работать на всех системах)
            logger.debug(f"Could not check for running instances: {e}")

        logger.info("Starting Telegram AI Assistant...")

        # Импортируем клиент здесь чтобы избежать циклических импортов
        from .client import TelegramUserClient

        # Создаем и запускаем клиент
        client = TelegramUserClient(config)
        await client.run()

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(0)
    except sqlite3.OperationalError as e:
        if "database is locked" in str(e).lower():
            logger.error(
                "Database is locked. This usually means:\n"
                "  1. Another instance of the application is already running\n"
                "  2. A previous instance didn't close properly\n"
                "\n"
                "Solutions:\n"
                "  - Check if another instance is running: ps aux | grep telegram-ai\n"
                "  - Kill the other instance: kill <PID>\n"
                "  - Or wait a few seconds and try again"
            )
            print(
                "\n❌ Ошибка: База данных заблокирована.\n"
                "   Вероятно, уже запущен другой экземпляр приложения.\n"
                "   Проверьте: ps aux | grep telegram-ai\n"
                "   Или подождите несколько секунд и попробуйте снова.\n"
            )
        else:
            logger.error(f"SQLite error: {e}", exc_info=True)
            print(f"\n❌ Ошибка базы данных: {e}\n")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


async def health_check():
    """Health check команда для диагностики."""
    print("🔍 Проверка состояния Telegram AI Assistant...\n")
    
    issues = []
    checks = []
    
    # Версия приложения
    try:
        import importlib.metadata
        try:
            version = importlib.metadata.version("telegram-ai")
        except importlib.metadata.PackageNotFoundError:
            # Если пакет не установлен, читаем из pyproject.toml
            try:
                import tomli
            except ImportError:
                try:
                    import tomli_w as tomli
                except ImportError:
                    tomli = None
            
            if tomli:
                pyproject_path = Path(__file__).parent.parent.parent / "pyproject.toml"
                if pyproject_path.exists():
                    with open(pyproject_path, "rb") as f:
                        pyproject = tomli.load(f)
                        version = pyproject.get("project", {}).get("version", "unknown")
                else:
                    version = "unknown"
            else:
                # Fallback: читаем как текст
                pyproject_path = Path(__file__).parent.parent.parent / "pyproject.toml"
                if pyproject_path.exists():
                    import re
                    content = pyproject_path.read_text()
                    match = re.search(r'version\s*=\s*"([^"]+)"', content)
                    version = match.group(1) if match else "unknown"
                else:
                    version = "unknown"
        checks.append(f"✅ Версия приложения: {version}")
    except Exception as e:
        issues.append(f"❌ Не удалось определить версию: {e}")
    
    # Версия Python
    checks.append(f"✅ Python: {sys.version.split()[0]}")
    
    # Конфигурация
    try:
        config_path = Path(__file__).parent.parent.parent / "config.yaml"
        config = Config.from_yaml(str(config_path))
        config.validate()
        checks.append("✅ Конфигурация валидна")
    except Exception as e:
        issues.append(f"❌ Ошибка конфигурации: {e}")
        print("\n".join(checks))
        print("\n".join(issues))
        sys.exit(1)
    
    # Проверка AI сервера
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                response = await client.get(f"{config.ai_server.base_url}/health")
                if response.status_code == 200:
                    checks.append(f"✅ AI сервер доступен: {config.ai_server.base_url}")
                else:
                    issues.append(f"⚠️  AI сервер вернул статус {response.status_code}")
            except httpx.TimeoutException:
                issues.append(f"❌ AI сервер недоступен (таймаут): {config.ai_server.base_url}")
            except Exception as e:
                issues.append(f"❌ AI сервер недоступен: {e}")
    except Exception as e:
        issues.append(f"❌ Ошибка проверки AI сервера: {e}")
    
    # Проверка ASR сервера (если включен)
    if config.asr_server.enabled:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Проверяем доступность ASR сервера через эндпоинт /transcribe
                # Сервер должен отвечать даже на пустой POST (422 = Unprocessable Entity означает что сервер работает)
                asr_checked = False
                try:
                    # Пробуем POST на /transcribe без файла - должен вернуть 422 (сервер работает, но нет файла)
                    response = await client.post(f"{config.asr_server.base_url}/transcribe")
                    if response.status_code == 422:
                        # 422 = Unprocessable Entity - сервер работает, но требует файл
                        checks.append(f"✅ ASR сервер доступен: {config.asr_server.base_url} (эндпоинт /transcribe работает)")
                        asr_checked = True
                    elif response.status_code in (200, 404, 405):
                        checks.append(f"✅ ASR сервер доступен: {config.asr_server.base_url} (статус {response.status_code})")
                        asr_checked = True
                except httpx.TimeoutException:
                    pass
                except Exception:
                    pass
                
                # Если POST не сработал, пробуем GET на разные эндпоинты
                if not asr_checked:
                    for endpoint in ["/health", "/", "/transcribe"]:
                        try:
                            response = await client.get(f"{config.asr_server.base_url}{endpoint}")
                            if response.status_code in (200, 404, 405):  # 405 = Method Not Allowed (сервер есть, но GET не поддерживается)
                                checks.append(f"✅ ASR сервер доступен: {config.asr_server.base_url} (проверен через {endpoint})")
                                asr_checked = True
                                break
                        except httpx.TimeoutException:
                            continue
                        except Exception:
                            continue
                
                if not asr_checked:
                    # Если ничего не сработало, проверяем базовое подключение
                    try:
                        response = await client.get(f"{config.asr_server.base_url}/", timeout=5.0)
                        if response.status_code in (200, 404):
                            checks.append(f"✅ ASR сервер доступен: {config.asr_server.base_url} (сервер отвечает)")
                        else:
                            issues.append(f"⚠️  ASR сервер вернул статус {response.status_code}")
                    except httpx.TimeoutException:
                        issues.append(f"❌ ASR сервер недоступен (таймаут): {config.asr_server.base_url}")
                    except httpx.ConnectError:
                        issues.append(f"❌ ASR сервер недоступен (не удалось подключиться): {config.asr_server.base_url}")
                    except Exception as e:
                        issues.append(f"⚠️  ASR сервер: {e}")
        except Exception as e:
            issues.append(f"❌ Ошибка проверки ASR сервера: {e}")
    else:
        checks.append("⏭️  ASR сервер отключен")
    
    # Проверка БД
    db_path = Path(config.memory.db_path)
    if db_path.exists():
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM messages")
            count = cursor.fetchone()[0]
            conn.close()
            checks.append(f"✅ SQLite БД доступна: {count} сообщений")
        except Exception as e:
            issues.append(f"❌ Ошибка доступа к БД: {e}")
    else:
        checks.append("ℹ️  SQLite БД будет создана при первом запуске")
    
    # Проверка ChromaDB (если включен)
    if config.memory.vector_search_enabled:
        chroma_path = Path(config.memory.vector_db_path)
        if chroma_path.exists():
            checks.append(f"✅ ChromaDB доступна: {chroma_path}")
        else:
            checks.append("ℹ️  ChromaDB будет создана при первом запуске")
    else:
        checks.append("⏭️  Векторный поиск отключен")
    
    # Проверка Google Calendar (если включен)
    if config.google_calendar.enabled:
        creds_path = Path(config.google_calendar.credentials_path)
        if creds_path.exists():
            checks.append(f"✅ Google Calendar credentials найдены: {creds_path}")
        else:
            issues.append(f"⚠️  Google Calendar включен, но credentials не найдены: {creds_path}")
    else:
        checks.append("⏭️  Google Calendar отключен")
    
    # Проверка RAG (если включен)
    if config.rag.enabled:
        rag_path = Path(config.rag.knowledge_base_path)
        if rag_path.exists():
            md_files = list(rag_path.rglob("*.md"))
            txt_files = list(rag_path.rglob("*.txt"))
            total = len(md_files) + len(txt_files)
            checks.append(f"✅ RAG база знаний: {total} файлов в {rag_path}")
        else:
            issues.append(f"⚠️  RAG включен, но база знаний не найдена: {rag_path}")
    else:
        checks.append("⏭️  RAG система отключена")
    
    # Проверка Web Search (если включен)
    if config.web_search.enabled:
        checks.append(f"✅ Web Search включен: {config.web_search.mcp_server_url}")
    else:
        checks.append("⏭️  Web Search отключен")
    
    # Проверка сессии Telegram
    session_path = Path(config.telegram.session_path)
    if session_path.exists():
        checks.append(f"✅ Telegram сессия найдена: {session_path}")
    else:
        checks.append("ℹ️  Telegram сессия будет создана при первом запуске")
    
    # Проверка rate limiting (если можем подключиться к БД)
    try:
        from .memory import Memory
        memory = Memory(
            db_path=config.memory.db_path,
            context_window=config.memory.context_window,
            max_history_days=config.memory.max_history_days,
        )
        
        # Статистика FloodWait (если есть история)
        if config.rate_limiting.global_limits.enabled:
            from .rate_limiter import GlobalRateLimiter
            global_limiter = GlobalRateLimiter(
                session_factory=memory.SessionLocal,
                enabled=True,
                messages_per_minute=config.rate_limiting.global_limits.messages_per_minute,
                messages_per_hour=config.rate_limiting.global_limits.messages_per_hour,
                adaptive_enabled=config.rate_limiting.adaptive.enabled,
                reduction_on_floodwait_percent=config.rate_limiting.adaptive.reduction_on_floodwait_percent,
                recovery_period_minutes=config.rate_limiting.adaptive.recovery_period_minutes,
                recovery_increment_percent=config.rate_limiting.adaptive.recovery_increment_percent,
            )
            flood_stats = global_limiter.get_flood_wait_stats(hours=24)
            if flood_stats["count"] > 0:
                checks.append(
                    f"⚠️  FloodWait за 24ч: {flood_stats['count']} событий, "
                    f"среднее {flood_stats['avg_wait_seconds']:.1f}с, "
                    f"максимум {flood_stats['max_wait_seconds']}с"
                )
            else:
                checks.append("✅ FloodWait за 24ч: нет событий")
            
            # Показываем базовые и текущие адаптивные лимиты
            base_msg = f"ℹ️  Базовые глобальные лимиты: {config.rate_limiting.global_limits.messages_per_minute}/мин, {config.rate_limiting.global_limits.messages_per_hour}/час"
            if config.rate_limiting.adaptive.enabled:
                current_minute = global_limiter.messages_per_minute
                current_hour = global_limiter.messages_per_hour
                checks.append(base_msg)
                checks.append(
                    f"ℹ️  Текущие адаптивные лимиты: {current_minute}/мин, {current_hour}/час "
                    f"({'снижены' if current_minute < config.rate_limiting.global_limits.messages_per_minute else 'базовые'})"
                )
            else:
                checks.append(base_msg)
            
            checks.append(
                f"ℹ️  Адаптивные лимиты: {'включены' if config.rate_limiting.adaptive.enabled else 'отключены'}"
            )
            checks.append(
                f"ℹ️  Лимиты по типам чатов: private={config.rate_limiting.chat_type_limits.private}, "
                f"group={config.rate_limiting.chat_type_limits.group}, "
                f"channel={config.rate_limiting.chat_type_limits.channel}"
            )
    except Exception as e:
        checks.append(f"ℹ️  Rate limiting статистика недоступна: {e}")
    
    # Вывод результатов
    print("\n".join(checks))
    if issues:
        print("\n⚠️  Предупреждения:")
        print("\n".join(issues))
    
    if not issues:
        print("\n✅ Все проверки пройдены успешно!")
        sys.exit(0)
    else:
        print("\n⚠️  Обнаружены проблемы, но приложение может работать")
        sys.exit(0)


async def rag_stats():
    """Команда для вывода статистики использования RAG системы."""
    try:
        # Загружаем конфигурацию
        config_path = Path(__file__).parent.parent.parent / "config.yaml"
        config = Config.from_yaml(str(config_path))
        config.validate()

        print("📊 Статистика использования RAG системы\n")

        # Проверяем, включена ли RAG система
        if not config.rag.enabled:
            print("⚠️  RAG система отключена в конфигурации")
            sys.exit(0)

        # Инициализируем компоненты для доступа к RAG системе
        from .ai_client import AIClient
        from .vector_memory import VectorMemory
        from .rag import RAGSystem

        ai_client = AIClient(
            base_url=config.ai_server.base_url,
            model=config.ai_server.model,
            api_key=config.ai_server.api_key,
            timeout=config.ai_server.timeout,
            max_retries=config.ai_server.max_retries,
            max_tokens=config.ai_server.max_tokens,
            system_prompt=config.ai_server.system_prompt,
            temperature=config.ai_server.temperature,
            timezone_name=config.ai_server.timezone,
            date_format=config.ai_server.date_format,
        )

        # Vector Memory для RAG
        vector_memory = VectorMemory(
            persist_directory=config.memory.vector_db_path,
            collection_name="rag_knowledge_base",
            ai_client=ai_client,
            enabled=True,
        )

        # RAG System
        rag_system = RAGSystem(
            vector_memory=vector_memory,
            enabled=config.rag.enabled,
            knowledge_base_path=config.rag.knowledge_base_path,
            max_results=config.rag.max_results,
            min_score=config.rag.min_score,
            log_stats_interval=config.rag.log_stats_interval,
        )

        # Получаем статистику
        stats = rag_system.get_statistics()

        # Выводим статистику
        print(f"Всего запросов: {stats['total_queries']}")
        print(f"Успешных запросов: {stats['successful_queries']} ({stats['success_rate']:.1f}%)")
        print(f"Пустых результатов: {stats['empty_results']}")
        print(f"Всего найдено чанков: {stats['total_chunks_found']}")
        print(f"\nСтатистика по релевантности:")
        print(f"  Средний score: {stats['avg_score']:.3f}")
        print(f"  Минимальный score: {stats['min_score']:.3f}")
        print(f"  Максимальный score: {stats['max_score']:.3f}")
        print(f"\nДокументов в коллекции: {stats['collection_count']}")

        if stats['top_files']:
            print(f"\nТоп-10 наиболее используемых файлов:")
            for i, (file_path, count) in enumerate(stats['top_files'], 1):
                print(f"  {i}. {file_path}: {count} использований")
        else:
            print("\nФайлы еще не использовались")

        sys.exit(0)

    except Exception as e:
        logger.error(f"Error getting RAG statistics: {e}", exc_info=True)
        print(f"\n❌ Ошибка при получении статистики: {e}")
        sys.exit(1)


def cli():
    """CLI точка входа."""
    if len(sys.argv) > 1:
        if sys.argv[1] == "health":
            asyncio.run(health_check())
        elif sys.argv[1] == "rag_stats":
            asyncio.run(rag_stats())
        else:
            asyncio.run(main())
    else:
        asyncio.run(main())


if __name__ == "__main__":
    cli()

