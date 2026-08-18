import os


# ============================================================
# Telegram Bot
# ============================================================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

if not TELEGRAM_TOKEN:
    raise RuntimeError(
        "未检测到 TELEGRAM_TOKEN，请在 Render → Environment 中配置。"
    )


# ============================================================
# Agnes / OpenAI Compatible API
# ============================================================

AGNES_API_KEY = os.getenv("AGNES_API_KEY")

if not AGNES_API_KEY:
    raise RuntimeError(
        "未检测到 AGNES_API_KEY，请在 Render → Environment 中配置。"
    )


AGNES_BASE_URL = os.getenv("AGNES_BASE_URL")

if not AGNES_BASE_URL:
    raise RuntimeError(
        "未检测到 AGNES_BASE_URL，请在 Render → Environment 中配置。"
    )


# ============================================================
# AI Models
# ============================================================

CHAT_MODELS = {

    "agnes-2.0-flash": {
        "name": "Agnes 2.0 Flash",
        "description": "速度快，适合日常聊天和普通问题。",
    },

    "agnes-2.5-flash": {
        "name": "Agnes 2.5 Flash",
        "description": "速度与能力比较均衡。",
    },

    "agnes-2.5-pro": {
        "name": "Agnes 2.5 Pro",
        "description": "更强的推理和复杂问题处理能力。",
    },

    "agnes-2.5-pro-alpha": {
        "name": "Agnes 2.5 Pro Alpha",
        "description": "实验性高级模型，适合复杂任务。",
    },

}


# ============================================================
# Default Model
# ============================================================

DEFAULT_MODEL = os.getenv(
    "DEFAULT_MODEL",
    "agnes-2.0-flash"
)


if DEFAULT_MODEL not in CHAT_MODELS:
    raise RuntimeError(
        f"DEFAULT_MODEL 无效：{DEFAULT_MODEL}"
    )


# ============================================================
# Image Model
#
# 如果图片模型与普通聊天模型不同，
# 可以在 Render Environment 中单独设置 IMAGE_MODEL。
#
# 如果没有设置，则默认使用 DEFAULT_MODEL。
# ============================================================

IMAGE_MODEL = os.getenv(
    "IMAGE_MODEL",
    DEFAULT_MODEL
)


# ============================================================
# Group History
# ============================================================

MAX_HISTORY = int(
    os.getenv(
        "MAX_HISTORY",
        "100"
    )
)


# ============================================================
# Auto Summary
# ============================================================

AUTO_SUMMARY_MESSAGE_COUNT = int(
    os.getenv(
        "AUTO_SUMMARY_MESSAGE_COUNT",
        "100"
    )
)


# ============================================================
# Telegram Message Limit
# ============================================================

MAX_TELEGRAM_LENGTH = 4000


# ============================================================
# SQLite
# ============================================================

DB_FILE = os.getenv(
    "DB_FILE",
    "bot_data.db"
)
