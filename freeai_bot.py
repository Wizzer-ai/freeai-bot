"""
FreeAI Bot — генератор комбинаций точек для Gmail
==================================================
"""

import asyncio
import json
import logging
import os
import sys
import tempfile
from datetime import datetime, timezone
from uuid import uuid4

import aiohttp

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup,
    InlineKeyboardButton, FSInputFile, LabeledPrice, PreCheckoutQuery
)
from aiogram.exceptions import TelegramBadRequest

# =============================================================
# ЯЗЫКИ
# =============================================================
LANGUAGES = {"ru": "Русский", "uz": "O'zbek", "en": "English"}

TRANSLATIONS = {
    "ru": {
        "welcome": "👋 Добро пожаловать в FreeAI Bot!\n\n🤖 Этот бот умеет:\n• Давать доступ к AI сервисам\n• Реферальная программа с заработком\n\n🔥 Нажми «ℹ️ Помощь» чтобы узнать как пользоваться ботом!",
        "help": "ℹ️ Как пользоваться ботом:\n\n1️⃣ 💰 Оплати доступ или приведи друга по реф-ссылке\n2️⃣ 📧 Отправь свой Gmail адрес (например, freeai@gmail.com)\n3️⃣ ⏳ Бот сгенерирует все комбинации с точками\n4️⃣ ◀️ ▶️ Листай список кнопками\n5️⃣ 📎 Файл со всеми вариантами придет автоматически\n\n🔑 Пароль от всех вариантов такой же, как у оригинала\n\n👥 Рефералы: делись ссылкой — получай 10% с каждой оплаты",
        "lang_changed": "✅ Язык: Русский",
        "menu_language": "🌐 Язык",
        "menu_help": "ℹ️ Помощь",
        "menu_dots": "📧 Сгенерировать почту",
        "menu_how": "ℹ️ Как работает",
        "menu_services": "🔗 Сервисы",
        "how_text": "📘 Как работает бот:\n\n1️⃣ Gmail игнорирует точки в имени.\n   <code>n.ame@gmail.com</code> = <code>name@gmail.com</code>\n\n2️⃣ Можно вставлять точки между буквами.\n\n3️⃣ Можно добавлять +текст после имени.\n   <code>name+shop@gmail.com</code>\n\n🎯 Для чего это нужно?\n• Сортировка писем\n• Отслеживание источников регистрации\n• Тестирование форм\n• Создание фильтров в Gmail\n\n⚠ Все письма приходят в один ящик.",
        "services_text": "🔗 Полезные сервисы\n\n💬 ИИ чаты:\n• Gemini — gemini.google.com\n• ChatGPT — chatgpt.com\n• Claude — claude.ai\n• DeepSeek — chat.deepseek.com\n\n🎨 ИИ для фото и видео:\n• Google Flow (Nano Banana, Veo 3.1) — labs.google/fx/ru/tools/flow\n   🎬 Видео до 8 сек на Veo 3.1\n• Hailuo AI — hailuoai.video\n• Seedance — seedance2.ai\n\n📊 ИИ для презентаций:\n• Gamma — gamma.app\n\n📎 Отправь мне email и получи комбинации с точками!",
        "get_email_text": "📧 Отправь мне Gmail адрес (например, <code>freeai@gmail.com</code>), и я сгенерирую ВСЕ возможные варианты расстановки точек!\n\nВсе они доставят письмо в один почтовый ящик ✅",
        "dots_title": "📧 Генератор точек для Gmail\n\nОтправь мне email — я сгенерирую ВСЕ возможные комбинации с точками!\n\nПример: <code>freeai@gmail.com</code>",
        "dots_wait": "⏳ Генерирую комбинации...",
        "dots_result": "✅ Готово! {total} комбинаций",
        "dots_item": "{n} из {total}\n\n<code>{email}</code>\n\n🔑 Пароль такой же, как у оригинала",
        "dots_empty": "❌ Введи email.\n\nПример: <code>freeai@gmail.com</code>",
        "dots_invalid": "❌ Неверный формат. Нужно: <code>local@domain.com</code>",
        "dots_long": "❌ Слишком длинный ({n} символов). Будет {total} комбинаций.",
        "dots_info": "ℹ️ Gmail игнорирует точки. Все варианты доставят письмо в тот же ящик!",
        "dots_total": "📊 Для {email}: {total} комбинаций",
        "dots_file": "📎 Все {total} комбинаций для {email}",
        "dots_warn": "⚠️ {total} комбинаций — много. Подожди.",
        "btn_prev": "◀️ Пред.",
        "btn_next": "След. ▶️",
        "access_denied": "❌ Доступ не получен\n\nНажми «🔓 Получить доступ» в меню",
        "access_button": "🔓 Получить доступ",
        "pay_title": "💎 Выберите способ оплаты:",
        "pay_stars": "⭐ 2000 Stars",
        "pay_crypto": "💰 $15 (CryptoBot)",
        "pay_crypto_creating": "⏳ Создаю счёт...",
        "pay_crypto_ready": "💰 Счёт на $15 USDT:\n{url}\n\nПосле оплаты нажмите «✅ Я оплатил» — админ подтвердит доступ",
        "pay_crypto_direct": "💰 Оплатите $15 USDT на @costgold — он откроет доступ\n\nИли используйте оплату ⭐ Stars",
        "pay_i_paid": "✅ Я оплатил",
        "pay_notify_done": "✅ Уведомление отправлено администратору! Ожидайте подтверждения.",
        "pay_success": "✅ Оплата получена! Доступ открыт.",
        "pay_stars_label": "Доступ к боту",
        "pay_stars_title": "FreeAI Bot — доступ",
        "pay_stars_desc": "Доступ к генератору комбинаций точек для Gmail",
        "pay_stars_link": "💎 Оплатите по ссылке:\n{url}",
        "menu_reviews": "⭐ Отзывы",
        "reviews_text": "⭐ Отзывы о боте\n\nСкоро здесь появятся отзывы пользователей!",
        "menu_ref": "👥 Рефералы",
        "menu_profile": "👤 Профиль",
        "profile_title": "👤 Профиль\n🆔 ID: {user_id}\n📌 Статус: {status}\n\n💰 Баланс: ${balance:.2f}\n👥 Платных рефералов: {count}\n\n🔥 Получай 10% с каждой оплаты друга!\n\nТвоя реф-ссылка:\n<code>{link}</code>",
        "ref_title": "👥 Реферальная программа\n\nТвоя ссылка:\n<code>{link}</code>\n\nПриведено платных: {count}\n💰 Заработано: ${earnings:.2f}\n\n🔥 Отправляй ссылку друзьям — получай 10% с каждой оплаты!",
        "service_welcome": "🚀 Добро пожаловать в FreeAI Bot!\n\nЭтот бот открывает доступ к безлимитному использованию лучших AI-сервисов:\n\n🧠 <b>Gemini Omni</b> — мощнейшая мультимодальная модель от Google\n🎨 <b>Nano Banana</b> — генерация и редактирование изображений\n🎬 <b>Veo 3.1</b> — создание видео до 8 секунд\n💬 <b>ChatGPT / Claude / DeepSeek</b> — ведущие AI-чаты\n📊 <b>Gamma</b> — AI для презентаций\n\n🔑 После оплаты или одобрения админа — полный доступ к генерации Gmail-комбинаций и всем сервисам!",
        "admin_users_title": "👥 Пользователи ({total}):\n",
        "admin_user_line": "{id} — {status}\n",
        "admin_approved": "✅ Пользователь {id} одобрен",
        "admin_rejected": "❌ Пользователь {id} отклонён",
        "admin_no_access": "❌ Нет доступа",
        "admin_btn_users": "👥 Пользователи",
        "admin_btn_approve": "✅ Одобрить",
        "admin_btn_reject": "❌ Отклонить",
        "admin_user_approved": "✅ Админ одобрил ваш доступ к FreeAI Bot!",
        "admin_access_granted": "✅ Админ одобрил ваш доступ к FreeAI Bot!\n\nНажмите /start чтобы начать",
        "admin_ask_approve": "✅ Одобрить по ID",
        "admin_ask_reject": "❌ Отклонить по ID",
        "admin_enter_id": "✏️ Отправьте ID пользователя (только цифры)\n\nИли нажмите «🔙 Отмена»",
        "admin_cancel": "🔙 Отмена",
        "error_generic": "❌ Ошибка. Попробуйте позже.",
        "error_invalid_id": "Неверный ID",
        "error_no_users": "Нет пользователей",
        "error_usage_approve": "Использование: /approve <user_id>",
        "error_usage_reject": "Использование: /reject <user_id>",
    },
    "uz": {
        "welcome": "👋 FreeAI Ботга хуш келибсиз!\n\n🤖 Бу бот қуйидаги вазифа бажаради:\n• АИ хизматларини чексиз ишлатиш\n• Реферал дастур орқали пул топиш\n\n🔥 «ℹ️ Ёрдам» тугмасини босинг — ботдан қандай фойдаланишни билиб олинг!",
        "help": "ℹ️ Ботдан қандай фойдаланиш:\n\n1️⃣ 💰 Тўлов қилинг ёки дўстингизни реферал ҳавола орқали таклиф қилинг\n2️⃣ 📧 Gmail манзилингизни юборинг (масалан, freeai@gmail.com)\n3️⃣ ⏳ Бот нуқта билан барча комбинацияларни яратади\n4️⃣ ◀️ ▶️ Рўйхатни тугмалар билан айлантиринг\n5️⃣ 📎 Барча вариантлар файли автоматик келади\n\n🔑 Парол барча вариантларда асл email билан бир хил\n\n👥 Рефераллар: ҳаволани улашинг — ҳар бир тўловдан 10% олинг",
        "lang_changed": "✅ Тил: Ўзбек",
        "menu_language": "🌐 Тил",
        "menu_help": "ℹ️ Ёрдам",
        "menu_dots": "📧 Почта яратиш",
        "menu_how": "ℹ️ Қандай ишлайди",
        "menu_services": "🔗 Хизматлар",
        "how_text": "📘 Бот қандай ишлайди:\n\n1️⃣ Gmail нуқталарни эътиборсиз қолдиради.\n   <code>n.ame@gmail.com</code> = <code>name@gmail.com</code>\n\n2️⃣ Нуқталарни ҳарфлар орасига қўйиш мумкин.\n\n3️⃣ Номдан кейин +матн қўшиш мумкин.\n   <code>name+shop@gmail.com</code>\n\n🎯 Нима учун керак?\n• Хатларни саралаш\n• Рўйхатдан ўтиш манбаларини кузатиш\n• Формаларни синаш\n• Gmail фильтрларини яратиш\n\n⚠ Барча хатлар бир қутига келади.",
        "services_text": "🔗 Фойдали хизматлар\n\n💬 AI чатлар:\n• Gemini — gemini.google.com\n• ChatGPT — chatgpt.com\n• Claude — claude.ai\n• DeepSeek — chat.deepseek.com\n\n🎨 AI фото ва видео учун:\n• Google Flow (Nano Banana, Veo 3.1) — labs.google/fx/ru/tools/flow\n   🎬 Veo 3.1 да 8 секундгача видео\n• Hailuo AI — hailuoai.video\n• Seedance — seedance2.ai\n\n📊 AI презентациялар учун:\n• Gamma — gamma.app\n\n📎 Менга email юборинг ва нуқта комбинацияларини олинг!",
        "get_email_text": "📧 Менга Gmail манзилини юборинг (масалан, <code>freeai@gmail.com</code>), мен эса нуқталарни жойлаштиришнинг БАРЧА вариантларини яратаман!\n\nҲаммаси бир қутига етказилади ✅",
        "dots_title": "📧 Gmail нуқта генератори\n\nEmail юборинг — нуқталар билан БАРЧА комбинацияларни яратаман!\n\nМисол: <code>freeai@gmail.com</code>",
        "dots_wait": "⏳ Комбинацияларни яратмоқда...",
        "dots_result": "✅ Тайёр! {total} та комбинация",
        "dots_item": "{n} дан {total}\n\n<code>{email}</code>\n\n🔑 Парол асл email билан бир хил",
        "dots_empty": "❌ Email киритинг.\n\nМисол: <code>freeai@gmail.com</code>",
        "dots_invalid": "❌ Нотўғри формат. Керак: <code>local@domain.com</code>",
        "dots_long": "❌ Жуда узун ({n} та белги). {total} та комбинация.",
        "dots_info": "ℹ️ Gmail нуқталарни эътиборсиз қолдиради. Барча вариантлар бир хил қутига етади!",
        "dots_total": "📊 {email} учун: {total} комбинация",
        "dots_file": "📎 {email} учун барча {total} комбинация",
        "dots_warn": "⚠️ {total} та комбинация — кўп. Кутинг.",
        "btn_prev": "◀️ Олд.",
        "btn_next": "Кей. ▶️",
        "access_denied": "❌ Кириш олинмаган\n\nМенюдан «🔓 Ботни ишлатиш» тугмасини босинг",
        "access_button": "🔓 Ботни ишлатиш",
        "pay_title": "💎 Тўлов усулини танланг:",
        "pay_stars": "⭐ 2000 Stars",
        "pay_crypto": "💰 $15 (CryptoBot)",
        "pay_crypto_creating": "⏳ Ҳисоб яратилмоқда...",
        "pay_crypto_ready": "💰 $15 USDT ли ҳисоб:\n{url}\n\nТўловдан сўнг «✅ Мен тўладим» тугмасини босинг — админ тасдиқлайди",
        "pay_crypto_direct": "💰 $15 USDT ни @costgold га тўланг, у киришни очади\n\n⭐ Stars орқали тўлаш ҳам мумкин",
        "pay_i_paid": "✅ Мен тўладим",
        "pay_notify_done": "✅ Хабар админга юборилди! Тасдиқланишини кутинг.",
        "pay_success": "✅ Тўлов қабул қилинди! Кириш очиқ.",
        "pay_stars_label": "Ботга кириш",
        "pay_stars_title": "FreeAI Bot — кириш",
        "pay_stars_desc": "Gmail нуқта комбинациялари генераторига кириш",
        "pay_stars_link": "💎 Ҳавола орқали тўланг:\n{url}",
        "menu_reviews": "⭐ Фикрлар",
        "reviews_text": "⭐ Бот ҳақида фикрлар\n\nТез орада фойдаланувчи фикрлари пайдо бўлади!",
        "menu_ref": "👥 Рефераллар",
        "menu_profile": "👤 Профил",
        "profile_title": "👤 Профил\n🆔 ID: {user_id}\n📌 Ҳолат: {status}\n\n💰 Баланс: ${balance:.2f}\n👥 Пулли рефераллар: {count}\n\n🔥 Ҳар бир тўловдан 10% олинг!\n\nСизнинг ҳаволангиз:\n<code>{link}</code>",
        "ref_title": "👥 Реферал дастури\n\nСизнинг ҳаволангиз:\n<code>{link}</code>\n\nПулли таклиф: {count}\n💰 Топилган: ${earnings:.2f}\n\n🔥 Дўстларга ҳаволани юборинг — ҳар бир тўловдан 10% олинг!",
        "service_welcome": "🚀 FreeAI Ботга хуш келибсиз!\n\nБу бот энг яхши АИ хизматларидан чексиз фойдаланиш имконини беради:\n\n🧠 <b>Gemini Omni</b> — Google'нинг кучли мультимодал модели\n🎨 <b>Nano Banana</b> — расм яратиш ва таҳрирлаш\n🎬 <b>Veo 3.1</b> — 8 секундгача видео яратиш\n💬 <b>ChatGPT / Claude / DeepSeek</b> — етакчи АИ чатлар\n📊 <b>Gamma</b> — презентациялар учун АИ\n\n🔑 Тўлов ёки админ тасдиқлашидан сўнг — Gmail комбинациялари ва барча хизматларга тўлиқ кириш!",
        "admin_users_title": "👥 Фойдаланувчилар ({total}):\n",
        "admin_user_line": "{id} — {status}\n",
        "admin_approved": "✅ Фойдаланувчи {id} тасдиқланди",
        "admin_rejected": "❌ Фойдаланувчи {id} рад этилди",
        "admin_no_access": "❌ Кириш йўқ",
        "admin_btn_users": "👥 Фойдаланувчилар",
        "admin_btn_approve": "✅ Тасдиқлаш",
        "admin_btn_reject": "❌ Рад этиш",
        "admin_user_approved": "✅ Админ FreeAI Ботга киришингизни тасдиқлади!",
        "admin_access_granted": "✅ Кириш очилди! FreeAI Ботдан фойдаланиш мумкин.\n\n/start ни босинг",
        "admin_ask_approve": "✅ ID орқали тасдиқлаш",
        "admin_ask_reject": "❌ ID орқали рад этиш",
        "admin_enter_id": "✏️ Фойдаланувчи ID сини юборинг (фақат рақамлар)\n\nЁки «🔙 Бекор қилиш»ни босинг",
        "admin_cancel": "🔙 Бекор қилиш",
        "error_generic": "❌ Хатолик. Кейинроқ уриниб кўринг.",
        "error_invalid_id": "Нотўғри ID",
        "error_no_users": "Фойдаланувчилар йўқ",
        "error_usage_approve": "Ишлатиш: /approve <user_id>",
        "error_usage_reject": "Ишлатиш: /reject <user_id>",
    },
    "en": {
        "welcome": "👋 Welcome to FreeAI Bot!\n\n🤖 This bot can:\n• Give access to AI services\n• Referral program with earnings\n\n🔥 Press «ℹ️ Help» to learn how to use the bot!",
        "help": "ℹ️ How to use the bot:\n\n1️⃣ 💰 Pay for access or refer a friend\n2️⃣ 📧 Send your Gmail address (e.g. freeai@gmail.com)\n3️⃣ ⏳ Bot generates all dot combinations\n4️⃣ ◀️ ▶️ Browse with Prev/Next buttons\n5️⃣ 📎 File with all variants arrives automatically\n\n🔑 Password is the same as the original for all variants\n\n👥 Referrals: share your link — earn 10% from each payment",
        "lang_changed": "✅ Language: English",
        "menu_language": "🌐 Language",
        "menu_help": "ℹ️ Help",
        "menu_dots": "📧 Generate email",
        "menu_how": "ℹ️ How it works",
        "menu_services": "🔗 Services",
        "how_text": "📘 How the bot works:\n\n1️⃣ Gmail ignores dots in the name.\n   <code>n.ame@gmail.com</code> = <code>name@gmail.com</code>\n\n2️⃣ You can insert dots between letters.\n\n3️⃣ You can add +text after the name.\n   <code>name+shop@gmail.com</code>\n\n🎯 Why is this useful?\n• Email sorting\n• Tracking registration sources\n• Testing forms\n• Creating Gmail filters\n\n⚠ All emails go to the same inbox.",
        "services_text": "🔗 Useful Services\n\n💬 AI chats:\n• Gemini — gemini.google.com\n• ChatGPT — chatgpt.com\n• Claude — claude.ai\n• DeepSeek — chat.deepseek.com\n\n🎨 AI for photo & video:\n• Google Flow (Nano Banana, Veo 3.1) — labs.google/fx/ru/tools/flow\n   🎬 Video up to 8 sec on Veo 3.1\n• Hailuo AI — hailuoai.video\n• Seedance — seedance2.ai\n\n📊 AI for presentations:\n• Gamma — gamma.app\n\n📎 Send me an email and get dot combinations!",
        "get_email_text": "📧 Send me a Gmail address (e.g. <code>freeai@gmail.com</code>), and I'll generate ALL possible dot placements!\n\nThey all deliver to the same inbox ✅",
        "dots_title": "📧 Gmail Dot Generator\n\nSend me an email — I'll generate ALL possible dot combinations!\n\nExample: <code>freeai@gmail.com</code>",
        "dots_wait": "⏳ Generating combinations...",
        "dots_result": "✅ Done! {total} combinations",
        "dots_item": "{n} of {total}\n\n<code>{email}</code>\n\n🔑 Password is the same as the original",
        "dots_empty": "❌ Enter an email.\n\nExample: <code>freeai@gmail.com</code>",
        "dots_invalid": "❌ Invalid format. Expected: <code>local@domain.com</code>",
        "dots_long": "❌ Too long ({n} chars). {total} combinations.",
        "dots_info": "ℹ️ Gmail ignores dots. All variants deliver to the same inbox!",
        "dots_total": "📊 For {email}: {total} combinations",
        "dots_file": "📎 All {total} combinations for {email}",
        "dots_warn": "⚠️ {total} combinations — that's a lot. Wait.",
        "btn_prev": "◀️ Prev",
        "btn_next": "Next ▶️",
        "access_denied": "❌ No access yet\n\nPress «🔓 Get access» in the menu",
        "access_button": "🔓 Get access",
        "pay_title": "💎 Choose payment method:",
        "pay_stars": "⭐ 2000 Stars",
        "pay_crypto": "💰 $15 (CryptoBot)",
        "pay_crypto_creating": "⏳ Creating invoice...",
        "pay_crypto_ready": "💰 $15 USDT invoice:\n{url}\n\nAfter payment click «✅ I paid» — admin will confirm",
        "pay_crypto_direct": "💰 Pay $15 USDT to @costgold and he will grant access\n\nOr use ⭐ Stars above",
        "pay_i_paid": "✅ I paid",
        "pay_notify_done": "✅ Notification sent to admin! Wait for confirmation.",
        "pay_success": "✅ Payment received! Access granted.",
        "pay_stars_label": "Access to bot",
        "pay_stars_title": "FreeAI Bot — access",
        "pay_stars_desc": "Access to Gmail dot combinations generator",
        "pay_stars_link": "💎 Pay via link:\n{url}",
        "service_welcome": "🚀 Welcome to FreeAI Bot!\n\nThis bot gives you unlimited access to the best AI services:\n\n🧠 <b>Gemini Omni</b> — Google's most powerful multimodal model\n🎨 <b>Nano Banana</b> — image generation and editing\n🎬 <b>Veo 3.1</b> — create videos up to 8 seconds\n💬 <b>ChatGPT / Claude / DeepSeek</b> — leading AI chats\n📊 <b>Gamma</b> — AI for presentations\n\n🔑 After payment or admin approval — full access to Gmail dot combinations and all services!",
        "admin_users_title": "👥 Users ({total}):\n",
        "admin_user_line": "{id} — {status}\n",
        "admin_approved": "✅ User {id} approved",
        "admin_rejected": "❌ User {id} rejected",
        "admin_no_access": "❌ No access",
        "admin_btn_users": "👥 Users",
        "admin_btn_approve": "✅ Approve",
        "admin_btn_reject": "❌ Reject",
        "admin_user_approved": "✅ Admin approved your access to FreeAI Bot!",
        "admin_access_granted": "✅ Access granted! You can now use FreeAI Bot.\n\nPress /start to begin",
        "admin_ask_approve": "✅ Approve by ID",
        "admin_ask_reject": "❌ Reject by ID",
        "admin_enter_id": "✏️ Send user ID (numbers only)\n\nOr press «🔙 Cancel»",
        "admin_cancel": "🔙 Cancel",
        "menu_reviews": "⭐ Reviews",
        "reviews_text": "⭐ Bot reviews\n\nUser reviews will appear here soon!",
        "menu_ref": "👥 Referrals",
        "menu_profile": "👤 Profile",
        "profile_title": "👤 Profile\n🆔 ID: {user_id}\n📌 Status: {status}\n\n💰 Balance: ${balance:.2f}\n👥 Paid referrals: {count}\n\n🔥 Earn 10% from each friend's payment!\n\nYour referral link:\n<code>{link}</code>",
        "ref_title": "👥 Referral program\n\nYour link:\n<code>{link}</code>\n\nPaid referrals: {count}\n💰 Earned: ${earnings:.2f}\n\n🔥 Share your link — earn 10% from each payment!",
        "error_generic": "❌ Error. Try again later.",
        "error_invalid_id": "Invalid ID",
        "error_no_users": "No users",
        "error_usage_approve": "Usage: /approve <user_id>",
        "error_usage_reject": "Usage: /reject <user_id>",
    },
}

