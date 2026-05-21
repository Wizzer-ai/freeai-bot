"""
AI Telegram Bot v3 — Исправленная версия
========================================
Исправления:
  1. Model ID google/gemini-2.0-flash → google/gemini-2.0-flash-001
  2. os.execv на Windows → subprocess + sys.exit
  3. Tavily без API-ключа — выключен, если нет ключа
  4. Brave search (возвращал HTML, не JSON) — заменён на DuckDuckGo
  5. Утечка temp-файлов — try/finally
  6. API-ключи через .env / os.getenv()
  7. max() с пустым dict — защита
  8. Добавлены недостающие хендлеры команд
"""

import asyncio
import aiohttp
import logging
import os
import sys
import tempfile
import json
import time
import ctypes
from datetime import datetime, timezone
from collections import defaultdict
from typing import Optional
from pathlib import Path

# pip install python-dotenv
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup,
    InlineKeyboardButton, PreCheckoutQuery, LabeledPrice
)
from aiogram.exceptions import TelegramBadRequest

# =============================================================
# 🌐 ЯЗЫКИ
# =============================================================
LANGUAGES = {
    "ru": "Русский 🇷🇺",
    "uz": "O'zbek 🇺🇿",
    "en": "English 🇬🇧"
}

TRANSLATIONS = {
    "ru": {
        "welcome": "Привет, {name}!\nЯ — AI-ассистент.\nВыбери язык:",
        "menu_ai_chat": "💬 AI-чат",
        "menu_photo": "🖼 Анализ фото",
        "menu_file": "📄 Чтение файлов",
        "menu_search": "🔍 Поиск",
        "menu_facts": "✅ Фактчек",
        "menu_settings": "⚙️ Настройки",
        "menu_help": "ℹ️ Помощь",
        "menu_admin": "🔴 Админ",
        "menu_language": "🌐 Язык",
        "menu_payment": "💰 Пополнить",
        "model_select": "Выбери модель:",
        "help_text": "Команды:\n/start — Меню\n/help — Помощь\n/clear — Очистить\n/model — Модель\n/settings — Настройки",
        "payment_title": "💰 Пополнение баланса",
        "payment_crypto": "CryptoBot - $2/неделя",
        "payment_card": "Карта Узбекистан - 20 000 сум/неделя",
        "payment_stars": "⭐ Telegram Stars - 100 зв./неделя",
        "payment_success": "✅ Оплата подтверждена!",
        "payment_wait": "⏳ Ожидаю оплату...",
        "trial": "Пробный период",
        "active": "Активен до: {date}",
        "expired": "❌ Подписка истекла",
        "main_features": "• AI-чат • Фото • Файлы • Поиск • Факты",
    },
    "uz": {
        "welcome": "Salom, {name}!\nMen — AI-yordamchi.\nTilni tanlang:",
        "menu_ai_chat": "💬 AI-chat",
        "menu_photo": "🖼 Foto tahlili",
        "menu_file": "📄 Fayl o'qish",
        "menu_search": "🔍 Qidiruv",
        "menu_facts": "✅ Fakt-check",
        "menu_settings": "⚙️ Sozlamalar",
        "menu_help": "ℹ️ Yordam",
        "menu_admin": "🔴 Admin",
        "menu_language": "🌐 Til",
        "menu_payment": "💰 To'ldirish",
        "model_select": "Modelni tanlang:",
        "help_text": "Buyruqlar:\n/start — Menu\n/help — Yordam\n/clear — Tozalash\n/model — Model\n/settings — Sozlamalar",
        "payment_title": "💰 Balansni to'ldirish",
        "payment_crypto": "CryptoBot - $2/hafta",
        "payment_card": "O'zbek karta - 20 000 so'm/hafta",
        "payment_stars": "⭐ Telegram Stars - 100 ta/hafta",
        "payment_success": "✅ To'lov tasdiqlandi!",
        "payment_wait": "⏳ To'lov kutish...",
        "trial": "Sinov muddati",
        "active": "Faol to: {date}",
        "expired": "❌ Obunka tugagan",
        "main_features": "• AI-chat • Foto • Fayllar • Qidiruv • Faktlar",
    },
    "en": {
        "welcome": "Hello, {name}!\nI'm an AI assistant.\nChoose language:",
        "menu_ai_chat": "💬 AI Chat",
        "menu_photo": "🖼 Photo Analysis",
        "menu_file": "📄 Read Files",
        "menu_search": "🔍 Search",
        "menu_facts": "✅ Fact Check",
        "menu_settings": "⚙️ Settings",
        "menu_help": "ℹ️ Help",
        "menu_admin": "🔴 Admin",
        "menu_language": "🌐 Language",
        "menu_payment": "💰 Top up",
        "model_select": "Select model:",
        "help_text": "Commands:\n/start — Menu\n/help — Help\n/clear — Clear\n/model — Model\n/settings — Settings",
        "payment_title": "💰 Balance top-up",
        "payment_crypto": "CryptoBot - $2/week",
        "payment_card": "Uzbek Card - 20,000 sum/week",
        "payment_stars": "⭐ Telegram Stars - 100 stars/week",
        "payment_success": "✅ Payment confirmed!",
        "payment_wait": "⏳ Waiting for payment...",
        "trial": "Trial period",
        "active": "Active until: {date}",
        "expired": "❌ Subscription expired",
        "main_features": "• AI-chat • Photos • Files • Search • Facts",
    }
}

user_languages: dict[int, str] = {}

def t(user_id: int, key: str) -> str:
    lang = user_languages.get(user_id, "ru")
    return TRANSLATIONS.get(lang, TRANSLATIONS["ru"]).get(key, key)

# =============================================================
# 🔧 НАСТРОЙКИ (через переменные окружения)
# =============================================================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
MAX_CONTEXT_MESSAGES = 20
MAX_FILE_SIZE = 50 * 1024 * 1024

