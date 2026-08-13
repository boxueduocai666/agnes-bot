import os
import threading
from flask import Flask

# 1. 创建一个极简的 Web 服务
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_web_server():
    # 获取 Render 分配的端口，如果没有则默认 10000
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# 2. 在程序启动时，通过多线程在后台运行这个 Web 服务
# 这行代码一定要放在你启动 Bot 的 main 函数之前
threading.Thread(target=run_web_server, daemon=True).start()
