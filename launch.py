import os, subprocess, sys, time

env = os.environ.copy()
env["DOTS_BOT_TOKEN"] = "8292291322:AAEhtxcroZ9MX-J_OQJ3vW-kEzvdOo6ivRA"
env["ADMIN_ID"] = "1066757511"

with open(os.path.expanduser("~/Desktop/bot_out.txt"), "w") as out, \
     open(os.path.expanduser("~/Desktop/bot_err.txt"), "w") as err:
    proc = subprocess.Popen(
        [sys.executable, os.path.expanduser("~/Desktop/freeai-bot-last/freeai_bot.py")],
        env=env, stdout=out, stderr=err
    )
    with open(os.path.expanduser("~/Desktop/bot_pid.txt"), "w") as f:
        f.write(str(proc.pid))
    print(f"PID: {proc.pid}", flush=True)