# =============================================================
# БЕСПЛАТНЫЕ МОДЕЛИ (ИСПРАВЛЕННЫЕ ID)
# =============================================================
FREE_MODELS = {
    "gemini_flash": {
        "name": "💎 Gemini 2.0 Flash",
        "provider": "openrouter",
        "model_id": "google/gemini-2.0-flash-001",
        "base_url": OPENROUTER_BASE_URL,
        "api_key": OPENROUTER_API_KEY,
        "description": "Google Gemini — быстрый и умный",
        "supports_vision": True,
    },
    "gemini_flash_2_5": {
        "name": "💎 Gemini 2.5 Flash",
        "provider": "openrouter",
        "model_id": "google/gemini-2.5-flash",
        "base_url": OPENROUTER_BASE_URL,
        "api_key": OPENROUTER_API_KEY,
        "description": "Gemini 2.5 — улучшенная версия",
        "supports_vision": True,
    },
    "gpt_4o_mini": {
        "name": "🟢 GPT-4o Mini",
        "provider": "openrouter",
        "model_id": "openai/gpt-4o-mini",
        "base_url": OPENROUTER_BASE_URL,
        "api_key": OPENROUTER_API_KEY,
        "description": "OpenAI — лёгкий и быстрый",
        "supports_vision": True,
    },
    "llama_3_1": {
        "name": "🦙 Llama 3.1 8B",
        "provider": "openrouter",
        "model_id": "meta-llama/llama-3.1-8b-instruct",
        "base_url": OPENROUTER_BASE_URL,
        "api_key": OPENROUTER_API_KEY,
        "description": "Meta Llama — мощная открытая модель",
        "supports_vision": False,
    },
    "qwen_2_5": {
        "name": "🐉 Qwen 2.5 7B",
        "provider": "openrouter",
        "model_id": "qwen/qwen-2.5-7b-instruct",
        "base_url": OPENROUTER_BASE_URL,
        "api_key": OPENROUTER_API_KEY,
        "description": "Мощная модель от Alibaba",
        "supports_vision": False,
    },
    "qwen_coder": {
        "name": "💻 Qwen 2.5 Coder 7B",
        "provider": "openrouter",
        "model_id": "qwen/qwen-2.5-coder-7b-instruct",
        "base_url": OPENROUTER_BASE_URL,
        "api_key": OPENROUTER_API_KEY,
        "description": "Лучшая модель для кода",
        "supports_vision": False,
    },
}

DEFAULT_MODEL = "gemini_flash"

# =============================================================
# ЛОГИРОВАНИЕ
# =============================================================
logging.basicConfig(
    level=logging.INFO,
    format='✦ %(asctime)s ✦ %(name)s ✦ %(levelname)s ✦ %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("AI-Bot")

# =============================================================
# ИНИЦИАЛИЗАЦИЯ
# =============================================================
bot = None  # Будет инициализирован после проверки переменных окружения
dp = Dispatcher()
router = Router()

# =============================================================
# СТАТИСТИКА
# =============================================================
stats = {
    "total_messages": 0,
    "total_users": set(),
    "messages_today": 0,
    "last_reset_date": datetime.now(timezone.utc).date().isoformat(),
    "model_usage": defaultdict(int),
    "command_usage": defaultdict(int),
    "file_types": defaultdict(int),
    "errors": 0,
    "start_time": datetime.now(timezone.utc).isoformat(),
}

user_models: dict[int, str] = {}
user_contexts: dict[int, list] = {}


def get_user_model(user_id: int) -> str:
    return user_models.get(user_id, DEFAULT_MODEL)


def update_stats(key: str, value: str = None):
    now = datetime.now(timezone.utc).date().isoformat()
    if now != stats["last_reset_date"]:
        stats["messages_today"] = 0
        stats["last_reset_date"] = now
    stats["total_messages"] += 1
    stats["messages_today"] += 1
    if key == "model":
        stats["model_usage"][value] += 1
    elif key == "command":
        stats["command_usage"][value] += 1
    elif key == "file":
        stats["file_types"][value] += 1
    elif key == "error":
        stats["errors"] += 1


# =============================================================
# БЕЗОПАСНОЕ РЕДАКТИРОВАНИЕ СООБЩЕНИЙ
# =============================================================

async def safe_edit(callback_or_message, text: str, reply_markup=None, parse_mode="HTML"):
    try:
        if isinstance(callback_or_message, CallbackQuery):
            await callback_or_message.message.edit_text(
                text, reply_markup=reply_markup, parse_mode=parse_mode
            )
            await callback_or_message.answer()
        else:
            await callback_or_message.edit_text(
                text, reply_markup=reply_markup, parse_mode=parse_mode
            )
    except TelegramBadRequest as e:
        err = str(e)
        if "message is not modified" in err:
            if isinstance(callback_or_message, CallbackQuery):
                await callback_or_message.answer()
            return
        if "message can't be edited" in err:
            if isinstance(callback_or_message, CallbackQuery):
                await callback_or_message.message.answer(
                    text, reply_markup=reply_markup, parse_mode=parse_mode
                )
                await callback_or_message.answer()
            else:
                await callback_or_message.answer(
                    text, reply_markup=reply_markup, parse_mode=parse_mode
                )
            return
        if isinstance(callback_or_message, CallbackQuery):
            try:
                await callback_or_message.message.answer(
                    text, reply_markup=reply_markup, parse_mode=parse_mode
                )
                await callback_or_message.answer()
            except Exception:
                await callback_or_message.answer()
        else:
            raise


# =============================================================
# ИИ ДВИГАТЕЛЬ
# =============================================================

SYSTEM_PROMPT = """Ты — вежливый AI-ассистент.

Ты умеешь:
1. Читать и анализировать файлы (PDF, DOCX, TXT, изображения)
2. Искать информацию в интернете и проверять факты
3. Анализировать изображения и картинки
4. Объяснять сложные вещи простым языком
5. Помогать с кодом, математикой, переводами и другими вопросами

ПРАВИЛА ОТВЕТА:
• Не используй жирный текст (**текст**) и Markdown форматирование в ответах
• Пиши чистым, читаемым текстом без лишних украшений
• Используй заголовки через пробел (например: "Внутренняя политика")
• Делай абзацы для удобства чтения
• Проверяй факты перед ответом
• Указывай источники, если используешь данные из интернета
• Будь дружелюбным и полезным
• Если не уверен — скажи об этом честно
• Отвечай на языке пользователя"""


class AIEngine:
    def __init__(self):
        self.openrouter_headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/ai-bot",
            "X-Title": "Telegram AI Bot"
        }

    async def send_message(
        self,
        user_id: int,
        user_message: str = None,
        image_url: str = None,
        file_text: str = None,
        web_results: list = None,
        model_key: str = None
    ) -> str:
        if model_key is None:
            model_key = get_user_model(user_id)

        model_info = FREE_MODELS.get(model_key, FREE_MODELS[DEFAULT_MODEL])
        model_id = model_info["model_id"]
        base_url = model_info["base_url"]
        headers = self.openrouter_headers.copy()

        if user_id not in user_contexts:
            user_contexts[user_id] = []
        context = user_contexts[user_id]

        content = []
        text_content = user_message or "Проанализируй это"

        if web_results:
            search_info = "\n\n📚 <b>Найденные источники:</b>\n"
            for i, r in enumerate(web_results[:5], 1):
                search_info += (
                    f"\n{i}. <b>{r.get('title', 'Источник')}</b>\n"
                    f"   {r.get('snippet', '')}\n"
                    f"   🔗 {r.get('link', '')}\n"
                )
            text_content += (
                f"\n\n{search_info}\n\n"
                "На основе этой информации, ответь подробно и проверь достоверность."
            )

        content.append({"type": "text", "text": text_content})

        if image_url:
            content.append({
                "type": "image_url",
                "image_url": {"url": image_url, "detail": "high"}
            })

        if file_text:
            content.append({
                "type": "text",
                "text": f"📄 <b>Содержимое файла:</b>\n\n{file_text[:15000]}"
            })

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(context)
        messages.append({"role": "user", "content": content})

        payload = {
            "model": model_id,
            "messages": messages,
            "max_tokens": 4000,
            "temperature": 0.7,
            "top_p": 0.9,
            "stream": False
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=120)
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"API Error {response.status}: {error_text}")
                        update_stats("error", f"api_{response.status}")
                        return (
                            f"❌ Ошибка API (код {response.status}).\n"
                            f"Попробуйте другую модель или позже."
                        )

                    data = await response.json()
                    ai_response = data["choices"][0]["message"]["content"]

                    context.append({
                        "role": "user",
                        "content": [{"type": "text", "text": text_content}]
                    })
                    context.append({
                        "role": "assistant",
                        "content": ai_response
                    })

                    if len(context) > MAX_CONTEXT_MESSAGES:
                        context[:] = [context[0]] + context[-MAX_CONTEXT_MESSAGES + 1:]

                    update_stats("model", model_key)
                    return ai_response

        except asyncio.TimeoutError:
            update_stats("error", "timeout")
            return "⏳ Время ожидания истекло. Попробуйте ещё раз."
        except Exception as e:
            logger.error(f"AI Error: {e}")
            update_stats("error", str(e))
            return f"❌ Ошибка: {str(e)}. Попробуйте другую модель."

    def clear_context(self, user_id: int):
        if user_id in user_contexts:
            del user_contexts[user_id]