user_languages: dict[int, str] = {}
pending_admin_action: dict[int, str] = {}  # admin_id -> "approve" or "reject"

def t(uid: int, key: str, **kwargs) -> str:
    lang = user_languages.get(uid, "ru")
    text = TRANSLATIONS.get(lang, TRANSLATIONS["ru"]).get(key, key)
    return text.format(**kwargs) if kwargs else text

# =============================================================
# ПРОВЕРКА ДОСТУПА
# =============================================================

STAR_PRICE = 2000

def check_access(user_id: int) -> bool:
    if user_id == ADMIN_ID:
        return True
    return user_statuses.get(user_id) in ("approved", "paid")

# =============================================================
# НАСТРОЙКИ
# =============================================================
TOKEN = os.getenv("DOTS_BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
CRYPTOBOT_TOKEN = os.getenv("CRYPTOBOT_TOKEN", "")
MAX_LOCAL_LENGTH = 30
MAX_COMBINATIONS_WARNING = 50000

# =============================================================
# ДАННЫЕ
# =============================================================
DATA_FILE = "freeai_bot_data.json"
user_statuses: dict[int, str] = {}
referrer: dict[int, int] = {}  # user_id -> who referred them
referral_earnings: dict[int, float] = {}  # user_id -> total earned $

stats_data = {
    "dots_count": 0,
    "total_users": set(),
    "last_date": "",
    "start_time": datetime.now(timezone.utc).isoformat(),
}

def load_data():
    global user_statuses, referrer, referral_earnings, user_languages
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            stats_data["dots_count"] = data.get("dots_count", 0)
            stats_data["total_users"] = set(data.get("total_users", []))
            stats_data["last_date"] = data.get("last_date", "")
            user_statuses_raw = data.get("user_statuses", {})
            user_statuses = {int(k): v for k, v in user_statuses_raw.items()}
            referrer_raw = data.get("referrer", {})
            referrer = {int(k): v for k, v in referrer_raw.items()}
            earnings_raw = data.get("referral_earnings", {})
            referral_earnings = {int(k): v for k, v in earnings_raw.items()}
            languages_raw = data.get("user_languages", {})
            user_languages = {int(k): v for k, v in languages_raw.items()}
    except (FileNotFoundError, json.JSONDecodeError):
        pass

def save_data():
    data = {
        "dots_count": stats_data["dots_count"],
        "total_users": list(stats_data["total_users"]),
        "last_date": stats_data["last_date"],
        "user_statuses": {str(k): v for k, v in user_statuses.items()},
        "referrer": {str(k): v for k, v in referrer.items()},
        "referral_earnings": {str(k): v for k, v in referral_earnings.items()},
        "user_languages": {str(k): v for k, v in user_languages.items()},
    }
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

load_data()

# =============================================================
# ХРАНИЛИЩЕ КОМБИНАЦИЙ (для навигации)
# =============================================================
user_pages: dict[int, dict] = {}
WELCOME_PHOTO_PATH = os.path.join(os.path.dirname(__file__), "welcome_photo.jpg")

# =============================================================
# CRYPTO BOT INVOICE
# =============================================================

async def create_crypto_invoice() -> str | None:
    if not CRYPTOBOT_TOKEN:
        return None
    url = "https://pay.crypt.bot/api/createInvoice"
    headers = {"Crypto-Pay-API-Token": CRYPTOBOT_TOKEN}
    payload = {
        "asset": "USDT",
        "amount": "15",
        "description": "FreeAI Bot — доступ",
        "paid_btn_name": "openBot",
        "paid_btn_url": "https://t.me/freeai_dots_bot",
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                data = await resp.json()
                if data.get("ok"):
                    return data["result"]["pay_url"]
    except Exception as e:
        logger.error(f"CryptoBot error: {e}")
    return None

# =============================================================
# ЛОГИРОВАНИЕ
# =============================================================
logging.basicConfig(
    level=logging.INFO,
    format='✦ %(asctime)s ✦ %(name)s ✦ %(levelname)s ✦ %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logging.getLogger("aiogram").setLevel(logging.WARNING)
logging.getLogger("aiogram.event").setLevel(logging.WARNING)
logger = logging.getLogger("FreeAI-Bot")

# =============================================================
# ИНИЦИАЛИЗАЦИЯ
# =============================================================
bot = Bot(token=TOKEN)
dp = Dispatcher()
router = Router()

# ---------- Глобальный перехват ошибок ----------
import traceback as _tb
@dp.error()
async def on_error(event):
    exc = getattr(event, "exception", event)
    uid = getattr(getattr(event, "update", None), "from_user", None)
    uid = uid.id if uid else "?"
    logger.error(f"Handler error for user {uid}: {exc}\n{_tb.format_exc()}")
    print(f"HANDLER ERROR [{uid}]: {exc}", flush=True)
    _tb.print_exc()

# =============================================================
# ГЕНЕРАТОР КОМБИНАЦИЙ ТОЧЕК
# =============================================================

def generate_dot_combinations(email: str) -> list[str]:
    email = email.strip().lower()
    if '@' not in email:
        return []
    local, domain = email.split('@', 1)
    n = len(local)
    if n <= 1:
        return [email]
    results = []
    total = 1 << (n - 1)
    for mask in range(total):
        chars = []
        for i in range(n - 1):
            chars.append(local[i])
            if mask & (1 << i):
                chars.append('.')
        chars.append(local[-1])
        results.append(''.join(chars) + '@' + domain)
    return results



# =============================================================
# КЛАВИАТУРЫ
# =============================================================

def get_language_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru")],
        [InlineKeyboardButton(text="🇺🇿 O'zbek", callback_data="lang_uz")],
        [InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en")],
    ])

def get_main_keyboard(user_id: int):
    lang = user_languages.get(user_id, "ru")
    labels = TRANSLATIONS.get(lang, TRANSLATIONS["ru"])

    if check_access(user_id):
        rows = [
            [InlineKeyboardButton(text=labels.get("menu_how", "ℹ️ How it works"), callback_data="action_how"),
             InlineKeyboardButton(text=labels.get("menu_services", "🔗 Services"), callback_data="action_services")],
            [InlineKeyboardButton(text=labels.get("menu_ref", "👥 Рефералы"), callback_data="action_ref"),
             InlineKeyboardButton(text=labels.get("menu_profile", "👤 Профиль"), callback_data="action_profile")],
            [InlineKeyboardButton(text=labels.get("menu_dots", "📧 Generate email"), callback_data="action_dots")],
        ]
        if user_id == ADMIN_ID:
            rows.append([InlineKeyboardButton(text=labels.get("admin_btn_users", "👥 Users"), callback_data="action_admin_users")])
        rows.append([
            InlineKeyboardButton(text=labels.get("menu_language", "🌐 Language"), callback_data="action_language"),
            InlineKeyboardButton(text=labels.get("menu_help", "ℹ️ Help"), callback_data="action_help"),
        ])
    else:
        rows = [
            [InlineKeyboardButton(text=labels.get("menu_ref", "👥 Рефералы"), callback_data="action_ref"),
             InlineKeyboardButton(text=labels.get("menu_profile", "👤 Профиль"), callback_data="action_profile")],
            [InlineKeyboardButton(text=labels.get("access_button", "🔓 Получить доступ"), callback_data="action_access")],
            [InlineKeyboardButton(text=labels.get("menu_reviews", "⭐ Отзывы"), callback_data="action_reviews"),
             InlineKeyboardButton(text=labels.get("menu_help", "ℹ️ Помощь"), callback_data="action_help")],
            [InlineKeyboardButton(text=labels.get("menu_language", "🌐 Language"), callback_data="action_language")],
        ]
    return InlineKeyboardMarkup(inline_keyboard=rows)

def get_back_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="action_main_menu")]
    ])

