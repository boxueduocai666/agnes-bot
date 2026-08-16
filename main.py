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
    filters,
)

from config import (
    CHAT_MODELS,
    DEFAULT_MODEL,
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


# ============================================================
# /start
# ============================================================

async def start_command(
    update: Update,
    context
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

        "🤖 **Agnes AI Telegram Bot**\n\n"

        "你好！我是群聊 AI 助手。\n\n"

        f"🧠 当前模型：**{current_name}**\n\n"

        "你可以：\n\n"

        "• 在群里 @我提问\n"
        "• 回复我的消息继续聊天\n"
        "• 发送图片让我分析\n"
        "• 使用 /choose 切换模型\n"
        "• 使用 /model 查看当前模型\n"
        "• 使用 /summary 总结群聊\n\n"

        "输入 /help 查看完整功能。",

        parse_mode="Markdown"
    )


# ============================================================
# /help
# ============================================================

async def help_command(
    update: Update,
    context
):

    if not update.message:
        return

    await update.message.reply_text(

        "📚 **功能菜单**\n\n"

        "🤖 **AI 对话**\n"
        "在群里 @机器人 + 问题，"
        "或者直接回复机器人的消息。\n\n"

        "🧠 **模型选择**\n"
        "/choose\n"
        "打开模型选择菜单。\n\n"

        "ℹ️ **当前模型**\n"
        "/model\n"
        "查看当前使用的模型。\n\n"

        "🖼️ **图片理解**\n"
        "发送图片并 @机器人，"
        "或者回复机器人发送的图片，"
        "机器人可以分析图片。\n\n"

        "📝 **群聊总结**\n"
        "/summary\n"
        "总结机器人记录到的群聊内容。\n\n"

        "💡 群聊中机器人不会主动回复普通消息，"
        "只有 @机器人、回复机器人或相关命令才会触发。",

        parse_mode="Markdown"
    )


# ============================================================
# /model
# ============================================================

async def model_command(
    update: Update,
    context
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

        "💡 **当前模型**\n\n"

        f"🧠 **{model_name}**\n\n"

        f"⚙️ 模型 ID：`{current_model}`\n\n"

        f"📌 {description}\n\n"

        "使用 /choose 可以切换模型。",

        parse_mode="Markdown"
    )


# ============================================================
# /choose
#
# 只负责显示模型名称。
# 模型 ID 只存在于 callback_data 中。
# ============================================================

async def choose_command(
    update: Update,
    context
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
    # 生成模型按钮
    # --------------------------------------------------------

    for model_id, info in CHAT_MODELS.items():

        # 只读取 name
        # 不把 model_id 拼到按钮文字里

        button_name = info.get(
            "name",
            model_id
        )


        # 当前模型增加勾选标记

        if model_id == current_model:

            button_name = (
                "✅ "
                + button_name
            )


        keyboard.append([

            InlineKeyboardButton(

                button_name,

                # ID 只放这里
                # 用户看不到

                callback_data=(
                    f"choose:{model_id}"
                )

            )

        ])


    # --------------------------------------------------------
    # 关闭按钮
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

        "🧠 **选择 AI 模型**\n\n"

        "点击下面的模型即可切换。\n\n"

        f"当前：**{current_name}**",

        reply_markup=reply_markup,

        parse_mode="Markdown"
    )


# ============================================================
# 模型按钮回调
# ============================================================

async def choose_callback(
    update: Update,
    context
):

    query = update.callback_query


    if not query:
        return


    await query.answer()


    data = query.data


    if not data:
        return


    if not data.startswith("choose:"):
        return


    # --------------------------------------------------------
    # 获取模型 ID
    # --------------------------------------------------------

    value = data.split(
        ":",
        1
    )[1]


    # --------------------------------------------------------
    # 关闭菜单
    # --------------------------------------------------------

    if value == "close":

        await query.edit_message_text(

            "❌ 已关闭模型选择菜单。"

        )

        return


    # --------------------------------------------------------
    # 检查模型是否存在
    # --------------------------------------------------------

    if value not in CHAT_MODELS:

        await query.edit_message_text(

            "❌ 无效的模型。\n\n"
            "请重新使用 /choose。"

        )

        return


    # --------------------------------------------------------
    # 切换模型
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
    # 获取模型信息
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
    # 返回切换结果
    # --------------------------------------------------------

    await query.edit_message_text(

        "✅ **模型切换成功！**\n\n"

        f"🧠 当前模型：**{model_name}**\n\n"

        f"📌 {description}\n\n"

        "之后你的 AI 对话将使用这个模型。",

        parse_mode="Markdown"
    )


# ============================================================
# Telegram 命令菜单
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
# 主程序
# ============================================================

def main():

    # --------------------------------------------------------
    # Telegram Token
    # --------------------------------------------------------

    import os

    TELEGRAM_TOKEN = os.environ.get(
        "TELEGRAM_TOKEN"
    )


    if not TELEGRAM_TOKEN:

        raise RuntimeError(

            "未检测到 TELEGRAM_TOKEN，"
            "请在 Render → Environment 中配置。"

        )


    # --------------------------------------------------------
    # 创建 Application
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
    # 模型选择按钮
    # ========================================================

    application.add_handler(

        CallbackQueryHandler(

            choose_callback,

            pattern=r"^choose:"

        )

    )


    # ========================================================
    # 普通消息
    # ========================================================

    application.add_handler(

        MessageHandler(

            filters.ALL,

            handle_message

        )

    )


    # ========================================================
    # 启动日志
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

    print("=" * 60)


    # ========================================================
    # 启动 Bot
    # ========================================================

    application.run_polling()


# ============================================================
# Entry
# ============================================================

if __name__ == "__main__":

    main()
