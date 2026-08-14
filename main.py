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
    raise RuntimeError(
        "❌ 未检测到 TELEGRAM_TOKEN，请在 Render → Environment 配置。"
    )

if not AGNES_API_KEY:
    raise RuntimeError(
        "❌ 未检测到 AGNES_API_KEY，请在 Render → Environment 配置。"
    )


# 如果没有手动设置 WEBHOOK_URL，
# 自动使用 Render 提供的 RENDER_EXTERNAL_URL
if not WEBHOOK_URL:

    if not RENDER_EXTERNAL_URL:
        raise RuntimeError(
            "❌ 未找到 WEBHOOK_URL 或 RENDER_EXTERNAL_URL。"
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

print("[START] 正在创建 Telegram Application...", flush=True)

telegram_app = (
    Application.builder()
    .token(TELEGRAM_TOKEN)
    .build()
)

print("[OK] Telegram Application 创建成功", flush=True)


# ============================================================
# 4. 注册 Telegram handlers
# ============================================================

print("[START] 正在注册 Telegram handlers...", flush=True)

register_handlers(telegram_app)

print("[OK] Telegram handlers 注册成功", flush=True)


# ============================================================
# 5. Telegram asyncio
# ============================================================

telegram_loop = asyncio.new_event_loop()


async def start_telegram():

    print("=" * 60, flush=True)
    print("[TG 1/6] Telegram 初始化开始", flush=True)

    try:

        # ----------------------------------------------------
        # 初始化
        # ----------------------------------------------------

        await telegram_app.initialize()

        print(
            "[TG 2/6] Telegram initialize() 成功",
            flush=True
        )

        # ----------------------------------------------------
        # 启动 Application
        # ----------------------------------------------------

        await telegram_app.start()

        print(
            "[TG 3/6] Telegram start() 成功",
            flush=True
        )

        # ----------------------------------------------------
        # 设置 Webhook
        # ----------------------------------------------------

        print(
            "[TG 4/6] 正在设置 Telegram Webhook...",
            flush=True
        )

        print(
            f"[TG] Webhook URL = {WEBHOOK_URL}",
            flush=True
        )

        if WEBHOOK_SECRET:
            print(
                "[TG] Webhook Secret = 已配置",
                flush=True
            )
        else:
            print(
                "[TG] Webhook Secret = 未配置",
                flush=True
            )

        await telegram_app.bot.set_webhook(
            url=WEBHOOK_URL,
            secret_token=(
                WEBHOOK_SECRET
                if WEBHOOK_SECRET
                else None
            ),
            drop_pending_updates=False
        )

        print(
            "[TG 5/6] ✅ Telegram Webhook 设置成功",
            flush=True
        )

        # ----------------------------------------------------
        # 获取 Webhook 当前状态
        # ----------------------------------------------------

        webhook_info = (
            await telegram_app.bot.get_webhook_info()
        )

        print(
            "[TG 6/6] ✅ Webhook 当前状态",
            flush=True
        )

        print(
            f"[TG] 当前 Webhook URL: {webhook_info.url}",
            flush=True
        )

        print(
            f"[TG] Pending updates: "
            f"{webhook_info.pending_update_count}",
            flush=True
        )

        print(
            f"[TG] Last error date: "
            f"{webhook_info.last_error_date}",
            flush=True
        )

        print(
            f"[TG] Last error message: "
            f"{webhook_info.last_error_message}",
            flush=True
        )

        print("=" * 60, flush=True)

        print(
            "🎉 Telegram Bot Webhook 启动完成！",
            flush=True
        )

        print(
            f"Webhook: {WEBHOOK_URL}",
            flush=True
        )

        print("=" * 60, flush=True)

        # 永久保持 asyncio 事件循环
        await asyncio.Event().wait()

    except Exception as e:

        print("=" * 60, flush=True)

        print(
            "❌ Telegram 后台启动失败",
            flush=True
        )

        print(
            f"错误类型: {type(e).__name__}",
            flush=True
        )

        print(
            f"错误内容: {e}",
            flush=True
        )

        print("=" * 60, flush=True)

        raise


# ============================================================
# 6. Telegram 后台线程
# ============================================================

def telegram_thread_target():

    print(
        "[THREAD] 正在启动 Telegram 后台线程...",
        flush=True
    )

    asyncio.set_event_loop(telegram_loop)

    try:

        telegram_loop.run_until_complete(
            start_telegram()
        )

    except Exception as e:

        print("=" * 60, flush=True)

        print(
            "❌ Telegram 后台线程发生错误",
            flush=True
        )

        print(
            f"错误类型: {type(e).__name__}",
            flush=True
        )

        print(
            f"错误内容: {e}",
            flush=True
        )

        print("=" * 60, flush=True)


# ============================================================
# 7. Telegram Webhook 接收接口
# ============================================================

@app.route("/webhook", methods=["POST"])
def telegram_webhook():

    print(
        "[WEBHOOK] 📩 收到 Telegram 请求",
        flush=True
    )

    # --------------------------------------------------------
    # Secret 验证
    # --------------------------------------------------------

    if WEBHOOK_SECRET:

        received_secret = request.headers.get(
            "X-Telegram-Bot-Api-Secret-Token"
        )

        if received_secret != WEBHOOK_SECRET:

            print(
                "[WEBHOOK] ❌ Secret 验证失败",
                flush=True
            )

            return jsonify({
                "ok": False,
                "error": "Unauthorized"
            }), 403

        print(
            "[WEBHOOK] ✅ Secret 验证成功",
            flush=True
        )

    # --------------------------------------------------------
    # 读取 Telegram Update
    # --------------------------------------------------------

    try:

        data = request.get_json(force=True)

        print(
            "[WEBHOOK] ✅ 收到 Telegram Update",
            flush=True
        )

        update = Update.de_json(
            data,
            telegram_app.bot
        )

        # ----------------------------------------------------
        # 交给 Telegram Application 处理
        # ----------------------------------------------------

        asyncio.run_coroutine_threadsafe(
            telegram_app.process_update(update),
            telegram_loop
        )

        print(
            "[WEBHOOK] ✅ Update 已提交给 Telegram Application",
            flush=True
        )

        return jsonify({
            "ok": True
        })

    except Exception as e:

        print(
            "[WEBHOOK] ❌ Webhook 处理失败",
            flush=True
        )

        print(
            f"[WEBHOOK] 错误类型: {type(e).__name__}",
            flush=True
        )

        print(
            f"[WEBHOOK] 错误内容: {e}",
            flush=True
        )

        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500


# ============================================================
# 8. 启动 Flask + Telegram
# ============================================================

if __name__ == "__main__":

    print("=" * 60, flush=True)

    print(
        "🚀 Agnes Telegram Bot 正在启动",
        flush=True
    )

    print("=" * 60, flush=True)

    # --------------------------------------------------------
    # 启动 Telegram 后台线程
    # --------------------------------------------------------

    telegram_thread = threading.Thread(
        target=telegram_thread_target,
        daemon=True
    )

    telegram_thread.start()

    print(
        "[THREAD] ✅ Telegram 后台线程已启动",
        flush=True
    )

    # --------------------------------------------------------
    # Render PORT
    # --------------------------------------------------------

    port = int(
        os.environ.get("PORT", 10000)
    )

    print(
        f"[FLASK] Web 服务端口: {port}",
        flush=True
    )

    print(
        f"[FLASK] Webhook 地址: {WEBHOOK_URL}",
        flush=True
    )

    print("=" * 60, flush=True)

    # --------------------------------------------------------
    # 启动 Flask
    # --------------------------------------------------------

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        use_reloader=False
            )