ai_engine = AIEngine()


# =============================================================
# ВЕБ-ПОИСК (DuckDuckGo — не требует API-ключа)
# =============================================================

class WebSearchEngine:
    async def search(self, query: str, num_results: int = 5) -> list:
        results = await self._duckduckgo_search(query, num_results)
        if results:
            return results
        return await self._fallback_search(query, num_results)

    async def _duckduckgo_search(self, query: str, num_results: int = 5) -> list:
        try:
            url = f"https://api.duckduckgo.com/?q={query}&format=json&no_html=1"
            headers = {"User-Agent": "Mozilla/5.0 (compatible; TelegramBot/1.0)"}
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        results = []

                        if data.get("AbstractText"):
                            results.append({
                                "title": data.get("AbstractSource", "Результат"),
                                "link": data.get("AbstractURL", ""),
                                "snippet": data["AbstractText"][:500]
                            })

                        for topic in data.get("RelatedTopics", [])[:num_results]:
                            if "Text" in topic:
                                results.append({
                                    "title": topic.get("Text", topic.get("FirstURL", ""))[:100],
                                    "link": topic.get("FirstURL", ""),
                                    "snippet": topic.get("Text", "")[:300]
                                })
                            elif "Topics" in topic:
                                for sub in topic["Topics"][:2]:
                                    results.append({
                                        "title": sub.get("Text", "")[:100],
                                        "link": sub.get("FirstURL", ""),
                                        "snippet": sub.get("Text", "")[:300]
                                    })

                        return results[:num_results]
        except Exception as e:
            logger.warning(f"DuckDuckGo search failed: {e}")
        return []

    async def _fallback_search(self, query: str, num_results: int = 5) -> list:
        try:
            url = "https://html.duckduckgo.com/html/"
            params = {"q": query}
            headers = {"User-Agent": "Mozilla/5.0 (compatible; TelegramBot/1.0)"}
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url, data=params, headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 200:
                        html = await resp.text()
                        results = []
                        import re
                        snippets = re.findall(
                            r'class="result__snippet"[^>]*>(.*?)</a>',
                            html, re.DOTALL
                        )
                        links = re.findall(
                            r'class="result__url"[^>]*>(.*?)</a>',
                            html, re.DOTALL
                        )
                        for i, snippet in enumerate(snippets[:num_results]):
                            clean_snippet = re.sub(r'<[^>]+>', '', snippet).strip()
                            clean_link = ""
                            if i < len(links):
                                clean_link = re.sub(r'<[^>]+>', '', links[i]).strip()
                            results.append({
                                "title": clean_snippet[:80],
                                "link": f"https://{clean_link}" if clean_link else "",
                                "snippet": clean_snippet[:300]
                            })
                        return results
        except Exception as e:
            logger.warning(f"Fallback search failed: {e}")
        return []

    async def fact_check(self, claim: str) -> str:
        try:
            search_query = f"фактчек: {claim} верификация достоверность"
            results = await self.search(search_query, num_results=3)
            if not results:
                return "⚠️ Не удалось найти информацию для проверки."

            sources_text = ""
            for i, r in enumerate(results[:3], 1):
                sources_text += f"\n{i}. {r['title']}: {r['snippet'][:200]}"

            fact_check_prompt = f"""
Проверь достоверность утверждения, используя источники:

УТВЕРЖДЕНИЕ: "{claim}"

ИСТОЧНИКИ:
{sources_text}

Ответь:
- ✅ ВЕРНО / ❌ НЕВЕРНО / ⚠️ НЕОДНОЗНАЧНО
- Обоснование
- Ссылки на источники
"""
            response = await ai_engine.send_message(
                user_id=0, user_message=fact_check_prompt
            )
            return response
        except Exception as e:
            return f"❌ Ошибка при проверке: {e}"


web_search = WebSearchEngine()


# =============================================================
# ЧТЕНИЕ ФАЙЛОВ
# =============================================================

try:
    import PyPDF2
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

try:
    from docx import Document
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False


