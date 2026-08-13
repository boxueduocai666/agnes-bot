import os
import threading
from flask import Flask
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
)

from bot_logic import (
    handle_message,
    handle_summary,
    handle_start,
)

# ============================================================
# 1. Flask Web Server
# ============================================================

app = Flask(__name__)


@app.route("/")
def home():
    return "Agnes Bot is running smoothly!"


@app.route("/health")
def health():
    return "OK"


def run_web_server():
    port = int(os.environ.get("PORT", 10000))

    app.run(
        host="0.0.0.0",
        port=port
    )


# ============================================================
# 2. Telegram Bot
# ============================================================

def main():
    token = os.environ.get("TELEGRAM_TOKEN")

    if not token:
        raise RuntimeError(
            "未检测到 TELEGRAM_TOKEN，请在 Render 的 Environment Variables 中配置。"
        )

    # --------------------------------------------------------
    # Render Web Service 需要 HTTP 服务
    # 所以在后台线程启动 Flask
    # --------------------------------------------------------

    web_thread = threading.Thread(
        target=run_web_server,
        daemon=True
    )

    web_thread.start()

    # --------------------------------------------------------
    # 创建 Telegram Application
    # 使用 python-telegram-bot
    # --------------------------------------------------------

    application = (
        Application.builder()
        .token(token)
        .build()
    )

    # --------------------------------------------------------
    # /start
    # --------------------------------------------------------

    application.add_handler(
        CommandHandler(
            "start",
            handle_start
        )
    )

    # --------------------------------------------------------
    # /summary
    # --------------------------------------------------------

    application.add_handler(
        CommandHandler(
            "summary",
            handle_summary
        )
    )

    # --------------------------------------------------------
    # 普通文字 + 图片
    # --------------------------------------------------------

    application.add_handler(
        MessageHandler(
            filters.TEXT | filters.PHOTO,
            handle_message
        )
    )

    print("========================================")
    print("Agnes Bot 正在启动...")
    print("Telegram Bot: OK")
    print("Flask Server: OK")
    print("========================================")

    # --------------------------------------------------------
    # 启动 Telegram 长轮询
    # --------------------------------------------------------

    application.run_polling()


# ============================================================
# 3. 程序入口
# ============================================================

if __name__ == "__main__":
    main()
