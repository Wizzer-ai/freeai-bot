"""
FreeAI Bot — Render-совместимый запуск
=======================================
Flask (порт $PORT) + aiogram polling в фоне.
"""
import os
import sys
import asyncio
import threading
import traceback
from flask import Flask

from freeai_bot import bot, dp, router, main as bot_main, TOKEN, logger
import freeai_bot

# ---------- Буфер логов (последние 200 строк) ----------
log_buffer = []
import io

def log_write(s):
    log_buffer.append(s)
    if len(log_buffer) > 200:
        log_buffer[:50] = []

# ---------- Flask (для Render — занимает порт) ----------
def run_http():
    app = Flask(__name__)

    @app.route("/")
    def root():
        return "FreeAI Bot is running", 200

    @app.route("/health")
    def health():
        return "OK", 200

    @app.route("/logs")
    def logs():
        return "<pre>" + "".join(log_buffer[-100:]) + "</pre>", 200

    @app.route("/debug")
    def debug():
        import os as _os
        import json as _json
        info = f"TOKEN set: {bool(TOKEN)}\n"
        info += f"ADMIN_ID: {_os.environ.get('ADMIN_ID', 'NOT SET')}\n"
        info += f"user_statuses: {len(freeai_bot.user_statuses)}\n"
        info += f"user_languages: {dict(freeai_bot.user_languages)}\n"
        info += f"data file exists: {_os.path.exists(freeai_bot.DATA_FILE)}\n"
        # Test Telegram API
        try:
            import urllib.request as _ur
            tg = f"https://api.telegram.org/bot{TOKEN}/getMe"
            resp = _json.loads(_ur.urlopen(tg, timeout=5).read())
            info += f"tg_getMe: {resp.get('result', {}).get('username', 'FAIL')}\n"
        except Exception as e:
            info += f"tg_error: {e}\n"
        return f"<pre>{info}</pre>", 200

    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

# ---------- Точка входа ----------
if __name__ == "__main__":
    threading.Thread(target=run_http, daemon=True).start()

    try:
        asyncio.run(bot_main())
    except Exception as e:
        tb = traceback.format_exc()
        msg = f"BOT CRASHED: {e}\n{tb}"
        log_write(msg)
        print(msg, flush=True)
        import time
        while True:
            time.sleep(10)