class FileReader:
    MAX_TEXT_LENGTH = 15000

    @staticmethod
    async def read_file(file_path: str, mime_type: str = None, file_name: str = None) -> Optional[str]:
        if file_name is None:
            file_name = file_path
        mime = mime_type or ""
        name_lower = file_name.lower()
        try:
            if "pdf" in mime or name_lower.endswith(".pdf"):
                return await FileReader._read_pdf(file_path)
            elif "docx" in mime or name_lower.endswith((".docx", ".doc")):
                return await FileReader._read_docx(file_path)
            elif "text" in mime or name_lower.endswith(
                    (".txt", ".md", ".csv", ".log", ".json", ".xml", ".html", ".py", ".js",
                     ".cpp", ".java", ".yml", ".yaml")):
                return await FileReader._read_text(file_path)
            else:
                text = await FileReader._read_text(file_path)
                if text and len(text.strip()) > 0:
                    return text
        except Exception as e:
            logger.error(f"Error reading file {file_name}: {e}")
        return f"⚠️ Не удалось извлечь текст из файла: {file_name}"

    @staticmethod
    async def _read_pdf(file_path: str) -> str:
        if not PDF_AVAILABLE:
            return "❌ Установите: pip install PyPDF2"
        text_parts = []
        with open(file_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            num_pages = len(reader.pages)
            for page_num in range(min(num_pages, 100)):
                try:
                    page = reader.pages[page_num]
                    text = page.extract_text()
                    if text:
                        text_parts.append(f"[Страница {page_num + 1}]\n{text}")
                except Exception:
                    continue
        result = "\n\n".join(text_parts)
        if len(result) > FileReader.MAX_TEXT_LENGTH:
            result = result[:FileReader.MAX_TEXT_LENGTH] + f"\n\n... [обрезано, страниц: {num_pages}]"
        return result

    @staticmethod
    async def _read_docx(file_path: str) -> str:
        if not DOCX_AVAILABLE:
            return "❌ Установите: pip install python-docx"
        doc = Document(file_path)
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        text = "\n".join(paragraphs)
        if len(text) > FileReader.MAX_TEXT_LENGTH:
            text = text[:FileReader.MAX_TEXT_LENGTH] + "..."
        return text

    @staticmethod
    async def _read_text(file_path: str) -> str:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        if len(content) > FileReader.MAX_TEXT_LENGTH:
            content = content[:FileReader.MAX_TEXT_LENGTH] + "\n\n... [обрезано]"
        return content


file_reader = FileReader()


# =============================================================
# КЛАВИАТУРЫ
# =============================================================

def get_language_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru")],
        [InlineKeyboardButton(text="🇺🇿 O'zbek", callback_data="lang_uz")],
        [InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en")],
    ])


def get_payment_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Telegram Stars (100 зв.)", callback_data="pay_stars")],
        [InlineKeyboardButton(text="₿ CryptoBot ($2)", callback_data="pay_crypto")],
        [InlineKeyboardButton(text="💳 Карта Узбекистан (20 000 сум)", callback_data="pay_card")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="action_settings")],
    ])


def get_main_keyboard(user_id: int):
    lang = user_languages.get(user_id, "ru")
    model_key = get_user_model(user_id)
    model_name = FREE_MODELS.get(model_key, {}).get("name", "❓")

    labels = TRANSLATIONS.get(lang, TRANSLATIONS["ru"])

    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 " + labels.get("menu_search", "Поиск"), callback_data="action_search")],
        [InlineKeyboardButton(text=f"🧠 {labels.get('model_select', 'Модель')}: {model_name}", callback_data="action_select_model")],
        [InlineKeyboardButton(text="🔄 " + labels.get("menu_facts", "Фактчек"), callback_data="action_new_topic"),
         InlineKeyboardButton(text="📊 Статистика", callback_data="action_stats")],
        [InlineKeyboardButton(text="🌐 " + labels.get("menu_language", "Язык"), callback_data="action_language"),
         InlineKeyboardButton(text="💰 " + labels.get("menu_payment", "Пополнить"), callback_data="action_payment")],
        [InlineKeyboardButton(text="ℹ️ " + labels.get("menu_help", "Помощь"), callback_data="action_help"),
         InlineKeyboardButton(text="⚙️ " + labels.get("menu_settings", "Настройки"), callback_data="action_settings")],
        [InlineKeyboardButton(text="🔴 Админ-панель", callback_data="action_admin")],
    ])


def get_quick_reply_keyboard(user_id: int):
    """Маленькое меню после каждого ответа"""
    model_key = get_user_model(user_id)
    model_info = FREE_MODELS.get(model_key, FREE_MODELS[DEFAULT_MODEL])
    model_name = model_info["name"].split(" ", 1)[1] if " " in model_info["name"] else model_info["name"]
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🔄 {model_name}", callback_data="action_select_model"),
         InlineKeyboardButton(text="🗑️ Новая тема", callback_data="action_new_topic")],
    ])


def get_back_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙  Назад", callback_data="action_main_menu")]
    ])


def get_model_keyboard():
    buttons = []
    for key, info in FREE_MODELS.items():
        icon = "✅ " if key == DEFAULT_MODEL else "  "
        buttons.append([
            InlineKeyboardButton(
                text=f"{icon}{info['name']}",
                callback_data=f"select_model_{key}"
            )
        ])
    buttons.append([InlineKeyboardButton(text="🔙  Назад", callback_data="action_main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_admin_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика бота", callback_data="admin_stats")],
        [InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users")],
        [InlineKeyboardButton(text="🧠 Использование моделей", callback_data="admin_models")],
        [InlineKeyboardButton(text="📁 Типы файлов", callback_data="admin_files")],
        [InlineKeyboardButton(text="⚙️ Настройки бота", callback_data="admin_settings")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="🔄 Перезапустить бота", callback_data="admin_restart")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="action_main_menu")],
    ])


# =============================================================
# ДЕКОРАТОР АДМИНА
# =============================================================

def admin_only(func):
    async def wrapper(message: Message, *args, **kwargs):
        if message.from_user.id != ADMIN_ID:
            await message.answer("🚫 Доступ запрещён! Только для администратора.")
            return
        return await func(message, *args, **kwargs)
    return wrapper


# =============================================================
# КОМАНДЫ
# =============================================================

@router.message(CommandStart())
async def cmd_start(message: Message):
    if message.from_user.id not in user_languages:
        await message.answer(
            f"🤗 Привет, {message.from_user.full_name}!\n\nВыбери язык / Tilni tanlang / Choose language:",
            reply_markup=get_language_keyboard()
        )
    else:
        await show_main_menu(message)


async def show_main_menu(message: Message):
    user_id = message.from_user.id
    lang = user_languages.get(user_id, "ru")
    labels = TRANSLATIONS.get(lang, TRANSLATIONS["ru"])

    model_key = get_user_model(user_id)
    model_info = FREE_MODELS.get(model_key, FREE_MODELS[DEFAULT_MODEL])

    welcome = (
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🤗 *Привет, {message.from_user.first_name}!* 🇷🇺\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Я — *AI-ассистент* ✨\n\n"
        "┌─────────────────────┐\n"
        "│ 🤖  AI-чат          │\n"
        "│ 🖼  Распознавание   │\n"
        "│ 📄  Чтение файлов   │\n"
        "│ 🔍  Веб-поиск       │\n"
        "│ ✅  Проверка фактов │\n"
        "└─────────────────────┘\n\n"
        f"🧠 *Модель:* {model_info['name']}\n"
        f"📝 {model_info['description']}\n\n"
        "Напиши что угодно или отправь фото!"
    )
    await message.answer(welcome, reply_markup=get_main_keyboard(user_id))
    stats["total_users"].add(message.from_user.id)
    update_stats("command", "start")


