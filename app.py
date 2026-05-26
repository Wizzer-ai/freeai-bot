"""
FreeAI Bot — Render + aiogram webhook
=======================================
"""
import os
import asyncio
import logging
from flask import Flask, request

from aiogram.types import Update

from freeai_bot import bot, dp, router, TOKEN, ADMIN_ID, logger
import freeai_bot

app = Flask(__name__)
WEBHOOK_PATH = "/webhook"
BASE_URL = os.environ.get("RENDER_EXTERNAL_URL", "https://freeai-bot.onrender.com")
WEBHOOK_URL = BASE_URL + WEBHOOK_PATH

# Единый event loop для всего приложения
loop = asyncio.new_event_loop()

@app.route("/")
def root():
    return "FreeAI Bot is running", 200

@app.route("/health")
def health():
    return "OK", 200

@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    try:
        update = Update.model_validate(request.json, context={"bot": bot})
        loop.run_until_complete(dp.feed_update(bot, update))
        return "OK", 200
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return f"ERROR: {e}", 500

@app.route("/debug")
def debug():
    info = f"TOKEN set: {bool(TOKEN)}\n"
    info += f"ADMIN_ID: {ADMIN_ID}\n"
    info += f"user_statuses: {len(freeai_bot.user_statuses)}\n"
    info += f"user_languages: {dict(freeai_bot.user_languages)}\n"
    return f"<pre>{info}</pre>", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))

    # Настройка вебхука при старте
    dp.include_router(router)
    wh = loop.run_until_complete(bot.get_webhook_info())
    if wh.url != WEBHOOK_URL:
        loop.run_until_complete(bot.set_webhook(WEBHOOK_URL, drop_pending_updates=True))
        logger.info(f"Webhook set: {WEBHOOK_URL}")
    else:
        logger.info(f"Webhook OK: {WEBHOOK_URL}")

    logger.info("Starting Flask...")
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