# =============================================================
# КОМАНДЫ
# =============================================================

@router.message(CommandStart())
async def cmd_start(message: Message):
    user_id = message.from_user.id
    stats_data["total_users"].add(user_id)

    args = (message.text or "").split()
    if len(args) > 1:
        payload = args[1]
        if payload.startswith("ref_"):
            try:
                ref_id = int(payload.split("_")[1])
                if ref_id != user_id and ref_id not in referrer:
                    referrer[user_id] = ref_id
            except:
                pass

    save_data()

    if user_id not in user_languages:
        await message.answer(
            "👋 Выбери язык / Tilni tanlang / Choose language:",
            reply_markup=get_language_keyboard()
        )
    else:
        if user_id not in user_statuses:
            user_statuses[user_id] = "pending"
            save_data()
        await show_main_menu(message)

def get_nav_keyboard(user_id: int, index: int, total: int) -> InlineKeyboardMarkup:
    buttons = []
    if index > 0:
        buttons.append(InlineKeyboardButton(text=t(user_id, "btn_prev"), callback_data="nav_prev"))
    if index < total - 1:
        buttons.append(InlineKeyboardButton(text=t(user_id, "btn_next"), callback_data="nav_next"))
    return InlineKeyboardMarkup(inline_keyboard=[buttons])