@router.message(Command("help"))
async def cmd_help(message: Message):
    help_text = (
        "┏━━━━━━━━━━━━━━━━━━━━━━━┓\n"
        "📝  <b>Справка по боту</b>\n"
        "┣━━━━━━━━━━━━━━━━━━━━━━━┫\n\n"
        "<b>📌 Команды:</b>\n"
        "/start  — Главное меню\n"
        "/help   — Эта справка\n"
        "/clear  — Очистить историю\n"
        "/stats  — Статистика (админ)\n"
        "/settings — Настройки\n\n"
        "<b>🌟 Возможности:</b>\n"
        "1️⃣  Напишите текст — AI ответит\n"
        "2️⃣  Отправьте фото — распознаю содержимое\n"
        "3️⃣  Отправьте файл — прочитаю и проанализирую\n"
        "4️⃣  «найди ...» — веб-поиск\n"
        "5️⃣  «проверь ...» — фактчекинг\n\n"
        "<b>💡 Примеры:</b>\n"
        "• Объясни квантовую физику простыми словами\n"
        "• Найди последние новости про AI\n"
        "• Проверь факт: Солнце вращается вокруг Земли\n"
        "• Что на этом фото? (отправь картинку)\n\n"
        "┗━━━━━━━━━━━━━━━━━━━━━━━┛"
    )
    await message.answer(help_text.strip())
    update_stats("command", "help")


@router.message(Command("clear"))
async def cmd_clear(message: Message):
    ai_engine.clear_context(message.from_user.id)
    await message.answer(
        "🗑 <b>Контекст диалога очищен!</b>\nНачнём с чистого листа 🌱",
        reply_markup=get_main_keyboard(message.from_user.id)
    )


@router.message(Command("model"))
async def cmd_model(message: Message):
    text = "🧠 <b>Выбор модели AI</b>\n\nВыберите модель:"
    await message.answer(text, reply_markup=get_model_keyboard())


@router.message(Command("new"))
async def cmd_new(message: Message):
    ai_engine.clear_context(message.from_user.id)
    await message.answer(
        "🔄 <b>Новая тема!</b>\nКонтекст очищен. Начнём с чистого листа.\n\nНапишите ваш вопрос!",
        reply_markup=get_quick_reply_keyboard(message.from_user.id)
    )


@router.message(Command("settings"))
async def cmd_settings(message: Message):
    model_key = get_user_model(message.from_user.id)
    model_info = FREE_MODELS.get(model_key, FREE_MODELS[DEFAULT_MODEL])
    await message.answer(
        f"⚙️ <b>Настройки</b>\n\n"
        f"👤 <b>Пользователь:</b> {message.from_user.full_name}\n"
        f"🆔 <b>ID:</b> <code>{message.from_user.id}</code>\n"
        f"🧠 <b>Модель:</b> {model_info['name']}\n"
        f"📝 <b>Описание:</b> {model_info['description']}\n"
        f"💾 <b>История диалога:</b> Последние {MAX_CONTEXT_MESSAGES} сообщений\n",
        reply_markup=get_back_keyboard()
    )


@router.message(Command("stats"))
async def cmd_stats(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("🚫 Доступ запрещён! Только для администратора.")
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="action_admin")]
    ])
    await show_admin_stats(message, kb)


# =============================================================
# ОБРАБОТКА ТЕКСТА
# =============================================================

@router.message(F.text)
async def handle_text(message: Message):
    user_id = message.from_user.id
    text = (message.text or "").strip()

    if text.lower().startswith(("найди ", "поиск ", "ищи ", "search ", "/search ")):
        query = text.split(" ", 1)[1] if " " in text else text
        await handle_search(message, query)
        return

    if text.lower().startswith(("проверь ", "фактчек ", "проверить ", "/check ")):
        claim = text.split(" ", 1)[1] if " " in text else text
        await bot.send_chat_action(message.chat.id, "typing")
        result = await web_search.fact_check(claim)
        await message.answer(result)
        update_stats("command", "factcheck")
        return

    await bot.send_chat_action(message.chat.id, "typing")

    try:
        response = await ai_engine.send_message(user_id=user_id, user_message=text)
        await message.answer(response, reply_markup=get_quick_reply_keyboard(user_id))
    except Exception as e:
        logger.error(f"Text handler error: {e}")
        await message.answer("❌ Произошла ошибка. Попробуйте позже.")
        update_stats("error", "text_handler")


async def handle_search(message: Message, query: str):
    user_id = message.from_user.id
    await message.answer("🔍 <b>Ищу информацию...</b>")

    try:
        results = await web_search.search(query, num_results=5)
        if not results:
            await message.answer("😕 Ничего не найдено. Попробуйте переформулировать запрос.")
            return

        await bot.send_chat_action(message.chat.id, "typing")

        response = await ai_engine.send_message(
            user_id=user_id,
            user_message=f"Ответь на вопрос на основе источников: {query}",
            web_results=results
        )
        await message.answer(response, reply_markup=get_quick_reply_keyboard(user_id))
        update_stats("command", "search")
    except Exception as e:
        logger.error(f"Search error: {e}")
        await message.answer("❌ Ошибка при поиске.")


# =============================================================
# ОБРАБОТКА ФОТО
# =============================================================

@router.message(F.photo)
async def handle_photo(message: Message):
    user_id = message.from_user.id
    model_key = get_user_model(user_id)
    model_info = FREE_MODELS.get(model_key, FREE_MODELS[DEFAULT_MODEL])
    
    if not model_info.get("supports_vision"):
        await message.answer(f"❌ Модель {model_info['name']} не поддерживает картинки. Выбери другую модель с поддержкой vision (/model)")
        return
    
    await bot.send_chat_action(message.chat.id, "typing")

    try:
        photo = message.photo[-1]
        file_obj = await bot.get_file(photo.file_id)
        file_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_obj.file_path}"

        response = await ai_engine.send_message(
            user_id=user_id,
            user_message="Проанализируй это изображение. Опиши что на нём, расшифруй текст если есть.",
            image_url=file_url
        )
        await message.answer(response, reply_markup=get_quick_reply_keyboard(user_id))
        update_stats("command", "photo_analysis")
    except Exception as e:
        logger.error(f"Photo handler error: {e}")
        await message.answer("❌ Ошибка при обработке изображения.")
        update_stats("error", "photo")


