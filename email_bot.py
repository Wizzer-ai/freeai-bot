import asyncio
import logging
import os
import tempfile
from itertools import product

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    CallbackQuery,
)
from aiogram.client.default import DefaultBotProperties

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
if not BOT_TOKEN:
    print("Ошибка: Укажи BOT_TOKEN в переменной окружения или в коде")
    print("Пример: set BOT_TOKEN=123456:ABCdef...")
    exit(1)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()


def generate_variations(email: str) -> list[str]:
    local, domain = email.split("@", 1)
    n = len(local)
    result = []
    for bits in product([True, False], repeat=n - 1):
        parts = []
        for i, ch in enumerate(local):
            parts.append(ch)
            if i < n - 1 and bits[i]:
                parts.append(".")
        result.append("".join(parts) + "@" + domain)
    return result


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📧 Сгенерировать email", callback_data="generate", style="primary")],
            [InlineKeyboardButton(text="❓ Как это работает", callback_data="info", style="primary")],
            [InlineKeyboardButton(text="📊 Статистика", callback_data="stats", style="primary")],
        ]
    )


@dp.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        f"👋 <b>Email Variator Bot</b>\n\n"
        f"Пришли мне email вида <code>devicebywyz@gmail.com</code>,\n"
        f"а я создам все возможные варианты с точками!\n\n"
        f"Gmail игнорирует точки — все письма придут на тот же ящик.",
        reply_markup=main_menu(),
    )


@dp.callback_query(F.data == "generate")
async def cb_generate(callback: CallbackQuery):
    await callback.message.edit_text(
        "📧 <b>Отправь мне email</b>\n\n"
        "Пример: <code>devicebywyz@gmail.com</code>\n\n"
        "Я создам файл со всеми вариантами расстановки точек.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="back_menu", style="primary")]
            ]
        ),
    )
    await callback.answer()


@dp.callback_query(F.data == "info")
async def cb_info(callback: CallbackQuery):
    await callback.message.edit_text(
        "❓ <b>Как это работает</b>\n\n"
        "Gmail не учитывает точки в логине email.\n"
        "<code>devicebywyz@gmail.com</code> = <code>de.vi.ce.by.wyz@gmail.com</code>\n\n"
        "Все письма на любой из вариантов приходят в один ящик.\n\n"
        "<b>Формула:</b> для N букв → 2^(N-1) вариантов",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="back_menu", style="primary")]
            ]
        ),
    )
    await callback.answer()


@dp.callback_query(F.data == "stats")
async def cb_stats(callback: CallbackQuery):
    await callback.message.edit_text(
        "📊 <b>Статистика</b>\n\n"
        "• 5 букв → 16 вариантов\n"
        "• 8 букв → 128 вариантов\n"
        "• 10 букв → 512 вариантов\n"
        "• 11 букв → 1024 варианта\n"
        "• 14 букв → 8192 варианта\n\n"
        "Рекомендуется до 14 букв (файл ~200 КБ)",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="back_menu", style="primary")]
            ]
        ),
    )
    await callback.answer()


@dp.callback_query(F.data == "back_menu")
async def cb_back_menu(callback: CallbackQuery):
    await callback.message.edit_text(
        f"👋 <b>Email Variator Bot</b>\n\n"
        f"Пришли мне email вида <code>devicebywyz@gmail.com</code>,\n"
        f"а я создам все возможные варианты с точками!\n\n"
        f"Gmail игнорирует точки — все письма придут на тот же ящик.",
        reply_markup=main_menu(),
    )
    await callback.answer()


@dp.message()
async def handle_email(message: Message):
    email = message.text.strip()

    if "@" not in email or "." not in email.split("@")[1]:
        await message.answer(
            "❌ <b>Неверный формат</b>\n"
            "Отправь email в формате: <code>user@domain.com</code>",
            reply_markup=main_menu(),
        )
        return

    try:
        local, domain = email.split("@", 1)
        n = len(local)

        if n > 14:
            await message.answer(
                f"⚠️ <b>Слишком длинный логин</b> ({n} букв)\n"
                f"Будет создано 2^{n-1} = {2**(n-1):,} вариантов.\n"
                f"Рекомендуется не больше 14 букв.\n\n"
                f"Попробуй другой email.",
                reply_markup=main_menu(),
            )
            return

        wait_msg = await message.answer(
            f"⏳ <b>Генерирую...</b>\n"
            f"Логин: {local} ({n} букв)\n"
            f"Вариантов: 2^{n-1} = {2**(n-1):,}"
        )

        vars_list = generate_variations(email)

        total = len(vars_list)
        filename = f"{local}_variants.txt"

        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", suffix=".txt", delete=False
        ) as f:
            temp_path = f.name
            f.write(f"Базовый email: {email}\n")
            f.write(f"Всего вариантов: {total}\n")
            f.write(f"Логин: {local} ({n} букв)\n")
            f.write("=" * 50 + "\n\n")
            for v in vars_list:
                f.write(v + "\n")

        await bot.delete_message(chat_id=message.chat.id, message_id=wait_msg.message_id)

        doc = FSInputFile(temp_path, filename=filename)
        await message.answer_document(
            document=doc,
            caption=f"✅ <b>Готово!</b>\n\n"
                    f"📧 {email}\n"
                    f"📊 {total} вариантов\n"
                    f"📁 {filename}",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Ещё раз", callback_data="generate", style="success")],
                    [InlineKeyboardButton(text="🔝 Главное меню", callback_data="back_menu", style="primary")],
                ]
            ),
        )

        os.unlink(temp_path)

    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)
        await message.answer(
            "❌ <b>Произошла ошибка</b>\nПроверь формат email и попробуй снова.",
            reply_markup=main_menu(),
        )


async def main():
    logger.info("Бот запущен...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
