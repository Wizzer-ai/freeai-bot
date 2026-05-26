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

# Simple log buffer
log_buffer = []
def log_write(s):
    log_buffer.append(s)
    if len(log_buffer) > 200:
        del log_buffer[:50]

@app.route("/")
def root():
    return "FreeAI Bot is running", 200

@app.route("/health")
def health():
    return "OK", 200

@app.route("/logs")
def logs():
    return "<pre>" + "".join(log_buffer[-100:]) + "</pre>", 200

@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    import traceback as _tb
    try:
        data = request.json
        update = Update(**data)
        log_write(f"Got update: {update.update_id}")
        if update.message:
            log_write(f"Message: {update.message.text[:50] if update.message.text else 'None'} from {update.message.from_user.id}")
        # Check state before
        from freeai_bot import user_statuses as us, user_languages as ul
        before_statuses = len(us)
        before_languages = len(ul)
        log_write(f"Before: statuses={before_statuses}, languages={before_languages}")
        asyncio.run(dp.feed_webhook_update(bot, update))
        # Check state after
        after_statuses = len(us)
        after_languages = len(ul)
        log_write(f"After: statuses={after_statuses}, languages={after_languages}")
        return "OK", 200
    except Exception as e:
        tb = _tb.format_exc()
        log_write(f"Webhook error: {e}\n{tb}")
        return f"ERROR: {tb}", 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))

    async def setup():
        dp.include_router(router)
        wh = await bot.get_webhook_info()
        if wh.url != WEBHOOK_URL:
            await bot.set_webhook(WEBHOOK_URL, drop_pending_updates=True)
            logger.info(f"Webhook set: {WEBHOOK_URL}")
        else:
            logger.info(f"Webhook OK: {WEBHOOK_URL}")

    asyncio.run(setup())
    logger.info("Starting Flask...")
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
