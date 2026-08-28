"""Модуль взаимодействия с Google Gemini API."""

import os
import logging
from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai import errors
from prompts import SYSTEM_PROMPT

# Загрузка переменных окружения из .env файла
load_dotenv()

logger = logging.getLogger(__name__)

PRIMARY_MODEL = "gemini-flash-latest"
FALLBACK_MODEL = "gemini-3.5-flash"


def is_503_error(exception: Exception) -> bool:
    """Проверяет, является ли ошибка ошибкой 503 (Service Unavailable / Overloaded)."""
    # Проверка кода ошибки в APIError / ServerError
    code = getattr(exception, "code", None)
    if code == 503:
        return True
    
    # Проверка статуса в ответе или тексте ошибки
    err_str = str(exception).upper()
    if "503" in err_str or "UNAVAILABLE" in err_str or "OVERLOADED" in err_str or "SERVICE UNAVAILABLE" in err_str:
        return True
        
    return False


async def ask_gemini(user_query: str) -> str:
    """Отправляет запрос к Gemini с системным промптом.
    
    При ошибке 503 выполняет повторный запрос к запасной модели gemini-3.5-flash.
    """
    gemini_key = os.getenv("GEMINI_KEY")
    if not gemini_key:
        logger.error("Переменная окружения GEMINI_KEY не найдена.")
        return (
            "🐾 Мурр... Ключ GEMINI_KEY не найден в переменных окружения.\n\n"
            "Пожалуйста, добавьте ваш API-ключ Gemini в файл `.env` в формате:\n"
            "`GEMINI_KEY=ваш_ключ`\n"
            "Получить бесплатный ключ можно в Google AI Studio: https://aistudio.google.com/"
        )

    client = genai.Client(api_key=gemini_key)
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        temperature=0.7,
    )

    # 1-я попытка: Основная модель gemini-flash-latest
    try:
        logger.info(f"Отправка запроса в Gemini (модель: {PRIMARY_MODEL})...")
        response = await client.aio.models.generate_content(
            model=PRIMARY_MODEL,
            contents=user_query,
            config=config,
        )
        if response and response.text:
            return response.text
        return "🐾 Не удалось получить текстовый ответ от модели. Попробуйте переформулировать вопрос."

    except Exception as e:
        if is_503_error(e):
            logger.warning(
                f"Модель {PRIMARY_MODEL} вернула ошибку 503 ({e}). "
                f"Повторяем запрос с запасной моделью {FALLBACK_MODEL}..."
            )
            # 2-я попытка: Запасная модель gemini-3.5-flash
            try:
                fallback_response = await client.aio.models.generate_content(
                    model=FALLBACK_MODEL,
                    contents=user_query,
                    config=config,
                )
                if fallback_response and fallback_response.text:
                    return fallback_response.text
                return "🐾 Не удалось получить текстовый ответ от запасной модели. Попробуйте еще раз позже."
            except Exception as fallback_err:
                logger.error(f"Ошибка при обращении к запасной модели {FALLBACK_MODEL}: {fallback_err}")
                return (
                    "🐾 Сервис временно перегружен. Пожалуйста, подождите минутку и повторите вопрос о котиках."
                )
        else:
            logger.error(f"Ошибка при запросе к Gemini ({PRIMARY_MODEL}): {e}")
            return (
                f"🐾 Произошла непредвиденная ошибка при обращении к Gemini: {e}\n"
                "Пожалуйста, попробуйте отправить запрос еще раз."
            )