async def show_main_menu(message: Message, user_id: int = 0):
    if not user_id:
        user_id = message.from_user.id
    text = t(user_id, "welcome")
    await message.answer(text, reply_markup=get_main_keyboard(user_id), parse_mode="HTML")

@router.message(Command("help"))
async def cmd_help(message: Message):
    user_id = message.from_user.id
    await message.answer(t(user_id, "help"))

@router.message(Command("lang"))
async def cmd_lang(message: Message):
    await message.answer("🌐 Выбери язык / Tilni tanlang / Choose language:", reply_markup=get_language_keyboard())

# =============================================================
# АДМИН-КОМАНДЫ
# =============================================================

@router.message(Command("users"))
async def cmd_users(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    lines = []
    for uid, status in user_statuses.items():
        lines.append(t(message.from_user.id, "admin_user_line", id=uid, status=status))
    if not lines:
        lines.append(t(message.from_user.id, "error_no_users"))
    text = t(message.from_user.id, "admin_users_title", total=len(lines)) + "".join(lines)
    await message.answer(text)

@router.message(Command("approve"))
async def cmd_approve(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    parts = (message.text or "").split()
    if len(parts) < 2:
        await message.answer(t(message.from_user.id, "error_usage_approve"))
        return
    try:
        uid = int(parts[1])
    except ValueError:
        await message.answer(t(message.from_user.id, "error_invalid_id"))
        return
    user_statuses[uid] = "approved"
    save_data()
    await message.answer(t(message.from_user.id, "admin_approved", id=uid))
    try:
        await bot.send_message(uid, t(uid, "admin_access_granted"))
    except:
        pass

@router.message(Command("reject"))
async def cmd_reject(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    parts = (message.text or "").split()
    if len(parts) < 2:
        await message.answer(t(message.from_user.id, "error_usage_reject"))
        return
    try:
        uid = int(parts[1])
    except ValueError:
        await message.answer(t(message.from_user.id, "error_invalid_id"))
        return
    user_statuses.pop(uid, None)
    save_data()
    await message.answer(t(message.from_user.id, "admin_rejected", id=uid))

# =============================================================
# ОБРАБОТКА ТЕКСТА
# =============================================================

@router.message(F.text)
async def handle_text(message: Message):
    user_id = message.from_user.id
    text = (message.text or "").strip()

    if not text or text.startswith("/"):
        return

    # Admin ID input handling
    if user_id == ADMIN_ID and user_id in pending_admin_action:
        action = pending_admin_action.pop(user_id)
        try:
            target = int(text)
        except ValueError:
            await message.answer(t(user_id, "error_invalid_id"))
            return
        if action == "approve":
            user_statuses[target] = "approved"
            save_data()
            await message.answer(t(user_id, "admin_approved", id=target))
            try:
                await bot.send_message(target, t(target, "admin_user_approved"))
            except:
                pass
        elif action == "reject":
            user_statuses.pop(target, None)
            save_data()
            await message.answer(t(user_id, "admin_rejected", id=target))
        return

    if not check_access(user_id):
        await message.answer(t(user_id, "access_denied"))
        return

    if '@' not in text:
        return

    text = text.lower()
    local, domain = text.split('@', 1)
    if not local or not domain:
        return

    n = len(local)
    total = 1 << (n - 1)
    if n > MAX_LOCAL_LENGTH:
        await message.answer(t(user_id, "dots_long", n=n, total=total))
        return
    if total > MAX_COMBINATIONS_WARNING:
        await message.answer(t(user_id, "dots_warn", total=total))

    await message.answer(t(user_id, "dots_total", email=text, total=total))
    wait_msg = await message.answer(t(user_id, "dots_wait"))
    combinations = generate_dot_combinations(text)
    total_actual = len(combinations)

    stats_data["dots_count"] += 1
    stats_data["last_date"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    save_data()

    user_pages[user_id] = {
        "combos": combinations,
        "index": 0,
        "total": total_actual,
    }

    combo = combinations[0]
    text_item = t(user_id, "dots_item", n=1, total=total_actual, email=combo)
    await wait_msg.edit_text(text_item, reply_markup=get_nav_keyboard(user_id, 0, total_actual), parse_mode="HTML")

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', encoding='utf-8', delete=False) as tmp:
            tmp_path = tmp.name
            tmp.write(f"# Dots combinations for: {text}\n")
            tmp.write(f"# Total: {total_actual}\n")
            tmp.write("#" + "=" * 50 + "\n")
            for c in combinations:
                tmp.write(c + '\n')
        file = FSInputFile(tmp_path)
        await message.answer_document(file, caption=t(user_id, "dots_file", total=total_actual, email=text))
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
    user_id = callback.from_user.id
    text = t(user_id, "welcome")
    try:
        await callback.message.edit_text(text, reply_markup=get_main_keyboard(user_id), parse_mode="HTML")
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=get_main_keyboard(user_id), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "action_how")
async def cb_how(callback: CallbackQuery):
    user_id = callback.from_user.id
    try:
        await callback.message.edit_text(t(user_id, "how_text"), reply_markup=get_back_keyboard(), parse_mode="HTML")
    except TelegramBadRequest:
        await callback.message.answer(t(user_id, "how_text"), reply_markup=get_back_keyboard(), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "action_services")
async def cb_services(callback: CallbackQuery):
    user_id = callback.from_user.id
    try:
        await callback.message.edit_text(t(user_id, "services_text"), reply_markup=get_back_keyboard())
    except TelegramBadRequest:
        await callback.message.answer(t(user_id, "services_text"), reply_markup=get_back_keyboard())
    await callback.answer()

@router.callback_query(F.data == "action_dots")
async def cb_dots(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not check_access(user_id):
        await callback.answer(t(user_id, "admin_no_access"), show_alert=True)
        return
    try:
        await callback.message.edit_text(t(user_id, "dots_title"), reply_markup=get_back_keyboard(), parse_mode="HTML")
    except TelegramBadRequest:
        await callback.message.answer(t(user_id, "dots_title"), reply_markup=get_back_keyboard(), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "action_access")
async def cb_access(callback: CallbackQuery):
    user_id = callback.from_user.id
    lang = user_languages.get(user_id, "ru")
    labels = TRANSLATIONS.get(lang, TRANSLATIONS["ru"])
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=labels.get("pay_stars", "⭐ 2000 Stars"), callback_data="pay_stars")],
        [InlineKeyboardButton(text=labels.get("pay_crypto", "💰 $15 CryptoBot"), callback_data="pay_crypto")],
        [InlineKeyboardButton(text="📨 Администратор", url="https://t.me/costgold"),
         InlineKeyboardButton(text="🔙 Назад", callback_data="action_main_menu")],
    ])
    try:
        await callback.message.edit_text(t(user_id, "pay_title"), reply_markup=keyboard)
    except TelegramBadRequest:
        await callback.message.answer(t(user_id, "pay_title"), reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "pay_stars")
