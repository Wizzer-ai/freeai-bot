import sys
import os
import winreg

SCRIPT_PATH = os.path.abspath("bot.py")
BATCH_PATH = os.path.abspath("start.bat")

try:
    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_WRITE)
    winreg.SetValueEx(key, "AIBot", 0, winreg.REG_SZ, f'"{BATCH_PATH}"')
    winreg.CloseKey(key)
    print("✅ Бот добавлен в автозагрузку Windows")
except Exception as e:
    print(f"❌ Ошибка: {e}")