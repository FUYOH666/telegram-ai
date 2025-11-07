"""Определение языка сообщения."""

import logging
from typing import Optional

try:
    from langdetect import detect, DetectorFactory, LangDetectException
    from langdetect.lang_detect_exception import LangDetectException as LangDetectExceptionImport

    # Фиксируем seed для детерминированности
    DetectorFactory.seed = 0

    LANGDETECT_AVAILABLE = True
except ImportError:
    LANGDETECT_AVAILABLE = False

logger = logging.getLogger(__name__)

# Маппинг кодов языков на понятные названия (только поддерживаемые языки!)
LANGUAGE_NAMES = {
    "ru": "русском",
    "en": "английском",
    "zh": "упрощенном китайском (Simplified Chinese)",
    "th": "тайском",
}

# Языки, которые поддерживаются (только эти 4 языка!)
SUPPORTED_LANGUAGES = {
    "ru": "Russian",
    "en": "English",
    "zh": "Chinese",
    "th": "Thai",
}


def detect_language(text: Optional[str]) -> Optional[str]:
    """
    Определить язык текста.

    Args:
        text: Текст для определения языка

    Returns:
        Код языка (например, "ru", "en", "zh") или None если не удалось определить
    """
    if not text or not text.strip():
        return None

    if not LANGDETECT_AVAILABLE:
        logger.warning("langdetect library not available, cannot detect language")
        return None

    try:
        # Минимальная длина текста для надежного определения
        text_clean = text.strip()
        if len(text_clean) < 1:
            return None

        # ПРИОРИТЕТ: Сначала проверяем по символам (надежнее для коротких текстов)
        # Это помогает избежать ошибок langdetect на коротких текстах с кириллицей
        
        # Проверяем наличие кириллицы для русского (ПРИОРИТЕТ #1)
        if any('\u0400' <= char <= '\u04FF' for char in text_clean):
            # Дополнительно проверяем через langdetect для подтверждения
            try:
                detected_lang = detect(text_clean)
                if detected_lang and detected_lang in SUPPORTED_LANGUAGES:
                    logger.debug(f"Detected language by symbols and langdetect: ru (langdetect said: {detected_lang}) for text: {text_clean[:50]}...")
                    return "ru"
                else:
                    logger.debug(f"Detected Cyrillic characters, using ru (langdetect said: {detected_lang}) for text: {text_clean[:50]}...")
                    return "ru"
            except Exception:
                logger.debug(f"Detected Cyrillic characters, using ru for text: {text_clean[:50]}...")
                return "ru"
        
        # Проверяем наличие китайских иероглифов
        if any('\u4e00' <= char <= '\u9fff' for char in text_clean):
            logger.debug(f"Detected Chinese characters, using zh for text: {text_clean[:50]}...")
            return "zh"
        
        # Проверяем наличие тайских символов
        if any('\u0e00' <= char <= '\u0e7f' for char in text_clean):
            logger.debug(f"Detected Thai characters, using th for text: {text_clean[:50]}...")
            return "th"
        
        # Если нет специфических символов - используем langdetect
        detected_lang = detect(text_clean)

        # Нормализуем код языка (zh-cn -> zh, zh-tw -> zh и т.д.)
        if detected_lang:
            # Если это составной код (zh-cn, en-us и т.д.), берем первую часть
            if "-" in detected_lang:
                detected_lang = detected_lang.split("-")[0]
            
            # Проверяем, что язык поддерживается (ТОЛЬКО ru, en, zh, th)
            if detected_lang in SUPPORTED_LANGUAGES:
                logger.debug(f"Detected language: {detected_lang} for text: {text_clean[:50]}...")
                return detected_lang
            else:
                # Если langdetect определил неподдерживаемый язык, но есть латиница - английский
                if any(char.isalpha() and ord(char) < 128 for char in text_clean):
                    logger.debug(f"Detected unsupported language: {detected_lang}, but found Latin characters, using en")
                    return "en"
                else:
                    logger.debug(f"Detected unsupported language: {detected_lang}, falling back to default (ru) for text: {text_clean[:50]}...")
                    return None
        
        logger.debug(f"Could not detect language for text: {text_clean[:50]}..., using default (ru)")
        return None

    except (LangDetectException, LangDetectExceptionImport, Exception) as e:
        logger.debug(f"Language detection failed: {e}, text: {text_clean[:50] if text else 'None'}...")
        return None


def get_language_name(lang_code: Optional[str]) -> str:
    """
    Получить читаемое название языка.

    Args:
        lang_code: Код языка (например, "ru", "en")

    Returns:
        Название языка на русском (например, "русском", "английском")
    """
    if not lang_code:
        return "русском"  # По умолчанию

    # Если язык не в списке поддерживаемых - возвращаем русский
    if lang_code not in LANGUAGE_NAMES:
        logger.warning(f"Unsupported language code: {lang_code}, using Russian")
        return "русском"

    return LANGUAGE_NAMES.get(lang_code, "русском")


def should_respond_in_language(message_lang: Optional[str], current_lang: Optional[str]) -> str:
    """
    Определить, на каком языке нужно отвечать.

    Args:
        message_lang: Язык текущего сообщения
        current_lang: Язык из контекста пользователя

    Returns:
        Код языка для ответа (всегда один из поддерживаемых: ru, en, zh, th)
    """
    # Проверяем, что язык в списке поддерживаемых
    def is_supported(lang: Optional[str]) -> bool:
        return lang is not None and lang in SUPPORTED_LANGUAGES
    
    # Если язык сообщения определен и поддерживается - используем его
    if is_supported(message_lang):
        return message_lang

    # Если язык из контекста поддерживается - используем его
    if is_supported(current_lang):
        return current_lang

    # По умолчанию - русский (всегда возвращаем валидный язык)
    return "ru"

