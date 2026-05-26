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

# ---------- Буфер логов (последние 200 строк) ----------
log_buffer = []
import io

class LogBuffer(io.StringIO):
    def write(self, s):
        log_buffer.append(s)
        if len(log_buffer) > 200:
            log_buffer[:50] = []
        super().write(s)

sys.stderr = LogBuffer()
sys.stdout = LogBuffer()

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

    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

# ---------- Точка входа ----------
if __name__ == "__main__":
    threading.Thread(target=run_http, daemon=True).start()

    try:
        asyncio.run(bot_main())
    except Exception as e:
        tb = traceback.format_exc()
        print(f"BOT CRASHED: {e}\n{tb}", flush=True)
        # Держим процесс живым, чтобы Flask продолжал отвечать
        import time
        while True:
            time.sleep(10)