async def cb_pay_stars(callback: CallbackQuery):
    user_id = callback.from_user.id
    lang = user_languages.get(user_id, "ru")
    labels = TRANSLATIONS.get(lang, TRANSLATIONS["ru"])
    prices = [LabeledPrice(label=labels.get("pay_stars_label", "Доступ к боту"), amount=STAR_PRICE)]
    invoice = await bot.create_invoice_link(
        title=labels.get("pay_stars_title", "FreeAI Bot — доступ"),
        description=labels.get("pay_stars_desc", "Доступ к генератору комбинаций точек для Gmail"),
        payload=str(uuid4()),
        provider_token="",
        currency="XTR",
        prices=prices,
    )
    await callback.message.answer(t(user_id, "pay_stars_link", url=invoice))
    await callback.answer()

@router.callback_query(F.data == "pay_crypto")
async def cb_pay_crypto(callback: CallbackQuery):
    user_id = callback.from_user.id
    await callback.message.answer(t(user_id, "pay_crypto_creating"))
    pay_url = await create_crypto_invoice()
    lang = user_languages.get(user_id, "ru")
    labels = TRANSLATIONS.get(lang, TRANSLATIONS["ru"])
    notify_btn = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=labels.get("pay_i_paid", "✅ Я оплатил"),
                              callback_data="pay_notify_admin")],
    ])
    if pay_url:
        await callback.message.answer(
            t(user_id, "pay_crypto_ready", url=pay_url),
            reply_markup=notify_btn
        )
    else:
        await callback.message.answer(
            t(user_id, "pay_crypto_direct"),
            reply_markup=notify_btn
        )
    await callback.answer()