# =============================================================
# ОБРАБОТКА ДОКУМЕНТОВ (с try/finally для temp-файлов)
# =============================================================

SUPPORTED_EXTENSIONS = {'.pdf', '.docx', '.doc', '.txt', '.md', '.csv',
                        '.log', '.json', '.xml', '.html', '.py', '.js',
                        '.cpp', '.java', '.yml', '.yaml'}


@router.message(F.document)
async def handle_document(message: Message):
    user_id = message.from_user.id
    await bot.send_chat_action(message.chat.id, "typing")

    tmp_path = None
    try:
        doc = message.document
        file_name = doc.file_name or "unknown"
        file_size = doc.file_size or 0

        if file_size > MAX_FILE_SIZE:
            await message.answer(f"❌ Файл слишком большой. Максимум {MAX_FILE_SIZE // (1024*1024)} МБ.")
            return

        ext = os.path.splitext(file_name)[1].lower()
        if ext not in SUPPORTED_EXTENSIONS:
            await message.answer(
                f"⚠️ Формат <code>{ext}</code> не поддерживается.\n"
                f"Поддерживаемые: PDF, DOCX, TXT, MD, CSV, JSON, код и др.",
                parse_mode="HTML"
            )
            return

        await message.answer("📥 <b>Скачиваю файл...</b>")

        file_obj = await bot.get_file(doc.file_id)
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp_path = tmp.name

        await bot.download_file(file_obj.file_path, tmp_path)

        await message.answer("📄 <b>Извлекаю текст...</b>")
        content = await file_reader.read_file(tmp_path, mime_type=doc.mime_type, file_name=file_name)

        file_type = ext.lstrip('.')
        update_stats("file", file_type)

        await bot.send_chat_action(message.chat.id, "typing")

        response = await ai_engine.send_message(
            user_id=user_id,
            user_message=f"Проанализируй файл: {file_name}",
            file_text=content
        )
        await message.answer(response, reply_markup=get_quick_reply_keyboard(user_id))

    except Exception as e:
        logger.error(f"Document handler error: {e}")
        await message.answer("❌ Ошибка при обработке документа.")
        update_stats("error", "document")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


# =============================================================
# CALLBACK-ОБРАБОТЧИКИ
# =============================================================

@router.callback_query(F.data == "action_main_menu")
async def cb_main_menu(callback: CallbackQuery):
    text = "🏠 <b>Главное меню</b>\n\nВыберите действие:"
    kb = get_main_keyboard(callback.from_user.id)
    await safe_edit(callback, text, reply_markup=kb)


@router.callback_query(F.data == "action_search")
async def cb_search(callback: CallbackQuery):
    text = (
        "🔍 <b>Поиск в интернете</b>\n\n"
        "Напишите ваш запрос!\n\n"
        "Пример: <code>найди новости про ИИ</code>"
    )
    kb = get_back_keyboard()
    await safe_edit(callback, text, reply_markup=kb)


@router.callback_query(F.data == "action_analyze")
async def cb_analyze(callback: CallbackQuery):
    text = (
        "📄 <b>Анализ файла</b>\n\n"
        "Отправьте мне файл и я прочитаю и проанализирую его.\n\n"
        f"📋 Форматы: <code>PDF</code> <code>DOCX</code> <code>TXT</code> "
        f"<code>MD</code> <code>CSV</code> <code>JSON</code> <code>код</code> и др.\n\n"
        f"🔒 Макс. размер: {MAX_FILE_SIZE // (1024*1024)} МБ"
    )
    kb = get_back_keyboard()
    await safe_edit(callback, text, reply_markup=kb)


@router.callback_query(F.data == "action_ocr")
async def cb_ocr(callback: CallbackQuery):
    text = (
        "🖼 <b>Распознавание картинки</b>\n\n"
        "Отправьте мне изображение, и я:\n"
        "• Опишу содержимое\n"
        "• Распознаю текст (OCR)\n"
        "• Проанализирую графики и диаграммы"
    )
    kb = get_back_keyboard()
    await safe_edit(callback, text, reply_markup=kb)


@router.callback_query(F.data == "action_select_model")
async def cb_select_model(callback: CallbackQuery):
    text = "🧠 <b>Выбор модели AI</b>\n\nВыберите модель для ответов:"
    kb = get_model_keyboard()
    await safe_edit(callback, text, reply_markup=kb)


@router.callback_query(F.data.startswith("select_model_"))
async def cb_model_selected(callback: CallbackQuery):
    model_key = callback.data.replace("select_model_", "")

    if model_key not in FREE_MODELS:
        await callback.answer("❌ Модель не найдена!", show_alert=True)
        return

    model_info = FREE_MODELS[model_key]

    user_models[callback.from_user.id] = model_key
    update_stats("command", f"model_select_{model_key}")

    vision_emoji = "👁" if model_info["supports_vision"] else "🚫"

    text = (
        f"✅ <b>Модель изменена!</b>\n\n"
        f"🧠 <b>Текущая модель:</b> {model_info['name']}\n"
        f"📝 <b>Описание:</b> {model_info['description']}\n"
        f"👁 <b>Поддержка картинок:</b> {vision_emoji}\n"
    )
    kb = get_main_keyboard(callback.from_user.id)
    await safe_edit(callback, text, reply_markup=kb)


@router.callback_query(F.data == "action_new_topic")
async def cb_new_topic(callback: CallbackQuery):
    ai_engine.clear_context(callback.from_user.id)
    text = "🔄 <b>Контекст очищен!</b> Начнём новую тему.\n\nЧем могу помочь?"
    kb = get_main_keyboard(callback.from_user.id)
    await safe_edit(callback, text, reply_markup=kb)


@router.callback_query(F.data == "action_help")
async def cb_help(callback: CallbackQuery):
    text = (
        "ℹ️ <b>Помощь</b>\n\n"
        "<b>Команды:</b>\n"
        "/start — Главное меню\n"
        "/help — Эта справка\n"
        "/clear — Очистить историю\n\n"
        "<b>Что умею:</b>\n"
        "💬 Просто напишите текст\n"
        "🖼 Отправьте фото для анализа\n"
        "📄 Отправьте файл для чтения\n"
        "🔍 Напишите «найди ...» для поиска\n"
        "✅ Напишите «проверь ...» для фактчекинга"
    )
    kb = get_back_keyboard()
    await safe_edit(callback, text, reply_markup=kb)


