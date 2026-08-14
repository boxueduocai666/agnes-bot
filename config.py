import os

# ============================================================
# Agnes API
# ============================================================

AGNES_API_KEY = os.environ.get("AGNES_API_KEY")

AGNES_BASE_URL = os.environ.get(
    "AGNES_BASE_URL",
    "https://apihub.agnes-ai.com/v1"
)

if not AGNES_API_KEY:
    raise RuntimeError(
        "未检测到 AGNES_API_KEY，请在 Render → Environment 中配置。"
    )


# ============================================================
# 模型配置
# ============================================================

# 默认模型
DEFAULT_MODEL = "agnes-2.0-flash"


# Telegram 中 /choose 显示的模型
AVAILABLE_MODELS = {

    "agnes-2.0-flash": {
        "name": "⚡ Agnes 2.0 Flash",
        "description": "速度快、综合能力强"
    },

    "agnes-2.5-flash": {
        "name": "🚀 Agnes 2.5 Flash",
        "description": "更强推理、代码和视觉能力"
    },

    "agnes-2.5-pro": {
        "name": "🧠 Agnes 2.5 Pro",
        "description": "高质量综合回答"
    },

    "agnes-2.5-pro-alpha": {
        "name": "🧪 Agnes 2.5 Pro Alpha",
        "description": "实验性 Pro 模型"
    },

}


# ============================================================
# 图片理解模型
# ============================================================

VISION_MODEL = "agnes-2.5-flash"


# ============================================================
# 群聊历史
# ============================================================

MAX_HISTORY = 100


# ============================================================
# Telegram 消息长度
# ============================================================

MAX_TELEGRAM_LENGTH = 4000
