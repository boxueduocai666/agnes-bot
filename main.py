import os
import threading

from flask import Flask

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters
)

from bot_logic import (
    handle_message,
    handle_summary
)


# ============================================================
# Flask Web 服务
# ============================================================

app = Flask(__name__)


@app.route("/")
def home():

    return "Agnes Bot is running smoothly!"


def run_web_server():

    port = int(
        os.environ.get(
            "PORT",
            10000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
    )


# ============================================================
# Telegram Bot
# ============================================================

BOT_TOKEN = os.environ.get(
    "TELEGRAM_TOKEN"
)


if not BOT_TOKEN:

    raise RuntimeError(
        "未检测到 TELEGRAM_TOKEN，请在 Render 的 Environment Variables 中配置。"
    )


# ============================================================
# 主程序
# ============================================================

async def main():

    print("🤖 Agnes Bot 正在启动……")

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
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
            (
                filters.TEXT
                | filters.PHOTO
            )
            & ~filters.COMMAND,

            handle_message
        )

    )


    print("✅ Telegram Bot 已启动。")


    # --------------------------------------------------------
    # 启动轮询
    # --------------------------------------------------------

    await application.initialize()

    await application.start()

    await application.updater.start_polling()


    # 保持程序运行

    import asyncio

    while True:

        await asyncio.sleep(3600)


# ============================================================
# 程序入口
# ============================================================

if __name__ == "__main__":

    import asyncio

    # Flask 后台线程
    threading.Thread(
        target=run_web_server,
        daemon=True
    ).start()


    # Telegram Bot
    asyncio.run(main())