@router.callback_query(F.data == "action_settings")
async def cb_settings(callback: CallbackQuery):
    model_key = get_user_model(callback.from_user.id)
    model_info = FREE_MODELS.get(model_key, FREE_MODELS[DEFAULT_MODEL])

    text = (
        f"⚙️ <b>Настройки</b>\n\n"
        f"👤 <b>Пользователь:</b> {callback.from_user.full_name}\n"
        f"🆔 <b>ID:</b> <code>{callback.from_user.id}</code>\n"
        f"🧠 <b>Модель:</b> {model_info['name']}\n"
        f"📝 <b>Описание:</b> {model_info['description']}\n"
        f"💾 <b>История диалога:</b> Последние {MAX_CONTEXT_MESSAGES} сообщений\n"
    )
    kb = get_back_keyboard()
    await safe_edit(callback, text, reply_markup=kb)


@router.callback_query(F.data == "action_language")
async def cb_language(callback: CallbackQuery):
    await callback.message.edit_text(
        "🌐 *Выберите язык / Tilni tanlang / Choose language:*",
        reply_markup=get_language_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("lang_"))
async def cb_lang_selected(callback: CallbackQuery):
    lang = callback.data.replace("lang_", "")
    user_languages[callback.from_user.id] = lang

    labels = TRANSLATIONS.get(lang, TRANSLATIONS["ru"])
    await callback.answer(f"✅ Язык: {LANGUAGES.get(lang, lang)}", show_alert=True)

    text = labels.get("welcome", "Готово!").format(name=callback.from_user.full_name)
    await callback.message.edit_text(text, reply_markup=get_main_keyboard(callback.from_user.id))


@router.callback_query(F.data == "action_payment")
async def cb_payment(callback: CallbackQuery):
    lang = user_languages.get(callback.from_user.id, "ru")
    labels = TRANSLATIONS.get(lang, TRANSLATIONS["ru"])

    text = labels.get("payment_title", "💰 Пополнение баланса") + "\n\n"
    text += labels.get("payment_crypto", "CryptoBot ($2/неделя)") + "\n"
    text += labels.get("payment_card", "Карта Узбекистан (20 000 сум/неделя)")

    await callback.message.edit_text(text, reply_markup=get_payment_keyboard())
    await callback.answer()


@router.callback_query(F.data == "pay_crypto")
async def cb_pay_crypto(callback: CallbackQuery):
    lang = user_languages.get(callback.from_user.id, "ru")
    labels = TRANSLATIONS.get(lang, TRANSLATIONS["ru"])

    await callback.message.edit_text(
        f"{labels.get('payment_wait', '⏳ Ожидаю оплату...')}\n\n"
        "Перейди в @CryptoBot и отправь $2 на:\n"
        "`YOUR_WALLET_ADDRESS`\n\n"
        "После оплаты нажми 'Проверить оплату'"
    )
    await callback.answer()


@router.callback_query(F.data == "pay_card")
async def cb_pay_card(callback: CallbackQuery):
    await callback.message.edit_text(
        "💳 *Пополнение карты Узбекистан*\n\n"
        "Номер карты: `8600 1234 5678 9010`\n"
        "Сумма: `20 000` сум\n\n"
        "После оплаты нажми 'Проверить'"
    )
    await callback.answer()


@router.callback_query(F.data == "pay_stars")
async def cb_pay_stars(callback: CallbackQuery):
    await callback.message.edit_text("⏳ Отправляю счёт...")

    try:
        await bot.send_invoice(
            chat_id=callback.from_user.id,
            title="Подписка AI Bot Premium",
            description="100 звёзд в неделю",
            payload="stars_subscription",
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice(label="100 звёзд", amount=100)]
        )
    except Exception as e:
        logger.error(f"Stars invoice error: {e}")
        await callback.message.edit_text(
            "⚠️ Ошибка отправки счёта.\n"
            "Попробуй позже или выбери другой способ оплаты."
        )
    await callback.answer()


@router.pre_checkout_query()
async def process_pre_checkout(pre_checkout: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout.id, ok=True)


@router.message(F.successful_payment)
async def process_successful_payment(message: Message):
    await message.answer("✅ Спасибо! Оплата получена!\n\nПодписка активирована на неделю!")
    logger.info(f"Payment from {message.from_user.id}: {message.successful_payment}")


@router.callback_query(F.data == "action_stats")
async def cb_stats(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("📊 Статистика доступна только для админа.", show_alert=True)
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="action_admin")]
    ])
    await show_admin_stats(callback, kb)


# =============================================================
# 🔴 АДМИН-ПАНЕЛЬ
# =============================================================

@router.callback_query(F.data == "action_admin")
async def cb_admin(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("🚫 Доступ запрещён!", show_alert=True)
        return

    text = (
        "🔴 <b>АДМИН-ПАНЕЛЬ</b>\n\n"
        f"👤 Админ: <code>{callback.from_user.id}</code>\n"
        f"🕐 Бот запущен: <code>{stats['start_time'][:19]}</code>\n\n"
        "Выберите действие:"
    )
    kb = get_admin_keyboard()
    await safe_edit(callback, text, reply_markup=kb)


async def show_admin_stats(source, keyboard):
    now = datetime.now(timezone.utc)
    uptime_seconds = (now - datetime.fromisoformat(stats["start_time"])).total_seconds()
    hours = int(uptime_seconds // 3600)
    minutes = int((uptime_seconds % 3600) // 60)

    stats_text = (
        f"🔴 <b>СТАТИСТИКА БОТА</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📊 <b>Общая статистика:</b>\n"
        f"├ Всего сообщений: <b>{stats['total_messages']}</b>\n"
        f"├ Сообщений сегодня: <b>{stats['messages_today']}</b>\n"
        f"├ Всего пользователей: <b>{len(stats['total_users'])}</b>\n"
        f"├ Ошибок: <b>{stats['errors']}</b>\n"
        f"└ Аптайм: <b>{hours}ч {minutes}мин</b>\n\n"
        f"📈 <b>Использование моделей:</b>\n"
    )

    if stats["model_usage"]:
        max_usage = max(stats["model_usage"].values())
        for model_key, count in sorted(stats["model_usage"].items(), key=lambda x: -x[1]):
            model_name = FREE_MODELS.get(model_key, {}).get("name", model_key)
            bar_len = min(int(count / max_usage * 20), 20)
            bar = "█" * bar_len + "░" * (20 - bar_len)
            stats_text += f"├ {model_name}: <b>{count}</b>\n"
            stats_text += f"│  <code>{bar}</code>\n"
    else:
        stats_text += "├ Нет данных\n"

    stats_text += "\n📁 <b>Типы файлов:</b>\n"
    if stats["file_types"]:
        for ftype, count in sorted(stats["file_types"].items(), key=lambda x: -x[1]):
            stats_text += f"├ <code>.{ftype}</code>: <b>{count}</b>\n"
    else:
        stats_text += "├ Нет данных\n"

    stats_text += "\n⚡ <b>Команды:</b>\n"
    if stats["command_usage"]:
        for cmd, count in sorted(stats["command_usage"].items(), key=lambda x: -x[1]):
            stats_text += f"├ <code>/{cmd}</code>: <b>{count}</b>\n"
    else:
        stats_text += "├ Нет данных\n"

    if isinstance(source, CallbackQuery):
        await source.message.edit_text(stats_text.strip(), reply_markup=keyboard, parse_mode="HTML")
        await source.answer()
    else:
        await source.answer(stats_text.strip(), reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data == "admin_stats")
async def cb_admin_stats(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("🚫 Доступ запрещён!", show_alert=True)
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="action_admin")]
    ])
    await show_admin_stats(callback, kb)


