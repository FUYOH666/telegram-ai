#!/usr/bin/env python3
"""Скрипт для сборки и валидации базы знаний RAG."""

from pathlib import Path

OUTPUT_DIR = Path(__file__).parent.parent / "knowledge_base"


def validate_structure() -> bool:
    """Проверить структуру базы знаний."""
    print("Проверка структуры базы знаний...")
    
    required_dirs = [
        "capabilities",
        "company",
        "projects",
        "technologies",
        "use-cases",
    ]
    
    all_valid = True
    
    for dir_name in required_dirs:
        dir_path = OUTPUT_DIR / dir_name
        if not dir_path.exists():
            print(f"  ❌ Отсутствует директория: {dir_name}")
            all_valid = False
        else:
            md_files = list(dir_path.rglob("*.md"))
            # Исключаем README.md из подсчета для директорий
            md_files = [f for f in md_files if f.name != "README.md"]
            print(f"  ✅ {dir_name}: {len(md_files)} файлов")
    
    return all_valid


def count_files() -> dict:
    """Подсчитать количество файлов в каждой категории."""
    counts = {}
    
    for category_dir in OUTPUT_DIR.iterdir():
        if category_dir.is_dir() and not category_dir.name.startswith("."):
            md_files = list(category_dir.rglob("*.md"))
            # Исключаем README.md из подсчета
            md_files = [f for f in md_files if f.name != "README.md"]
            counts[category_dir.name] = len(md_files)
    
    return counts


def validate_files() -> bool:
    """Проверить валидность файлов."""
    print("\nПроверка файлов...")
    
    all_valid = True
    
    for md_file in OUTPUT_DIR.rglob("*.md"):
        try:
            content = md_file.read_text(encoding="utf-8")
            
            # Проверяем минимальный размер
            if len(content) < 100:
                print(f"  ⚠️  Файл слишком короткий: {md_file.relative_to(OUTPUT_DIR)}")
            
            # Проверяем наличие заголовков
            if not content.startswith("#"):
                print(f"  ⚠️  Файл без заголовка: {md_file.relative_to(OUTPUT_DIR)}")
            
        except Exception as e:
            print(f"  ❌ Ошибка при чтении {md_file.relative_to(OUTPUT_DIR)}: {e}")
            all_valid = False
    
    return all_valid


def create_summary():
    """Создать сводку по базе знаний."""
    counts = count_files()
    
    total_files = sum(counts.values())
    
    summary = f"""# База знаний Scanovich.ai

## Статистика

Всего документов: {total_files}

### По категориям:
"""
    
    for category, count in sorted(counts.items()):
        summary += f"- **{category}**: {count} файлов\n"
    
    summary += """
## Структура

База знаний содержит информацию о:
- **capabilities** - Возможности и универсальность решений (развертывание, интеграция, full-stack)
- **company** - Компании и услугах
- **projects** - Проектах и кейсах (AI-ассистенты, автоматизация, платформы, обработка речи)
- **technologies** - Технологиях и компетенциях
- **use-cases** - Применении решений по индустриям (финансы, здравоохранение, право, телеком)

## Использование

Эта база знаний используется RAG системой для поиска релевантной информации при ответах на вопросы клиентов.

### Обновление базы знаний

Для валидации структуры и файлов запустите:

```bash
uv run python scripts/build_knowledge_base.py
```

Скрипт проверит:
- Наличие всех необходимых директорий
- Валидность файлов (минимальный размер, наличие заголовков)
- Обновит статистику в README.md
"""
    
    summary_file = OUTPUT_DIR / "README.md"
    summary_file.write_text(summary, encoding="utf-8")
    print(f"\n✅ Создана сводка: {summary_file}")


def main():
    """Основная функция."""
    print("🚀 Сборка и валидация базы знаний...\n")
    
    if not OUTPUT_DIR.exists():
        print(f"❌ Директория базы знаний не найдена: {OUTPUT_DIR}")
        return
    
    # Проверка структуры
    structure_valid = validate_structure()
    
    if not structure_valid:
        print("\n❌ Структура базы знаний неполная")
        return
    
    # Проверка файлов
    files_valid = validate_files()
    
    # Подсчет файлов
    counts = count_files()
    total = sum(counts.values())
    
    print(f"\n📊 Всего файлов: {total}")
    
    # Создание сводки
    create_summary()
    
    if structure_valid and files_valid:
        print("\n✅ База знаний валидна и готова к использованию!")
    else:
        print("\n⚠️  База знаний имеет некоторые проблемы, но может быть использована")


if __name__ == "__main__":
    main()

