import os
import asyncio
import threading
from flask import Flask, request, jsonify

from telegram import Update
from telegram.ext import Application

from bot_logic import register_handlers


# ============================================================
# 1. 基础配置
# ============================================================

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

if not TELEGRAM_TOKEN:
    raise RuntimeError(
        "未检测到 TELEGRAM_TOKEN，请在 Render → Environment 中配置。"
    )


# Render 会自动提供 RENDER_EXTERNAL_URL
# 也可以自己在 Environment 中配置 WEBHOOK_URL
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL")

WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

if not WEBHOOK_URL:
    if RENDER_EXTERNAL_URL:
        WEBHOOK_URL = f"{RENDER_EXTERNAL_URL}/webhook"
    else:
        raise RuntimeError(
            "未找到 WEBHOOK_URL 或 RENDER_EXTERNAL_URL。"
        )


# 可选的 Webhook 安全密钥
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")


# ============================================================
# 2. Flask
# ============================================================

app = Flask(__name__)


@app.route("/")
def home():
    return "Agnes Bot is running smoothly!"


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "service": "agnes-bot"
    })


# ============================================================
# 3. Telegram Application
# ============================================================

telegram_app = (
    Application.builder()
    .token(TELEGRAM_TOKEN)
    .build()
)


# 注册所有 Telegram 消息处理器
register_handlers(telegram_app)


# ============================================================
# 4. Telegram 后台事件循环
# ============================================================

telegram_loop = asyncio.new_event_loop()


async def start_telegram():
    """
    初始化 Telegram Bot，并设置 Webhook。
    """

    await telegram_app.initialize()
    await telegram_app.start()

    # 设置 Webhook
    await telegram_app.bot.set_webhook(
        url=WEBHOOK_URL,
        secret_token=WEBHOOK_SECRET if WEBHOOK_SECRET else None,
        drop_pending_updates=False
    )

    print("=" * 60)
    print("Telegram Bot 已启动")
    print(f"Webhook: {WEBHOOK_URL}")
    print("=" * 60)

    # 保持事件循环运行
    await asyncio.Event().wait()


def telegram_thread_target():
    """
    Telegram 独立后台线程。
    """

    asyncio.set_event_loop(telegram_loop)

    try:
        telegram_loop.run_until_complete(start_telegram())
    except Exception as e:
        print("Telegram 后台线程发生错误：")
        print(repr(e))


# ============================================================
# 5. Webhook 接收接口
# ============================================================

@app.route("/webhook", methods=["POST"])
def telegram_webhook():

    # 如果配置了 Webhook Secret，就验证请求
    if WEBHOOK_SECRET:

        received_secret = request.headers.get(
            "X-Telegram-Bot-Api-Secret-Token"
        )

        if received_secret != WEBHOOK_SECRET:
            return jsonify({
                "ok": False,
                "error": "Unauthorized"
            }), 403

    try:

        data = request.get_json(force=True)

        update = Update.de_json(
            data,
            telegram_app.bot
        )

        # 把 Telegram 更新交给后台 asyncio
        future = asyncio.run_coroutine_threadsafe(
            telegram_app.process_update(update),
            telegram_loop
        )

        # 不等待处理完成，立即告诉 Telegram 收到了
        return jsonify({
            "ok": True
        })

    except Exception as e:

        print("Webhook 处理失败：")
        print(repr(e))

        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500


# ============================================================
# 6. 启动
# ============================================================

if __name__ == "__main__":

    # 启动 Telegram 后台线程
    threading.Thread(
        target=telegram_thread_target,
        daemon=True
    ).start()

    # Render 需要监听 PORT
    port = int(os.environ.get("PORT", 10000))

    print(f"Flask Web 服务启动，端口：{port}")

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        use_reloader=False
    )