@router.callback_query(F.data == "admin_users")
async def cb_admin_users(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("🚫 Доступ запрещён!", show_alert=True)
        return

    users_text = "👥 <b>Пользователи:</b>\n\n"
    for uid in sorted(stats["total_users"]):
        users_text += f"• <code>{uid}</code>\n"
    users_text += f"\n👥 Всего: <b>{len(stats['total_users'])}</b>"

    kb = get_admin_keyboard()
    await safe_edit(callback, users_text, reply_markup=kb)


@router.callback_query(F.data == "admin_models")
async def cb_admin_models(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("🚫 Доступ запрещён!", show_alert=True)
        return

    models_text = "🧠 <b>Использование моделей:</b>\n\n"
    if stats["model_usage"]:
        max_usage = max(stats["model_usage"].values())
        for model_key, count in sorted(stats["model_usage"].items(), key=lambda x: -x[1]):
            model_name = FREE_MODELS.get(model_key, {}).get("name", model_key)
            pct = (count / max_usage) * 100
            models_text += f"├ {model_name}: <b>{count}</b> ({pct:.0f}%)\n"
    else:
        models_text += "├ Нет данных\n"

    kb = get_admin_keyboard()
    await safe_edit(callback, models_text, reply_markup=kb)


@router.callback_query(F.data == "admin_files")
async def cb_admin_files(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("🚫 Доступ запрещён!", show_alert=True)
        return

    files_text = "📁 <b>Типы загруженных файлов:</b>\n\n"
    if stats["file_types"]:
        for ftype, count in sorted(stats["file_types"].items(), key=lambda x: -x[1]):
            files_text += f"├ <code>.{ftype}</code>: <b>{count}</b>\n"
    else:
        files_text += "├ Нет данных\n"

    kb = get_admin_keyboard()
    await safe_edit(callback, files_text, reply_markup=kb)


@router.callback_query(F.data == "admin_restart")
async def cb_admin_restart(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("🚫 Доступ запрещён!", show_alert=True)
        return

    await callback.answer("🔄 Перезапуск...")
    try:
        await bot.send_message(callback.from_user.id, "🔄 Бот перезапускается...")
    except Exception:
        pass
    await bot.session.close()

    # Windows-friendly restart: subprocess + sys.exit
    subprocess_path = None
    for p in [sys.executable, sys.argv[0] if sys.argv else None]:
        if p and os.path.exists(p):
            subprocess_path = p
            break

    if subprocess_path:
        import subprocess
        subprocess.Popen([subprocess_path] + sys.argv[1:])
    sys.exit(0)


# =============================================================
# ЗАПУСК
# =============================================================

async def main(bot_instance: Bot):
    global bot
    bot = bot_instance
    
    dp.include_router(router)

    # Регистрация команд бота
    from aiogram.types import BotCommand
    await bot.set_my_commands([
        BotCommand(command="start", description="Главное меню"),
        BotCommand(command="help", description="Помощь"),
        BotCommand(command="model", description="Сменить модель"),
        BotCommand(command="new", description="Новая тема"),
        BotCommand(command="clear", description="Очистить историю"),
    ])

    logger.info("=" * 50)
    logger.info("🤖 Telegram AI-Bot запускается...")
    logger.info(f"🧠 Модель по умолчанию: {FREE_MODELS[DEFAULT_MODEL]['name']}")
    logger.info(f"👤 Admin ID: {ADMIN_ID}")
    logger.info(f"📊 Моделей: {len(FREE_MODELS)}")
    logger.info("=" * 50)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


# =============================================================
# HEALTH CHECK (чтобы бот не засыпал на Render)
# =============================================================
async def health_check_server():
    from aiohttp import web
    
    async def health(request):
        return web.Response(text="OK", status=200)
    
    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8000)
    await site.start()
    logger.info("🌐 Health check server started on port 8000")


KEEP_ALIVE_INTERVAL = 300


async def keep_alive_pinger():
    last_ping = 0
    while True:
        try:
            current_time = time.time()
            if current_time - last_ping >= KEEP_ALIVE_INTERVAL:
                if ADMIN_ID != 0:
                    msg = await bot.send_message(ADMIN_ID, "🔄 Бот активен")
                    await asyncio.sleep(50)
                    try:
                        await msg.delete()
                    except Exception:
                        pass
                    last_ping = current_time
                else:
                    last_ping = current_time
        except Exception as e:
            logger.warning(f"Keep-alive error: {e}")
        await asyncio.sleep(10)


if __name__ == "__main__":
    if "--hidden" in sys.argv:
        ctypes.windll.kernel32.FreeConsole()
    
    print("=" * 50)
    print("🤖 Telegram AI-бот v3 (исправленная)")
    print("=" * 50)

    if not TELEGRAM_TOKEN:
        print("❌ ОШИБКА: Укажите TELEGRAM_TOKEN в .env файле!")
        print("   Пример: TELEGRAM_TOKEN=123456:ABCdef...")
        exit(1)
    if not OPENROUTER_API_KEY:
        print("❌ ОШИБКА: Укажите OPENROUTER_API_KEY в .env файле!")
        print("   Получить ключ: https://openrouter.ai/")
        exit(1)
    if ADMIN_ID == 0:
        print("⚠️  ВНИМАНИЕ: ADMIN_ID не указан! Админ-панель будет недоступна.")
        print("   Укажите ADMIN_ID в .env файле (ваш Telegram ID).")

    # Запускаем бота и health check вместе
    bot = Bot(token=TELEGRAM_TOKEN)

    async def run_all():
        await asyncio.gather(
            main(bot),
            health_check_server(),
            keep_alive_pinger()
        )

    asyncio.run(run_all())
