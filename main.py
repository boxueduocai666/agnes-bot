from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    BotCommand,
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
    DEFAULT_MODEL,
    AVAILABLE_MODELS,
)

from ai_logic import (
    get_user_model,
    set_user_model,
)

from bot_logic import (
    handle_message,
    handle_summary,
)


# ============================================================
# /choose
# ============================================================

async def choose_model(

    update: Update,

    context: ContextTypes.DEFAULT_TYPE

):

    user = update.effective_user


    if not user:

        return


    current_model = get_user_model(

        user.id

    )


    keyboard = []


    for model_id, info in AVAILABLE_MODELS.items():

        current_mark = (

            " ✅"

            if model_id == current_model

            else ""

        )


        button_text = (

            info["name"]

            + current_mark

        )


        keyboard.append([

            InlineKeyboardButton(

                button_text,

                callback_data=f"model:{model_id}"

            )

        ])


    keyboard.append([

        InlineKeyboardButton(

            "❌ 关闭",

            callback_data="model:close"

        )

    ])


    reply_markup = InlineKeyboardMarkup(

        keyboard

    )


    await update.message.reply_text(

        "🤖 **选择 AI 模型**\n\n"

        f"当前模型：`{current_model}`\n\n"

        "点击下面的按钮即可切换模型：",

        reply_markup=reply_markup,

        parse_mode="Markdown"

    )


# ============================================================
# 模型按钮
# ============================================================

async def model_callback(

    update: Update,

    context: ContextTypes.DEFAULT_TYPE

):

    query = update.callback_query


    await query.answer()


    user = query.from_user


    data = query.data


    if data == "model:close":

        try:

            await query.edit_message_text(

                "❌ 已关闭模型选择。"

            )

        except Exception:

            pass

        return


    if not data.startswith("model:"):

        return


    model = data.split(

        ":",

        1

    )[1]


    if model not in AVAILABLE_MODELS:

        await query.edit_message_text(

            "❌ 无效的模型。"

        )

        return


    success = set_user_model(

        user.id,

        model

    )


    if not success:

        await query.edit_message_text(

            "❌ 模型切换失败。"

        )

        return


    info = AVAILABLE_MODELS[model]


    await query.edit_message_text(

        "✅ **模型切换成功**\n\n"

        f"当前模型：**{info['name']}**\n"

        f"模型 ID：`{model}`\n\n"

        "现在直接 @机器人 提问即可。",

        parse_mode="Markdown"

    )


# ============================================================
# 设置 Telegram 命令菜单
# ============================================================

async def post_init(

    application: Application

):

    await application.bot.set_my_commands([

        BotCommand(

            "choose",

            "🤖 选择 AI 模型"

        ),

        BotCommand(

            "summary",

            "📝 总结最近群聊"

        ),

    ])


    print(

        "[BOT] Telegram 命令菜单设置完成"

    )


# ============================================================
# 创建 Bot
# ============================================================

def main():

    import os


    bot_token = os.environ.get(

        "TELEGRAM_BOT_TOKEN"

    )


    if not bot_token:

        raise RuntimeError(

            "未检测到 TELEGRAM_BOT_TOKEN，"
            "请在 Render → Environment 中配置。"

        )


    application = (

        Application.builder()

        .token(bot_token)

        .post_init(post_init)

        .build()

    )


    # --------------------------------------------------------
    # /choose
    # --------------------------------------------------------

    application.add_handler(

        CommandHandler(

            "choose",

            choose_model

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
    # 模型按钮
    # --------------------------------------------------------

    application.add_handler(

        CallbackQueryHandler(

            model_callback,

            pattern=r"^model:"

        )

    )


    # --------------------------------------------------------
    # 普通消息 / 图片 / 回复
    # --------------------------------------------------------

    application.add_handler(

        MessageHandler(

            filters.ALL,

            handle_message

        )

    )


    print(

        "=" * 60

    )

    print(

        "🤖 Telegram AI Bot 启动"

    )

    print(

        f"默认模型：{DEFAULT_MODEL}"

    )

    print(

        "支持 /choose 模型选择"

    )

    print(

        "支持 /summary 群聊总结"

    )

    print(

        "=" * 60


    )


    application.run_polling()


# ============================================================
# 程序入口
# ============================================================

if __name__ == "__main__":

    main()
