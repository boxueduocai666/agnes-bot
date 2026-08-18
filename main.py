import os
import threading

from flask import Flask

from telegram import (
    Update,
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from config import (
    CHAT_MODELS,
    DEFAULT_MODEL,
    TELEGRAM_TOKEN,
)

from ai_logic import (
    set_user_model,
    get_user_model,
    get_model_display_name,
)

from bot_logic import (
    handle_message,
    handle_summary,
)

from database import (
    init_database,
)


# ============================================================
# Render Health Server
# ============================================================

flask_app = Flask(
    __name__
)


@flask_app.route("/")
def health():

    return (
        "Agnes Telegram Bot is running.",
        200
    )


@flask_app.route("/health")
def health_check():

    return (
        "OK",
        200
    )


def run_health_server():

    port = int(
        os.getenv(
            "PORT",
            "10000"
        )
    )

    flask_app.run(

        host="0.0.0.0",

        port=port,

        debug=False,

        use_reloader=False

    )


# ============================================================
# /start
# ============================================================

async def start_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return


    user_id = update.effective_user.id


    current_model = get_user_model(
        user_id
    )


    current_name = get_model_display_name(
        current_model
    )


    await update.message.reply_text(

        "🤖 <b>Agnes AI Telegram Bot</b>\n\n"

        "你好！我是群聊 AI 助手。\n\n"

        f"🧠 当前模型：<b>{current_name}</b>\n\n"

        "你可以：\n\n"

        "• 在群里 @我提问\n"
        "• 回复我的消息继续聊天\n"
        "• 发送图片让我分析\n"
        "• 使用 /choose 切换模型\n"
        "• 使用 /model 查看当前模型\n"
        "• 使用 /summary 总结群聊\n\n"

        "输入 /help 查看完整功能。",

        parse_mode="HTML"

    )


# ============================================================
# /help
# ============================================================

async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return


    await update.message.reply_text(

        "📚 <b>功能菜单</b>\n\n"

        "🤖 <b>AI 对话</b>\n"
        "在群里 @机器人 + 问题，"
        "或者直接回复机器人的消息。\n\n"

        "🧠 <b>模型选择</b>\n"
        "/choose\n"
        "打开模型选择菜单。\n\n"

        "ℹ️ <b>当前模型</b>\n"
        "/model\n"
        "查看当前使用的模型。\n\n"

        "🖼️ <b>图片理解</b>\n"
        "发送图片并 @机器人，"
        "或者回复机器人发送的图片，"
        "机器人可以分析图片。\n\n"

        "📝 <b>群聊总结</b>\n"
        "/summary\n"
        "总结机器人记录到的群聊内容。\n\n"

        "💡 群聊中机器人不会主动回复普通消息，"
        "只有 @机器人、回复机器人或相关命令才会触发。",

        parse_mode="HTML"

    )


# ============================================================
# /model
# ============================================================

async def model_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return


    user_id = update.effective_user.id


    current_model = get_user_model(
        user_id
    )


    model_info = CHAT_MODELS.get(

        current_model,

        {}

    )


    description = model_info.get(

        "description",

        ""

    )


    model_name = get_model_display_name(
        current_model
    )


    await update.message.reply_text(

        "💡 <b>当前模型</b>\n\n"

        f"🧠 <b>{model_name}</b>\n\n"

        f"⚙️ 模型 ID：<code>{current_model}</code>\n\n"

        f"📌 {description}\n\n"

        "使用 /choose 可以切换模型。",

        parse_mode="HTML"

    )


# ============================================================
# /choose
# ============================================================

async def choose_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return


    user_id = update.effective_user.id


    current_model = get_user_model(
        user_id
    )


    current_name = get_model_display_name(
        current_model
    )


    keyboard = []


    # --------------------------------------------------------
    # Model Buttons
    # --------------------------------------------------------

    for model_id, info in CHAT_MODELS.items():

        button_name = info.get(

            "name",

            model_id

        )


        if model_id == current_model:

            button_name = (
                "✅ "
                + button_name
            )


        keyboard.append([

            InlineKeyboardButton(

                button_name,

                callback_data=(
                    f"choose:{model_id}"
                )

            )

        ])


    # --------------------------------------------------------
    # Close
    # --------------------------------------------------------

    keyboard.append([

        InlineKeyboardButton(

            "❌ 关闭",

            callback_data="choose:close"

        )

    ])


    reply_markup = InlineKeyboardMarkup(
        keyboard
    )


    await update.message.reply_text(

        "🧠 <b>选择 AI 模型</b>\n\n"

        "点击下面的模型即可切换。\n\n"

        f"当前：<b>{current_name}</b>",

        reply_markup=reply_markup,

        parse_mode="HTML"

    )


# ============================================================
# Model Callback
# ============================================================

async def choose_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query


    if not query:
        return


    await query.answer()


    data = query.data


    if not data:
        return


    if not data.startswith(
        "choose:"
    ):

        return


    value = data.split(
        ":",
        1
    )[1]


    # --------------------------------------------------------
    # Close
    # --------------------------------------------------------

    if value == "close":

        await query.edit_message_text(

            "❌ 已关闭模型选择菜单。"

        )

        return


    # --------------------------------------------------------
    # Check
    # --------------------------------------------------------

    if value not in CHAT_MODELS:

        await query.edit_message_text(

            "❌ 无效的模型。\n\n"
            "请重新使用 /choose。"

        )

        return


    # --------------------------------------------------------
    # Set Model
    # --------------------------------------------------------

    success = set_user_model(

        query.from_user.id,

        value

    )


    if not success:

        await query.edit_message_text(

            "❌ 模型切换失败。\n\n"
            "请重新使用 /choose。"

        )

        return


    # --------------------------------------------------------
    # Model Info
    # --------------------------------------------------------

    model_info = CHAT_MODELS.get(

        value,

        {}

    )


    model_name = get_model_display_name(
        value
    )


    description = model_info.get(

        "description",

        ""

    )


    # --------------------------------------------------------
    # Result
    # --------------------------------------------------------

    await query.edit_message_text(

        "✅ <b>模型切换成功！</b>\n\n"

        f"🧠 当前模型：<b>{model_name}</b>\n\n"

        f"📌 {description}\n\n"

        "之后你的 AI 对话将使用这个模型。",

        parse_mode="HTML"

    )


# ============================================================
# Telegram Command Menu
# ============================================================

async def setup_bot_commands(
    application
):

    commands = [

        BotCommand(
            "start",
            "开始使用机器人"
        ),

        BotCommand(
            "help",
            "查看帮助"
        ),

        BotCommand(
            "choose",
            "选择 AI 模型"
        ),

        BotCommand(
            "model",
            "查看当前模型"
        ),

        BotCommand(
            "summary",
            "总结群聊"
        ),

    ]


    await application.bot.set_my_commands(
        commands
    )


    print(
        "[MENU] Telegram 命令菜单设置完成"
    )


# ============================================================
# Main
# ============================================================

def main():

    print("=" * 60)

    print(
        "🚀 Agnes Telegram Bot 正在启动..."
    )

    print("=" * 60)


    # --------------------------------------------------------
    # Database
    # --------------------------------------------------------

    init_database()


    print(
        "[DATABASE] SQLite 初始化完成"
    )


    # --------------------------------------------------------
    # Render Health Server
    # --------------------------------------------------------

    health_thread = threading.Thread(

        target=run_health_server,

        daemon=True

    )


    health_thread.start()


    print(
        "[SERVER] Render Health Server 已启动"
    )


    # --------------------------------------------------------
    # Application
    # --------------------------------------------------------

    application = (

        Application.builder()

        .token(TELEGRAM_TOKEN)

        .post_init(
            setup_bot_commands
        )

        .build()

    )


    # ========================================================
    # Commands
    # ========================================================

    application.add_handler(

        CommandHandler(
            "start",
            start_command
        )

    )


    application.add_handler(

        CommandHandler(
            "help",
            help_command
        )

    )


    application.add_handler(

        CommandHandler(
            "choose",
            choose_command
        )

    )


    application.add_handler(

        CommandHandler(
            "model",
            model_command
        )

    )


    application.add_handler(

        CommandHandler(
            "summary",
            handle_summary
        )

    )


    # ========================================================
    # Model Callback
    # ========================================================

    application.add_handler(

        CallbackQueryHandler(

            choose_callback,

            pattern=r"^choose:"

        )

    )


    # ========================================================
    # Messages
    # ========================================================

    application.add_handler(

        MessageHandler(

            filters.ALL,

            handle_message

        )

    )


    # ========================================================
    # Startup Log
    # ========================================================

    print("=" * 60)

    print(
        "🤖 Agnes Telegram Bot 启动"
    )

    print(
        f"🧠 默认模型：{DEFAULT_MODEL}"
    )

    print(
        "🖼️ 图片理解：已启用"
    )

    print(
        "🎨 图片生成：未启用"
    )

    print(
        "🎬 视频生成：未启用"
    )

    print(
        "📝 群聊总结：已启用"
    )

    print(
        "🧠 模型选择：已启用"
    )

    print(
        "🌐 Render Health：已启用"
    )

    print("=" * 60)


    # ========================================================
    # Start Polling
    # ========================================================

    application.run_polling(
        drop_pending_updates=True
    )


# ============================================================
# Entry
# ============================================================

if __name__ == "__main__":

    main()
