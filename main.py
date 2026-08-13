import os
import threading
import asyncio
from flask import Flask
from aiogram import Bot, Dispatcher

# ==================== 1. Flask 网页服务（防掉线欺骗层） ====================
app = Flask(__name__)

@app.route('/')
def home():
    return "Agnes Bot is running smoothly!"

def run_web_server():
    # 获取 Render 动态分配的端口，默认 10000
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# 在后台线程中启动网页服务，与 Telegram 机器人互不干扰
threading.Thread(target=run_web_server, daemon=True).start()


# ==================== 2. Telegram 机器人核心逻辑 ====================
# 读取环境变量中的 Token
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("未检测到 BOT_TOKEN 环境变量，请在 Render 后台的 Secrets 中配置！")

# 初始化 Bot 和 Dispatcher
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# 导入你写在 bot_logic.py 里的业务逻辑和搜索处理函数
from bot_logic import register_handlers
register_handlers(dp)  # 注册你的所有消息处理和搜索路由


async def main():
    print("Bot 正在启动并准备接收消息...")
    # 启动长轮询，联网搜索功能将由 bot_logic.py 中的 ddgs 正常提供
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
