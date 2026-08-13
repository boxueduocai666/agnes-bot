import os
from collections import defaultdict
from telegram import Update
from telegram.ext import ContextTypes
from openai import OpenAI
from duckduckgo_search import DDGS

# 从环境变量中获取配置
AGNES_API_KEY = os.environ.get("AGNES_API_KEY")
AGNES_BASE_URL = "https://apihub.agnes-ai.com/v1"
MODEL_NAME = "agnes-2.0-flash"

client = OpenAI(api_key=AGNES_API_KEY, base_url=AGNES_BASE_URL)

group_history = defaultdict(list)
MAX_HISTORY = 100

# 网页搜索函数
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

# 消息处理 & 联网问答
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    chat = update.effective_chat
    chat_id = chat.id
    user_name = update.effective_user.first_name or "Anonymous"
    text = update.message.text
    message_id = update.message.message_id

    if not text.startswith('/'):
        group_history[chat_id].append({"user": user_name, "text": text, "message_id": message_id})
        if len(group_history[chat_id]) > MAX_HISTORY:
            group_history[chat_id].pop(0)

    bot_username = context.bot.username
    is_private = chat.type == "private"
    is_mentioned = bot_username and f"@{bot_username}" in text

    if is_private or is_mentioned:
        prompt = text.replace(f"@{bot_username}", "").strip() if bot_username else text.strip()
        if not prompt:
            return

        processing_msg = await update.message.reply_text("正在联网查询中...")
        try:
            search_results = search_web(prompt)
            system_prompt = (
                "你是一个精明的 AI 助手。请根据以下联网搜索结果，实时、准确地回答用户的问题。\n"
                f"实时搜索结果：\n{search_results}"
            )
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ]
            )
            await context.bot.edit_message_text(
                chat_id=chat_id, message_id=processing_msg.message_id,
                text=response.choices[0].message.content, parse_mode="HTML"
            )
        except Exception as e:
            await context.bot.edit_message_text(
                chat_id=chat_id, message_id=processing_msg.message_id,
                text=f"请求失败: {str(e)}"
            )

# 群总结命令 /summary
async def handle_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    chat_id = chat.id
    history = group_history.get(chat_id, [])

    if len(history) < 3:
        await update.message.reply_text("记录太少，无法总结。")
        return

    status_msg = await update.message.reply_text("正在生成总结...")

    if chat.username:
        chat_link_prefix = f"https://t.me/{chat.username}"
    else:
        cid = str(chat_id).replace("-100", "").replace("-", "")
        chat_link_prefix = f"https://t.me/c/{cid}"

    formatted_lines = []
    for item in history:
        msg_link = f"{chat_link_prefix}/{item['message_id']}"
        formatted_lines.append(f"• <a href='{msg_link}'>{item['user']}</a>: {item['text']}")
    
    formatted_history = "\n".join(formatted_lines)
    msg_count = len(history)

    system_prompt = (
        "你是一个群聊总结助手。请严格按照以下 HTML 格式输出：\n\n"
        "<b>📝 群聊 AI 总结</b>\n"
        f"💬 已分析 {msg_count} 条消息\n\n"
        "请列出 3-5 个话题。话题标题格式为：<b>1. <a href='对应的跳转链接'>话题名称</a></b>\n"
        "内容简短描述。最后加上：<i>点击蓝色标题可跳转。</i>\n\n"
        "不要使用 Markdown 符号，全部使用 HTML 标签(<b>, <a>, <i>)。"
    )

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"聊天记录:\n{formatted_history}"}
            ]
        )
        await context.bot.edit_message_text(
            chat_id=chat_id, message_id=status_msg.message_id,
            text=response.choices[0].message.content, parse_mode="HTML"
        )
    except Exception as e:
        await context.bot.edit_message_text(chat_id=chat_id, message_id=status_msg.message_id, text=f"出错: {str(e)}")
