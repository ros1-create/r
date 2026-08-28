"""Главный модуль Telegram-бота о породах кошек (aiogram 3)."""

import asyncio
import logging
import os
import sys
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.utils.chat_action import ChatActionSender

from gemini_client import ask_gemini

# Загружаем переменные окружения из .env
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Инициализация диспетчера
dp = Dispatcher()


def split_text(text: str, max_len: int = 4000) -> list[str]:
    """Разбивает длинный текст на части для соблюдения лимитов Telegram (4096 символов)."""
    if len(text) <= max_len:
        return [text]
    
    parts = []
    while len(text) > max_len:
        split_idx = text.rfind("\n\n", 0, max_len)
        if split_idx == -1:
            split_idx = text.rfind("\n", 0, max_len)
        if split_idx == -1:
            split_idx = text.rfind(" ", 0, max_len)
        if split_idx == -1:
            split_idx = max_len
        
        parts.append(text[:split_idx].strip())
        text = text[split_idx:].strip()
    
    if text:
        parts.append(text)
    return parts


async def send_safe_message(message: types.Message, text: str) -> None:
    """Безопасно отправляет сообщение, пробуя Markdown, а при ошибке парсинга — обычный текст."""
    parts = split_text(text)
    for part in parts:
        try:
            await message.answer(part, parse_mode=ParseMode.MARKDOWN)
        except Exception:
            try:
                await message.answer(part, parse_mode=None)
            except Exception as e:
                logger.error(f"Ошибка при отправке сообщения: {e}")


@dp.message(CommandStart())
async def cmd_start(message: types.Message) -> None:
    """Обработчик команды /start."""
    user_name = message.from_user.first_name if message.from_user else "друг"
    welcome_text = (
        f"🐾 *Здравствуйте, {user_name}!*\n\n"
        "Я — ваш спокойный проводник в удивительный мир кошачьих пород. ✨\n\n"
        "Вы можете спросить меня о чем угодно:\n"
        "• Описание конкретной породы (например: *«Расскажи про мейн-куна»* или *«Британская короткошёрстная»*)\n"
        "• Подбор породы под ваш стиль жизни (например: *«Какая кошка подойдет для семьи с маленьким ребенком?»*)\n"
        "• Гипоаллергенные или тихие породы\n"
        "• Особенности характера, ухода и здоровья\n\n"
        "Напишите название породы или ваш вопрос, и мы спокойно во всём разберёмся. 🐱"
    )
    await message.answer(welcome_text, parse_mode=ParseMode.MARKDOWN)


@dp.message(Command("help"))
async def cmd_help(message: types.Message) -> None:
    """Обработчик команды /help."""
    help_text = (
        "🐾 *Как пользоваться ботом:*\n\n"
        "1. Просто отправьте сообщение с названием породы или вопросом.\n"
        "2. Примеры запросов:\n"
        "   — *«Расскажи про сибирскую кошку»*\n"
        "   — *«Какие кошки самые спокойные и ласковые?»*\n"
        "   — *«Посоветуй породу кошки, которая хорошо переносит одиночество»*\n"
        "   — *«Чем отличается бенгальская кошка от ориентальной?»*\n\n"
        "Я работаю на базе нейросети Gemini и готов подробно ответить на любые вопросы о кошках. 🐱"
    )
    await message.answer(help_text, parse_mode=ParseMode.MARKDOWN)


@dp.message()
async def handle_message(message: types.Message, bot: Bot) -> None:
    """Обработчик текстовых сообщений пользователя."""
    if not message.text:
        return

    logger.info(f"Получено сообщение от @{message.from_user.username if message.from_user else 'unknown'}: {message.text[:50]}...")

    # Показ статуса «печатает» во время ожидания ответа от Gemini
    async with ChatActionSender.typing(bot=bot, chat_id=message.chat.id):
        reply_text = await ask_gemini(message.text)
        await send_safe_message(message, reply_text)


async def main() -> None:
    """Точка входа и запуск бота."""
    bot_token = os.getenv("BOT_TOKEN")
    
    if not bot_token:
        logger.error(
            "ОШИБКА: BOT_TOKEN не найден в переменных окружения!\n"
            "Пожалуйста, укажите токен в файле .env (BOT_TOKEN=...)."
        )
        print("\n" + "="*60)
        print("ВНИМАНИЕ: Переменная BOT_TOKEN не задана в файле .env!")
        print("Добавьте ваш токен бота в файл .env:")
        print("BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ")
        print("="*60 + "\n")
        return

    bot = Bot(token=bot_token)
    logger.info("Запуск Telegram-бота (Long Polling)...")
    
    try:
        # Сброс накопившихся вебхуков и запуск long polling
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        logger.info("Сессия бота закрыта.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен.")