@router.callback_query(F.data == "pay_notify_admin")
async def cb_pay_notify_admin(callback: CallbackQuery):
    user_id = callback.from_user.id
    username = callback.from_user.username or "—"
    mention = f"<a href='tg://user?id={user_id}'>{user_id}</a>"
    await bot.send_message(ADMIN_ID, 
        f"💰 Пользователь {mention} (@{username}) сообщает, что оплатил!\n"
        f"Команда: /approve {user_id}",
        parse_mode="HTML"
    )
    await callback.answer(t(user_id, "pay_notify_done"), show_alert=True)

@router.pre_checkout_query()
async def pre_checkout(pre_checkout_q: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_q.id, ok=True)

@router.message(F.successful_payment)
async def on_successful_payment(message: Message):
    user_id = message.from_user.id
    user_statuses[user_id] = "paid"
    if user_id in referrer:
        ref_id = referrer[user_id]
        commission = 2.0  # 10% of $20 = $2 (stars value) or $1.5 of $15
        referral_earnings[ref_id] = referral_earnings.get(ref_id, 0) + commission
        try:
            await bot.send_message(
                ref_id,
                f"🎉 По вашей реферальной ссылке оплатили подписку!\n"
                f"💰 Начислено ${commission:.2f}"
            )
        except:
            pass
    save_data()
    await message.answer(t(user_id, "pay_success"), reply_markup=get_main_keyboard(user_id))

