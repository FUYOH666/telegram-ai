#!/usr/bin/env python3
"""Извлечение информации о проектах из GitHub репозиториев для RAG базы знаний."""

import json
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

OUTPUT_DIR = Path(__file__).parent.parent / "knowledge_base" / "projects"
GITHUB_OWNER = "FUYOH666"


def get_all_repos() -> List[Dict]:
    """Получить список всех репозиториев через GitHub CLI."""
    print(f"Получение списка репозиториев для {GITHUB_OWNER}...")
    
    try:
        result = subprocess.run(
            ["gh", "repo", "list", GITHUB_OWNER, "--limit", "1000", "--json", 
             "name,description,isPrivate,url,createdAt,updatedAt,primaryLanguage"],
            capture_output=True,
            text=True,
            check=True,
        )
        
        repos = json.loads(result.stdout)
        print(f"✅ Найдено {len(repos)} репозиториев")
        return repos
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка при получении списка репозиториев: {e}")
        return []
    except json.JSONDecodeError as e:
        print(f"❌ Ошибка при парсинге JSON: {e}")
        return []


def get_readme_content(owner: str, repo: str) -> Optional[str]:
    """Получить содержимое README через GitHub API."""
    try:
        # Пробуем разные варианты названий README
        readme_files = ["README.md", "README.rst", "readme.md", "Readme.md"]
        
        for readme_file in readme_files:
            try:
                result = subprocess.run(
                    ["gh", "api", f"repos/{owner}/{repo}/contents/{readme_file}"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                
                data = json.loads(result.stdout)
                if "content" in data:
                    import base64
                    content = base64.b64decode(data["content"]).decode("utf-8")
                    return content
            except subprocess.CalledProcessError:
                continue
        
        return None
        
    except Exception as e:
        print(f"  ⚠️  Не удалось получить README для {repo}: {e}")
        return None


def extract_technologies_from_readme(readme: str) -> List[str]:
    """Извлечь упоминания технологий из README."""
    technologies = []
    
    # Ключевые слова технологий
    tech_keywords = [
        "Python", "JavaScript", "TypeScript", "Go", "Rust", "Java", "C++",
        "FastAPI", "Django", "Flask", "React", "Next.js", "Vue",
        "PostgreSQL", "MySQL", "MongoDB", "SQLite",
        "PyTorch", "TensorFlow", "Hugging Face", "OpenAI", "Whisper",
        "LLM", "GPT", "Claude", "Anthropic",
        "OCR", "Computer Vision", "Speech-to-Text", "TTS",
        "Docker", "Kubernetes", "AWS", "GCP", "Azure",
    ]
    
    readme_lower = readme.lower()
    for tech in tech_keywords:
        if tech.lower() in readme_lower:
            technologies.append(tech)
    
    return list(set(technologies))  # Уникальные значения


def categorize_project(repo: Dict, readme: Optional[str]) -> str:
    """Определить категорию проекта."""
    name_lower = repo["name"].lower()
    description_lower = (repo.get("description") or "").lower()
    readme_lower = (readme or "").lower()
    
    text = f"{name_lower} {description_lower} {readme_lower}"
    
    if any(word in text for word in ["telegram", "whatsapp", "chat", "assistant", "bot", "llm-talk"]):
        return "ai-assistants"
    elif any(word in text for word in ["voice", "speech", "whisper", "asr", "audio", "transcribe"]):
        return "speech-processing"
    elif any(word in text for word in ["automation", "automate", "gtd", "declaration", "voip", "call"]):
        return "automation"
    elif any(word in text for word in ["platform", "mindtech", "system", "management"]):
        return "platforms"
    elif any(word in text for word in ["cli", "tool", "cleaner", "utility"]):
        return "tools"
    else:
        return "other"


def create_project_file(repo: Dict, readme: Optional[str], category: str):
    """Создать файл с описанием проекта."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    category_dir = OUTPUT_DIR / category
    category_dir.mkdir(parents=True, exist_ok=True)
    
    name = repo["name"]
    description = repo.get("description") or "Проект на платформе GitHub"
    is_private = repo.get("isPrivate", False)
    
    # Извлекаем основную информацию из README без кода
    if readme:
        # Удаляем блоки кода
        readme_clean = re.sub(r"```[\s\S]*?```", "", readme)
        readme_clean = re.sub(r"`[^`]+`", "", readme_clean)
        # Берем первые несколько абзацев
        paragraphs = [p.strip() for p in readme_clean.split("\n\n") if p.strip()][:5]
        readme_summary = "\n\n".join(paragraphs)
    else:
        readme_summary = ""
    
    technologies = extract_technologies_from_readme(readme or "")
    
    # Формируем содержимое файла
    content = f"""# {name}

## Описание

{description}

{readme_summary}

## Основные возможности

Проект демонстрирует наши возможности в области разработки AI-решений и автоматизации бизнес-процессов.

"""
    
    if technologies:
        content += f"""## Используемые технологии

{', '.join(technologies)}

"""
    
    content += f"""## Тип проекта

{category.replace('-', ' ').title()}

## Демонстрация возможностей

Этот проект показывает, что мы можем разработать решение под конкретные задачи клиента. Работаем с различными технологиями и создаем кастомные решения под специфические потребности.

---
*Проект: {name} | {'Приватный' if is_private else 'Публичный'} репозиторий*
"""
    
    # Создаем безопасное имя файла
    safe_name = re.sub(r"[^\w\-_]", "_", name.lower())
    file_path = category_dir / f"{safe_name}.md"
    
    file_path.write_text(content, encoding="utf-8")
    print(f"  ✅ Создан файл: {file_path}")


def create_projects_index(repos_by_category: Dict[str, List[Dict]]):
    """Создать индексный файл со всеми проектами."""
    index_content = """# Проекты Scanovich.ai

Этот раздел содержит описание наших проектов, демонстрирующих широкий спектр возможностей компании.

## Категории проектов

"""
    
    category_names = {
        "ai-assistants": "AI-ассистенты и чат-боты",
        "speech-processing": "Обработка речи и аудио",
        "automation": "Автоматизация бизнес-процессов",
        "platforms": "Платформы и комплексные решения",
        "tools": "Инструменты и утилиты",
        "other": "Другие проекты",
    }
    
    for category, repos in repos_by_category.items():
        if not repos:
            continue
        
        category_name = category_names.get(category, category.replace("-", " ").title())
        index_content += f"\n### {category_name}\n\n"
        
        for repo in repos:
            name = repo["name"]
            description = repo.get("description") or "Проект на платформе GitHub"
            safe_name = re.sub(r"[^\w\-_]", "_", name.lower())
            index_content += f"- **{name}**: {description}\n"
            index_content += f"  - Файл: `{category}/{safe_name}.md`\n"
        
        index_content += "\n"
    
    index_content += """## Универсальность наших решений

Этот список проектов демонстрирует широкий спектр наших возможностей:

- Разработка AI-ассистентов и интеллектуальных систем
- Обработка речи и аудио (распознавание, синтез)
- Автоматизация бизнес-процессов
- Создание платформ и комплексных решений
- Разработка инструментов и утилит

**Важно**: мы не ограничиваемся только этими типами проектов. Можем разработать решение под любую вашу задачу — от простых автоматизаций до комплексных платформ.

## Кастомная разработка

Каждый проект показывает нашу способность адаптироваться под специфические требования и создавать решения, оптимальные для конкретных задач клиента.

Если у вас есть задача, которая не представлена в этих примерах — это не проблема. Мы можем разработать решение под ваши нужды.
"""
    
    index_file = OUTPUT_DIR / "_index.md"
    index_file.write_text(index_content, encoding="utf-8")
    print(f"✅ Создан индексный файл: {index_file}")


def main():
    """Основная функция."""
    print("🚀 Начало извлечения информации о проектах из GitHub...")
    
    repos = get_all_repos()
    
    if not repos:
        print("❌ Не найдено репозиториев")
        return
    
    repos_by_category = {
        "ai-assistants": [],
        "speech-processing": [],
        "automation": [],
        "platforms": [],
        "tools": [],
        "other": [],
    }
    
    for i, repo in enumerate(repos, 1):
        name = repo["name"]
        print(f"\n[{i}/{len(repos)}] Обработка репозитория: {name}")
        
        # Получаем README
        readme = get_readme_content(GITHUB_OWNER, name)
        
        # Определяем категорию
        category = categorize_project(repo, readme)
        repos_by_category[category].append(repo)
        
        # Создаем файл проекта
        create_project_file(repo, readme, category)
    
    # Создаем индексный файл
    create_projects_index(repos_by_category)
    
    print(f"\n✅ Обработано {len(repos)} репозиториев")
    print(f"✅ Проекты сгруппированы по {len([c for c in repos_by_category.values() if c])} категориям")


if __name__ == "__main__":
    main()

