import os
import logging
from collections import defaultdict
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from openai import OpenAI

# 从 Render 环境变量中安全获取配置
AGNES_API_KEY = os.environ.get("AGNES_API_KEY")
AGNES_BASE_URL = "https://apihub.agnes-ai.com/v1"
MODEL_NAME = "agnes-2.0-flash"
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

client = OpenAI(api_key=AGNES_API_KEY, base_url=AGNES_BASE_URL)

# 内存缓存：{chat_id: [{"user": "张三", "text": "你好"}]}
group_history = defaultdict(list)
MAX_HISTORY = 100  # 每个群最大保留消息条数

# 监听普通消息并记录，同时响应 Direct/@ 问答
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    chat_id = update.effective_chat.id
    user_name = update.effective_user.first_name or "Anonymous"
    text = update.message.text

    # 1. 缓存消息（忽略指令消息）
    if not text.startswith('/'):
        group_history[chat_id].append(f"{user_name}: {text}")
        if len(group_history[chat_id]) > MAX_HISTORY:
            group_history[chat_id].pop(0)

    # 2. 基础问答（私聊，或者在群里被 @ 时触发）
    bot_username = context.bot.username
    is_private = update.message.chat.type == "private"
    is_mentioned = f"@{bot_username}" in text

    if is_private or is_mentioned:
        prompt = text.replace(f"@{bot_username}", "").strip()
        if not prompt:
            return

        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": "你是一个友好的 Telegram 群组小助手。"},
                    {"role": "user", "content": prompt}
                ]
            )
            reply = response.choices[0].message.content
            await update.message.reply_text(reply, parse_mode="Markdown")
        except Exception as e:
            await update.message.reply_text(f"请求失败: {str(e)}")

# 群总结命令 /summary
async def handle_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    history = group_history.get(chat_id, [])

    if len(history) < 5:
        await update.message.reply_text("群内消息记录太少，还不足以生成总结哦。")
        return

    status_msg = await update.message.reply_text("正在读取历史消息并生成总结...")
    formatted_history = "\n".join(history)

    system_prompt = (
        "你是一个高效的群聊摘要助手。请根据提供的聊天记录进行客观总结。\n"
        "要求：\n"
        "1. 提取 2-4 个主要讨论议题\n"
        "2. 梳理主要结论或共识\n"
        "3. 待办事项提取（如有）\n"
        "4. 忽略打招呼等无意义闲聊，输出结构明确的 Markdown"
    )

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"聊天记录：\n{formatted_history}"}
            ]
        )
        summary = response.choices[0].message.content
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=status_msg.message_id,
            text=summary,
            parse_mode="Markdown"
        )
    except Exception as e:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=status_msg.message_id,
            text=f"生成总结出错: {str(e)}"
        )

if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("summary", handle_summary))
    app.add_handler(MessageHandler(filters.TEXT, handle_message))
    
    print("Bot 已成功运行...")
    app.run_polling()