@router.callback_query(F.data == "action_help")
async def cb_help(callback: CallbackQuery):
    user_id = callback.from_user.id
    try:
        await callback.message.edit_text(t(user_id, "help"), reply_markup=get_back_keyboard())
    except TelegramBadRequest:
        await callback.message.answer(t(user_id, "help"), reply_markup=get_back_keyboard())
    await callback.answer()

@router.callback_query(F.data == "action_language")
async def cb_language(callback: CallbackQuery):
    await callback.message.edit_text("🌐 Выбери язык / Tilni tanlang / Choose language:", reply_markup=get_language_keyboard())
    await callback.answer()

@router.callback_query(F.data.startswith("lang_"))
async def cb_lang_selected(callback: CallbackQuery):
    lang = callback.data.replace("lang_", "")
    user_languages[callback.from_user.id] = lang
    await callback.answer(f"✅ {t(callback.from_user.id, 'lang_changed')}", show_alert=True)

    user_id = callback.from_user.id

    if user_id not in user_statuses:
        user_statuses[user_id] = "pending"
        save_data()
    if user_id == ADMIN_ID:
        user_statuses[user_id] = "approved"
        save_data()

    if os.path.exists(WELCOME_PHOTO_PATH):
        from aiogram.types import FSInputFile as FSIF
        try:
            await callback.message.answer_photo(
                photo=FSIF(WELCOME_PHOTO_PATH),
                caption=t(user_id, "service_welcome"),
                parse_mode="HTML"
            )
        except:
            await callback.message.answer(t(user_id, "service_welcome"), parse_mode="HTML")
    else:
        await callback.message.answer(t(user_id, "service_welcome"), parse_mode="HTML")
    try:
        await callback.message.delete()
    except:
        pass
    await show_main_menu(callback.message, user_id=user_id)

@router.callback_query(F.data == "action_admin_users")
async def cb_admin_users(callback: CallbackQuery):
    user_id = callback.from_user.id
    if user_id != ADMIN_ID:
        await callback.answer()
        return
    total = paid = approved = pending = 0
    for uid, status in user_statuses.items():
        if uid == ADMIN_ID:
            continue
        total += 1
        if status == "paid":
            paid += 1
        elif status == "approved":
            approved += 1
        else:
            pending += 1
    stats = (
        f"📊 Статистика:\n"
        f"💰 Оплатили: {paid}\n"
        f"✅ Одобрены: {approved}\n"
        f"⏳ В ожидании: {pending}\n"
        f"👥 Всего: {total}\n\n"
    )
    lines = []
    for uid, status in user_statuses.items():
        if uid == ADMIN_ID:
            continue
        btn_approve = InlineKeyboardButton(text=t(user_id, "admin_btn_approve"), callback_data=f"admin_appr_{uid}")
        btn_reject = InlineKeyboardButton(text=t(user_id, "admin_btn_reject"), callback_data=f"admin_rej_{uid}")
        text = t(user_id, "admin_user_line", id=uid, status=status)
        lines.append([InlineKeyboardButton(text=text.strip(), callback_data="noop")])
        lines.append([btn_approve, btn_reject])
    if not lines:
        lines.append([InlineKeyboardButton(text=t(user_id, "error_no_users"), callback_data="noop")])
    lines.append([
        InlineKeyboardButton(text=t(user_id, "admin_ask_approve"), callback_data="admin_ask_approve"),
        InlineKeyboardButton(text=t(user_id, "admin_ask_reject"), callback_data="admin_ask_reject"),
    ])
    lines.append([InlineKeyboardButton(text="🔙 Назад", callback_data="action_main_menu")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=lines)
    try:
        await callback.message.edit_text(stats + t(user_id, "admin_users_title", total=total), reply_markup=keyboard)
    except TelegramBadRequest:
        await callback.message.answer(stats + t(user_id, "admin_users_title", total=total), reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("admin_appr_"))
async def cb_admin_approve(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer()
        return
    uid = int(callback.data.split("_")[-1])
    user_statuses[uid] = "approved"
    save_data()
    await callback.answer(t(callback.from_user.id, "admin_approved", id=uid), show_alert=True)
    try:
        await bot.send_message(uid, t(uid, "admin_user_approved"))
    except:
        pass
    await cb_admin_users(callback)

@router.callback_query(F.data.startswith("admin_rej_"))
async def cb_admin_reject(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer()
        return
    uid = int(callback.data.split("_")[-1])
    user_statuses.pop(uid, None)
    save_data()
    await callback.answer(t(callback.from_user.id, "admin_rejected", id=uid), show_alert=True)
    await cb_admin_users(callback)

@router.callback_query(F.data == "admin_ask_approve")
async def cb_admin_ask_approve(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer()
        return
    pending_admin_action[ADMIN_ID] = "approve"
    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(ADMIN_ID, "admin_cancel"), callback_data="admin_cancel_input")]
    ])
    await callback.message.answer(t(ADMIN_ID, "admin_enter_id"), reply_markup=cancel_kb)
    await callback.answer()

