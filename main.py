import os
import asyncio
import threading

from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import Application

from bot_logic import register_handlers


# ============================================================
# 1. 环境变量
# ============================================================

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
AGNES_API_KEY = os.environ.get("AGNES_API_KEY")

RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")


if not TELEGRAM_TOKEN:
    raise RuntimeError("❌ 未检测到 TELEGRAM_TOKEN")

if not AGNES_API_KEY:
    raise RuntimeError("❌ 未检测到 AGNES_API_KEY")


# 自动生成 Webhook 地址
if not WEBHOOK_URL:

    if not RENDER_EXTERNAL_URL:
        raise RuntimeError(
            "❌ 未检测到 WEBHOOK_URL 或 RENDER_EXTERNAL_URL"
        )

    WEBHOOK_URL = f"{RENDER_EXTERNAL_URL}/webhook"


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

print("🔵 正在创建 Telegram Application...")

telegram_app = (
    Application.builder()
    .token(TELEGRAM_TOKEN)
    .build()
)

print("🟢 Telegram Application 创建成功")


# 注册消息处理器
print("🔵 正在注册 Telegram handlers...")

register_handlers(telegram_app)

print("🟢 Telegram handlers 注册成功")


# ============================================================
# 4. Telegram asyncio
# ============================================================

telegram_loop = asyncio.new_event_loop()


async def start_telegram():

    print("🔵 Telegram 后台初始化开始")

    try:

        # 初始化
        await telegram_app.initialize()

        print("🟢 Telegram Application 初始化成功")

        # 启动 Application
        await telegram_app.start()

        print("🟢 Telegram Application 启动成功")

        # 设置 Webhook
        print("🔵 正在设置 Telegram Webhook...")
        print(f"🔗 Webhook URL: {WEBHOOK_URL}")

        await telegram_app.bot.set_webhook(
            url=WEBHOOK_URL,
            secret_token=WEBHOOK_SECRET if WEBHOOK_SECRET else None,
            drop_pending_updates=False
        )

        print("🟢 Telegram Webhook 设置成功")

        # 获取 Webhook 状态
        webhook_info = await telegram_app.bot.get_webhook_info()

        print("=" * 60)
        print("🎉 Telegram Bot 已成功启动")
        print(f"Webhook: {WEBHOOK_URL}")
        print(f"Webhook 当前地址: {webhook_info.url}")
        print(f"Pending updates: {webhook_info.pending_update_count}")
        print("=" * 60)

        # 永久运行
        await asyncio.Event().wait()

    except Exception as e:

        print("=" * 60)
        print("❌ Telegram 后台启动失败")
        print(repr(e))
        print("=" * 60)

        raise


def telegram_thread_target():

    print("🔵 正在启动 Telegram 后台线程...")

    asyncio.set_event_loop(telegram_loop)

    try:

        telegram_loop.run_until_complete(
            start_telegram()
        )

    except Exception as e:

        print("=" * 60)
        print("❌ Telegram 后台线程发生错误")
        print(repr(e))
        print("=" * 60)


# ============================================================
# 5. Webhook
# ============================================================

@app.route("/webhook", methods=["POST"])
def telegram_webhook():

    print("📩 收到 Telegram Webhook")

    # 验证 Secret
    if WEBHOOK_SECRET:

        received_secret = request.headers.get(
            "X-Telegram-Bot-Api-Secret-Token"
        )

        if received_secret != WEBHOOK_SECRET:

            print("❌ Webhook Secret 验证失败")

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

        # 将 Telegram 更新交给 asyncio
        asyncio.run_coroutine_threadsafe(
            telegram_app.process_update(update),
            telegram_loop
        )

        print("🟢 Telegram Update 已提交处理")

        return jsonify({
            "ok": True
        })

    except Exception as e:

        print("❌ Webhook 处理失败")
        print(repr(e))

        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500


# ============================================================
# 6. 启动 Flask + Telegram
# ============================================================

if __name__ == "__main__":

    print("=" * 60)
    print("🚀 Agnes Telegram Bot 正在启动")
    print("=" * 60)

    # 启动 Telegram 后台线程
    telegram_thread = threading.Thread(
        target=telegram_thread_target,
        daemon=True
    )

    telegram_thread.start()

    print("🟢 Telegram 后台线程已启动")

    # Render PORT
    port = int(
        os.environ.get("PORT", 10000)
    )

    print(f"🌐 Flask Web 服务启动，端口: {port}")
    print(f"🌐 Webhook 地址: {WEBHOOK_URL}")

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        use_reloader=False
        )
