import os
import logging
from collections import defaultdict
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from openai import OpenAI
from duckduckgo_search import DDGS

# 从 Render 环境变量中安全获取配置
AGNES_API_KEY = os.environ.get("AGNES_API_KEY")
AGNES_BASE_URL = "https://apihub.agnes-ai.com/v1"
MODEL_NAME = "agnes-2.0-flash"
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

client = OpenAI(api_key=AGNES_API_KEY, base_url=AGNES_BASE_URL)

# 内存缓存：{chat_id: [{"user": "张三", "text": "你好", "message_id": 123}]}
group_history = defaultdict(list)
MAX_HISTORY = 100  # 每个群最大保留消息条数

# 简单的网页搜索函数
def search_web(query: str) -> str:
    try:
        with DDGS() as ddgs:
            results = [r for r in ddgs.text(query, max_results=3)]
            if not results:
                return "未找到相关联网信息。"
            search_summary = "\n".join([f"- {r['title']}: {r['body']} ({r['href']})" for r in results])
            return search_summary
    except Exception as e:
        return f"搜索出错: {str(e)}"

# 监听普通消息并记录，同时响应 Direct/@ 问答
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    chat = update.effective_chat
    chat_id = chat.id
    user_name = update.effective_user.first_name or "Anonymous"
    text = update.message.text
    message_id = update.message.message_id

    # 1. 缓存消息（带上 message_id，忽略指令）
    if not text.startswith('/'):
        group_history[chat_id].append({
            "user": user_name,
            "text": text,
            "message_id": message_id
        })
        if len(group_history[chat_id]) > MAX_HISTORY:
            group_history[chat_id].pop(0)

    # 2. 基础问答（私聊，或者在群里被 @ 时触发）
    bot_username = context.bot.username
    is_private = chat.type == "private"
    is_mentioned = bot_username and f"@{bot_username}" in text

    if is_private or is_mentioned:
        prompt = text.replace(f"@{bot_username}", "").strip() if bot_username else text.strip()
        if not prompt:
            return

        # 发送一个“正在思考/搜索”的提示
        processing_msg = await update.message.reply_text("正在联网查询中...")

        try:
            # 自动执行网页搜索，获取实时资讯
            search_results = search_web(prompt)

            system_prompt = (
                "你是一个精明的 AI 助手。用户向你提问，并附带了相关的互联网实时搜索结果。\n"
                "请根据以下搜索结果，准确、实时地回答用户的问题。如果搜索结果中没有答案，请根据你的知识库回答并说明。\n"
                f"实时搜索结果：\n{search_results}"
            )

            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ]
            )
            reply = response.choices[0].message.content
            
            # 编辑更新回复内容
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=processing_msg.message_id,
                text=reply,
                parse_mode="Markdown"
            )
        except Exception as e:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=processing_msg.message_id,
                text=f"请求失败: {str(e)}"
            )

# 群总结命令 /summary（支持蓝色可跳转标题）
async def handle_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    chat_id = chat.id
    history = group_history.get(chat_id, [])

    if len(history) < 3:
        await update.message.reply_text("群内消息记录太少，还不足以生成总结哦。")
        return

    status_msg = await update.message.reply_text("正在读取历史消息并生成总结...")

    if chat.username:
        chat_link_prefix = f"https://t.me/{chat.username}"
    else:
        chat_id_str = str(chat_id)
        if chat_id_str.startswith("-100"):
            internal_id = chat_id_str[4:]
        else:
            internal_id = chat_id_str.replace("-", "")
        chat_link_prefix = f"https://t.me/c/{internal_id}"

    formatted_lines = []
    for item in history:
        msg_link = f"{chat_link_prefix}/{item['message_id']}"
        formatted_lines.append(f"[消息链接: {msg_link}] {item['user']}: {item['text']}")
    
    formatted_history = "\n".join(formatted_lines)
    msg_count = len(history)

    system_prompt = (
        "你是一个精细化的群聊摘要助手。请根据提供的聊天记录（每条记录前都带有对应的专属跳转链接），严格按照以下格式输出：\n\n"
        f"📝 **群聊 AI 总结**\n"
        f"💬 已分析 {msg_count} 条有效消息，整理出主要话题\n\n"
        "请列出 3-5 个核心话题。每个话题的标题必须采用 Markdown 超链接格式，格式为：`[序号. 话题名称](对应的消息链接)`。\n"
        "例如：`1. [W电源装机图](https://t.me/c/...)`\n"
        "并在标题下方详细描述该话题的讨论内容和细节。\n\n"
        "最后附上一行固定提示：\n"
        "_点击蓝色标题可跳转到相关消息。_\n\n"
        "要求：忽略无意义的打招呼和纯灌水，重点提取有价值的讨论。直接输出总结内容，不要带任何多余的客套话。"
    )

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"聊天记录:\n{formatted_history}"}
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