@router.callback_query(F.data == "admin_ask_reject")
async def cb_admin_ask_reject(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer()
        return
    pending_admin_action[ADMIN_ID] = "reject"
    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(ADMIN_ID, "admin_cancel"), callback_data="admin_cancel_input")]
    ])
    await callback.message.answer(t(ADMIN_ID, "admin_enter_id"), reply_markup=cancel_kb)
    await callback.answer()

@router.callback_query(F.data == "admin_cancel_input")
async def cb_admin_cancel_input(callback: CallbackQuery):
    pending_admin_action.pop(ADMIN_ID, None)
    await callback.message.edit_text("❌ Отменено")
    await callback.answer()
    await cb_admin_users(callback)

@router.callback_query(F.data == "action_reviews")
async def cb_reviews(callback: CallbackQuery):
    user_id = callback.from_user.id
    try:
        await callback.message.edit_text(t(user_id, "reviews_text"), reply_markup=get_back_keyboard())
    except TelegramBadRequest:
        await callback.message.answer(t(user_id, "reviews_text"), reply_markup=get_back_keyboard())
    await callback.answer()

@router.callback_query(F.data == "action_profile")
async def cb_profile(callback: CallbackQuery):
    user_id = callback.from_user.id
    try:
        bot_username = (await bot.get_me()).username
        link = f"https://t.me/{bot_username}?start=ref_{user_id}"
        count = sum(1 for uid, ref in referrer.items() if ref == user_id and user_statuses.get(uid) == "paid")
        balance = referral_earnings.get(user_id, 0.0)
        s = user_statuses.get(user_id, None)
        lang = user_languages.get(user_id, "ru")
        labels = {"ru": {"paid": "✅ Оплачен", "approved": "✅ Одобрен", "pending": "⏳ Ожидание"},
                  "uz": {"paid": "✅ Тўланган", "approved": "✅ Тасдиқланган", "pending": "⏳ Кутилмоқда"},
                  "en": {"paid": "✅ Paid", "approved": "✅ Approved", "pending": "⏳ Pending"}}
        status = labels.get(lang, labels["ru"]).get(s or "pending", labels["ru"]["pending"])
        text = t(user_id, "profile_title", user_id=user_id, status=status, link=link, count=count, balance=balance)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📤 Улашиш / Share", url=f"https://t.me/share/url?url={link}")],
            [InlineKeyboardButton(text="🔙 Асосий меню", callback_data="action_main_menu")],
        ])
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Profile error for {user_id}: {e}", exc_info=True)
        try:
            await callback.message.answer(t(user_id, "error_generic"))
        except Exception:
            pass
    await callback.answer()

@router.callback_query(F.data == "action_ref")
async def cb_ref(callback: CallbackQuery):
    user_id = callback.from_user.id
    bot_username = (await bot.get_me()).username
    link = f"https://t.me/{bot_username}?start=ref_{user_id}"
    count = sum(1 for uid, ref in referrer.items() if ref == user_id and user_statuses.get(uid) == "paid")
    earnings = referral_earnings.get(user_id, 0)
    text = t(user_id, "ref_title", link=link, count=count, earnings=earnings)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Поделиться", url=f"https://t.me/share/url?url={link}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="action_main_menu")],
    ])
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "noop")
async def cb_noop(callback: CallbackQuery):
    await callback.answer()

@router.callback_query(F.data == "nav_prev")
async def cb_nav_prev(callback: CallbackQuery):
    user_id = callback.from_user.id
    page = user_pages.get(user_id)
    if not page:
        await callback.answer()
        return
    idx = page["index"] - 1
    if idx < 0:
        await callback.answer()
        return
    page["index"] = idx
    combo = page["combos"][idx]
    text_item = t(user_id, "dots_item", n=idx+1, total=page["total"], email=combo)
    await callback.message.edit_text(text_item, reply_markup=get_nav_keyboard(user_id, idx, page["total"]), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "nav_next")
async def cb_nav_next(callback: CallbackQuery):
    user_id = callback.from_user.id
    page = user_pages.get(user_id)
    if not page:
        await callback.answer()
        return
    idx = page["index"] + 1
    if idx >= page["total"]:
        await callback.answer()
        return
    page["index"] = idx
    combo = page["combos"][idx]
    text_item = t(user_id, "dots_item", n=idx+1, total=page["total"], email=combo)
    await callback.message.edit_text(text_item, reply_markup=get_nav_keyboard(user_id, idx, page["total"]), parse_mode="HTML")
    await callback.answer()

# =============================================================
# ЗАПУСК
# =============================================================

async def main():
    if not TOKEN:
        print("❌ Не задан TELEGRAM_TOKEN или DOTS_BOT_TOKEN в .env")
        sys.exit(1)

    dp.include_router(router)

    from aiogram.types import BotCommand
    await bot.set_my_commands([
        BotCommand(command="start", description="Главное меню"),
        BotCommand(command="help", description="Помощь"),
        BotCommand(command="lang", description="Язык"),
    ])

    await bot.delete_webhook(drop_pending_updates=True)
    # Отправляем тестовое сообщение админу
    try:
        await bot.send_message(ADMIN_ID, "🤖 Бот запущен на Render!")
    except Exception as e:
        print(f"FAILED to send startup message: {e}", flush=True)
    logger.info("=" * 50)
    logger.info(" FreeAI Bot запущен!")
    logger.info("=" * 50)
    await dp.start_polling(bot, skip_updates=False)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nБот остановлен")
    finally:
        asyncio.run(bot.session.close())
