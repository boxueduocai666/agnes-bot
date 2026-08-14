import os
import base64
import re
from collections import defaultdict

from telegram import Update
from telegram.constants import ChatType
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from openai import OpenAI
from ddgs import DDGS


# ============================================================
# 1. Agnes API
# ============================================================

AGNES_API_KEY = os.environ.get("AGNES_API_KEY")
AGNES_BASE_URL = "https://apihub.agnes-ai.com/v1"
MODEL_NAME = "agnes-2.0-flash"

if not AGNES_API_KEY:
    raise RuntimeError(
        "未检测到 AGNES_API_KEY，请在 Render → Environment 中配置。"
    )

client = OpenAI(
    api_key=AGNES_API_KEY,
    base_url=AGNES_BASE_URL
)


# ============================================================
# 2. 群聊历史
# ============================================================

group_history = defaultdict(list)

MAX_HISTORY = 100


# ============================================================
# 3. Telegram 消息长度处理
# ============================================================

MAX_TELEGRAM_LENGTH = 4000


def split_long_text(text: str, max_length=MAX_TELEGRAM_LENGTH):

    if not text:
        return [""]

    if len(text) <= max_length:
        return [text]

    parts = []

    remaining = text

    while len(remaining) > max_length:

        cut = remaining.rfind(
            "\n",
            0,
            max_length
        )

        if cut < max_length * 0.5:

            cut = remaining.rfind(
                "。",
                0,
                max_length
            )

        if cut < max_length * 0.5:

            cut = max_length

        part = remaining[:cut].strip()

        if part:
            parts.append(part)

        remaining = remaining[cut:].strip()

    if remaining:
        parts.append(remaining)

    return parts


# ============================================================
# 4. 清理 AI 输出
# ============================================================

def clean_ai_text(text: str) -> str:

    if not text:
        return ""

    text = text.strip()

    # 去除可能出现的 HTML
    text = text.replace("<br>", "\n")
    text = text.replace("<br/>", "\n")
    text = text.replace("<br />", "\n")

    # 防止 AI 自己套一层奇怪的 Markdown
    text = re.sub(
        r"^```(?:markdown|text)?\s*",
        "",
        text,
        flags=re.IGNORECASE
    )

    if text.endswith("```"):
        text = text[:-3]

    return text.strip()


# ============================================================
# 5. 联网搜索
# ============================================================

def search_web(query: str) -> str:

    try:

        print(
            f"[SEARCH] 开始搜索：{query}",
            flush=True
        )

        results = []

        with DDGS() as ddgs:

            for result in ddgs.text(
                query,
                max_results=5
            ):

                results.append(result)

        if not results:

            print(
                "[SEARCH] 没有搜索结果",
                flush=True
            )

            return "未找到相关联网信息。"

        output = []

        for result in results:

            title = result.get(
                "title",
                ""
            )

            body = result.get(
                "body",
                ""
            )

            href = result.get(
                "href",
                ""
            )

            output.append(
                f"标题：{title}\n"
                f"摘要：{body}\n"
                f"链接：{href}"
            )

        print(
            f"[SEARCH] 完成，共 {len(results)} 条",
            flush=True
        )

        return "\n\n".join(output)

    except Exception as e:

        print(
            "[SEARCH] ❌ 搜索失败：",
            repr(e),
            flush=True
        )

        return f"联网搜索失败：{e}"


# ============================================================
# 6. Agnes 文本请求
# ============================================================

def ask_agnes(
    prompt: str,
    system_prompt: str = None,
    history=None
) -> str:

    messages = []

    if system_prompt:

        messages.append({
            "role": "system",
            "content": system_prompt
        })

    if history:

        for item in history:

            messages.append({
                "role": item["role"],
                "content": item["content"]
            })

    messages.append({
        "role": "user",
        "content": prompt
    })

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=messages
    )

    if not response.choices:
        return "AI 没有返回有效结果。"

    content = response.choices[0].message.content

    if not content:
        return "AI 返回了空内容。"

    return clean_ai_text(content)


# ============================================================
# 7. 获取机器人用户名
# ============================================================

async def get_bot_username(context):

    try:

        me = await context.bot.get_me()

        return me.username

    except Exception as e:

        print(
            "[BOT] 获取用户名失败：",
            repr(e),
            flush=True
        )

        return None


# ============================================================
# 8. 获取消息文字
# ============================================================

def get_message_text(message) -> str:

    if not message:
        return ""

    return (
        message.text
        or message.caption
        or ""
    )


# ============================================================
# 9. 获取被回复消息
# ============================================================

def get_replied_content(message) -> str:

    if not message:
        return ""

    replied = message.reply_to_message

    if not replied:
        return ""

    replied_text = get_message_text(
        replied
    )

    sender = replied.from_user

    if sender:

        sender_name = (
            sender.first_name
            or sender.username
            or "未知用户"
        )

    else:

        sender_name = "未知用户"

    if replied_text:

        if len(replied_text) > 6000:

            replied_text = (
                replied_text[:6000]
                + "\n……引用内容过长，已截断。"
            )

        return (
            "【被回复消息】\n"
            f"发送者：{sender_name}\n"
            f"内容：\n{replied_text}"
        )

    if replied.photo:

        return (
            "【被回复消息】\n"
            f"发送者：{sender_name}\n"
            "内容：这是一张图片，没有文字。"
        )

    return ""


# ============================================================
# 10. 图片分析
# ============================================================

async def analyze_image(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    target_photo,
    user_prompt: str,
    replied_context: str = ""
):

    processing_msg = await update.message.reply_text(
        "🖼️ 正在分析图片…"
    )

    try:

        print(
            "[IMAGE] 开始下载图片",
            flush=True
        )

        photo_file = await target_photo.get_file()

        image_bytes = await photo_file.download_as_bytearray()

        if not image_bytes:

            raise RuntimeError(
                "图片下载失败。"
            )

        image_base64 = base64.b64encode(
            bytes(image_bytes)
        ).decode("utf-8")

        image_url = (
            "data:image/jpeg;base64,"
            + image_base64
        )

        if not user_prompt.strip():

            user_prompt = (
                "请分析这张图片，并用清晰、自然的中文回答。"
                "描述重要内容即可，不要编造图片中不存在的信息。"
            )

        if replied_context:

            user_prompt = (
                replied_context
                + "\n\n"
                + "【用户的问题】\n"
                + user_prompt
            )

        system_prompt = """
你是一个 Telegram 图片分析助手。

请用自然、清晰、简洁的中文回答。

排版要求：
1. 第一行可以使用一个合适的 emoji 标题。
2. 内容分成 2-5 个自然段。
3. 重要内容可以使用 **加粗**。
4. 多项内容使用 • 项目符号。
5. 不要使用 HTML。
6. 不要把回答写成一整堵文字。
7. 不要编造图片中看不到的信息。
8. 如果无法确定，请明确说明。
"""

        response = client.chat.completions.create(

            model=MODEL_NAME,

            messages=[

                {
                    "role": "system",
                    "content": system_prompt
                },

                {
                    "role": "user",

                    "content": [

                        {
                            "type": "text",
                            "text": user_prompt
                        },

                        {
                            "type": "image_url",

                            "image_url": {
                                "url": image_url
                            }
                        }

                    ]
                }

            ]
        )

        if not response.choices:

            reply = "❌ AI 没有返回图片分析结果。"

        else:

            reply = (
                response.choices[0]
                .message
                .content
                or "❌ AI 返回了空结果。"
            )

        reply = clean_ai_text(reply)

        parts = split_long_text(reply)

        await context.bot.delete_message(
            chat_id=update.effective_chat.id,
            message_id=processing_msg.message_id
        )

        for part in parts:

            await update.message.reply_text(
                part,
                parse_mode="Markdown"
            )

        print(
            "[IMAGE] ✅ 图片分析完成",
            flush=True
        )

    except Exception as e:

        print(
            "[IMAGE] ❌ 图片分析失败：",
            repr(e),
            flush=True
        )

        try:

            await context.bot.edit_message_text(

                chat_id=update.effective_chat.id,

                message_id=processing_msg.message_id,

                text=(
                    "❌ 图片分析失败\n\n"
                    f"{str(e)}"
                )
            )

        except Exception:

            pass


# ============================================================
# 11. AI 排版规则
# ============================================================

AI_SYSTEM_PROMPT = """
你是一个高质量的 Telegram AI 助手。

你的回答会直接发送到 Telegram。

【排版规则，非常重要】

请让回答具有良好的阅读体验，不要输出一整堵文字。

规则：

1. 开头可以使用一个合适的 emoji + 简短标题。
例如：
🤖 关于这个问题

2. 正文必须分段。
每个段落之间空一行。

3. 重要结论使用：
**加粗**

4. 多个并列内容使用：
• 第一项
• 第二项
• 第三项

5. 如果需要步骤，使用：
1. 第一步
2. 第二步
3. 第三步

6. 如果有“结论”，可以使用：
💡 **结论**
然后单独写结论。

7. 如果有提醒，可以使用：
⚠️ **注意**

8. 如果有代码：
使用标准 Markdown 代码块。

9. 不要使用 HTML 标签。

10. 不要使用表格。
Telegram 手机上表格通常很难阅读。

11. 不要在回答开头写：
“当然可以，以下是……”
除非确实需要。

12. 不要重复用户的问题。

13. 如果用户只是简单问一句话，就不要强行写成超长文章。

14. 根据问题复杂程度决定回答长度。

15. 最重要的是：
内容自然、清晰、像一个真正好用的 Telegram AI 助手。
"""


# ============================================================
# 12. 普通消息
# ============================================================

async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    chat = update.effective_chat
    user = update.effective_user

    if not user:
        return

    chat_id = chat.id

    user_name = (
        user.first_name
        or user.username
        or "Anonymous"
    )

    bot_username = await get_bot_username(
        context
    )

    text = get_message_text(
        update.message
    )

    is_private = (
        chat.type == ChatType.PRIVATE
    )

    is_mentioned = False

    if bot_username and text:

        is_mentioned = (
            f"@{bot_username.lower()}"
            in text.lower()
        )

    is_reply_to_bot = False

    if update.message.reply_to_message:

        replied_user = (
            update.message
            .reply_to_message
            .from_user
        )

        if replied_user:

            if (
                replied_user.username
                and bot_username
                and replied_user.username.lower()
                == bot_username.lower()
            ):

                is_reply_to_bot = True

    # --------------------------------------------------------
    # 被回复内容
    # --------------------------------------------------------

    replied_context = get_replied_content(
        update.message
    )

    if replied_context:

        print(
            "[REPLY] 检测到引用/回复内容",
            flush=True
        )

    # ========================================================
    # 图片
    # ========================================================

    target_photo = None

    if update.message.photo:

        target_photo = (
            update.message.photo[-1]
        )

    elif (
        update.message.reply_to_message
        and update.message.reply_to_message.photo
    ):

        target_photo = (
            update.message
            .reply_to_message
            .photo[-1]
        )

    if target_photo:

        allowed = (
            is_private
            or is_mentioned
            or is_reply_to_bot
            or update.message.reply_to_message is not None
        )

        if not allowed:
            return

        user_prompt = text

        if bot_username:

            user_prompt = user_prompt.replace(
                f"@{bot_username}",
                ""
            )

        user_prompt = user_prompt.strip()

        await analyze_image(

            update,
            context,
            target_photo,
            user_prompt,
            replied_context
        )

        return

    # ========================================================
    # 普通文字
    # ========================================================

    if not text.strip():
        return

    # --------------------------------------------------------
    # 群聊历史
    # --------------------------------------------------------

    if chat.type in (
        ChatType.GROUP,
        ChatType.SUPERGROUP
    ):

        if not text.startswith("/"):

            group_history[chat_id].append({

                "user": user_name,

                "text": text,

                "message_id":
                    update.message.message_id

            })

            if len(group_history[chat_id]) > MAX_HISTORY:

                group_history[chat_id].pop(0)

    # --------------------------------------------------------
    # 是否回答
    # --------------------------------------------------------

    if not (
        is_private
        or is_mentioned
        or is_reply_to_bot
    ):

        return

    # --------------------------------------------------------
    # 清理 @机器人
    # --------------------------------------------------------

    prompt = text

    if bot_username:

        prompt = prompt.replace(
            f"@{bot_username}",
            ""
        )

    prompt = prompt.strip()

    if not prompt:
        return

    # ========================================================
    # 构造问题
    # ========================================================

    if replied_context:

        final_prompt = (
            replied_context
            + "\n\n"
            + "【用户当前问题】\n"
            + prompt
        )

    else:

        final_prompt = prompt

    # ========================================================
    # 联网搜索
    # ========================================================

    processing_msg = await update.message.reply_text(
        "🔎 正在思考并查询资料…"
    )

    try:

        search_results = search_web(
            prompt
        )

        # ----------------------------------------------------
        # 最近聊天上下文
        # ----------------------------------------------------

        recent_history = []

        if chat_id in group_history:

            recent_messages = (
                group_history[chat_id][-10:]
            )

            for item in recent_messages:

                recent_history.append({

                    "role": "user",

                    "content": (
                        f"{item['user']}: "
                        f"{item['text']}"
                    )
                })

        # ----------------------------------------------------
        # 系统提示
        # ----------------------------------------------------

        system_prompt = (
            AI_SYSTEM_PROMPT
            + "\n\n"
            + "你还需要遵守以下规则：\n"
            + "• 如果存在【被回复消息】，"
              "它就是用户当前问题的重要上下文。\n"
            + "• 如果用户是在追问上一条消息，"
              "请直接理解上下文，不要让用户重复粘贴。\n"
            + "• 联网搜索结果只能作为参考。\n"
            + "• 搜索结果不足时要明确说明。\n\n"
            + "【联网搜索结果】\n"
            + "--------------------\n"
            + search_results
            + "\n--------------------"
        )

        print(
            "[AI] 正在请求 Agnes...",
            flush=True
        )

        reply = ask_agnes(

            final_prompt,

            system_prompt,

            recent_history
        )

        reply = clean_ai_text(
            reply
        )

        parts = split_long_text(
            reply
        )

        # 删除“正在思考”
        try:

            await context.bot.delete_message(

                chat_id=chat_id,

                message_id=processing_msg.message_id
            )

        except Exception:

            pass

        # ----------------------------------------------------
        # 发送最终回答
        # ----------------------------------------------------

        for index, part in enumerate(parts):

            try:

                await update.message.reply_text(
                    part,
                    parse_mode="Markdown"
                )

            except Exception as markdown_error:

                print(
                    "[FORMAT] Markdown 解析失败，"
                    "自动切换纯文本：",
                    repr(markdown_error),
                    flush=True
                )

                await update.message.reply_text(
                    part
                )

        print(
            "[AI] ✅ 回复完成",
            flush=True
        )

    except Exception as e:

        print("=" * 60, flush=True)

        print(
            "[AI] ❌ 请求失败：",
            repr(e),
            flush=True
        )

        print("=" * 60, flush=True)

        try:

            await context.bot.edit_message_text(

                chat_id=chat_id,

                message_id=processing_msg.message_id,

                text=(
                    "❌ 请求失败\n\n"
                    f"{str(e)}"
                )
            )

        except Exception:

            pass


# ============================================================
# 13. /summary
# ============================================================

async def handle_summary(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    chat = update.effective_chat

    chat_id = chat.id

    history = group_history.get(
        chat_id,
        []
    )

    if len(history) < 3:

        await update.message.reply_text(
            "📝 目前记录太少，至少需要 3 条消息才能生成总结。"
        )

        return

    status_msg = await update.message.reply_text(
        "📝 正在整理群聊内容…"
    )

    # --------------------------------------------------------
    # 群链接
    # --------------------------------------------------------

    if chat.username:

        chat_link_prefix = (
            f"https://t.me/{chat.username}"
        )

    else:

        cid = str(chat_id)

        if cid.startswith("-100"):

            cid = cid[4:]

        else:

            cid = cid.replace("-", "")

        chat_link_prefix = (
            f"https://t.me/c/{cid}"
        )

    # --------------------------------------------------------
    # 历史
    # --------------------------------------------------------

    formatted_lines = []

    for index, item in enumerate(
        history,
        start=1
    ):

        msg_link = (
            f"{chat_link_prefix}/{item['message_id']}"
        )

        formatted_lines.append(

            f"[消息 {index}]\n"
            f"用户：{item['user']}\n"
            f"内容：{item['text']}\n"
            f"链接：{msg_link}"

        )

    formatted_history = "\n\n".join(
        formatted_lines
    )

    system_prompt = """
你是 Telegram 群聊总结助手。

请根据聊天记录制作一个简洁、漂亮、容易阅读的总结。

排版严格遵循：

📝 **群聊 AI 总结**

💬 **本次分析**
分析最近的主要讨论。

🔥 **主要话题**

1. **话题名称**
简要说明这个话题讨论了什么。

2. **话题名称**
简要说明。

3. **话题名称**
简要说明。

💡 **总结**
用一两句话概括整个聊天。

要求：

• 不要编造聊天记录。
• 最多总结 5 个话题。
• 没有意义的闲聊可以忽略。
• 不要输出 HTML。
• 不要使用表格。
• 使用自然中文。
• 不要把每一条消息都重复一遍。
"""

    try:

        response = client.chat.completions.create(

            model=MODEL_NAME,

            messages=[

                {
                    "role": "system",
                    "content": system_prompt
                },

                {
                    "role": "user",
                    "content": (
                        "聊天记录如下：\n\n"
                        + formatted_history
                    )
                }

            ]
        )

        if not response.choices:

            raise RuntimeError(
                "AI 没有返回总结。"
            )

        result = (
            response.choices[0]
            .message
            .content
            or ""
        )

        result = clean_ai_text(
            result
        )

        # ----------------------------------------------------
        # 消息链接
        # ----------------------------------------------------

        links = []

        for index, item in enumerate(
            history,
            start=1
        ):

            msg_link = (
                f"{chat_link_prefix}/{item['message_id']}"
            )

            links.append(
                f"• 消息 {index}：{msg_link}"
            )

        final_text = (
            result
            + "\n\n"
            + "🔗 **相关消息**\n"
            + "\n".join(links)
        )

        parts = split_long_text(
            final_text
        )

        try:

            await context.bot.delete_message(

                chat_id=chat_id,

                message_id=status_msg.message_id
            )

        except Exception:

            pass

        for part in parts:

            try:

                await update.message.reply_text(
                    part,
                    parse_mode="Markdown"
                )

            except Exception:

                await update.message.reply_text(
                    part
                )

    except Exception as e:

        print(
            "[SUMMARY] ❌ 总结失败：",
            repr(e),
            flush=True
        )

        try:

            await context.bot.edit_message_text(

                chat_id=chat_id,

                message_id=status_msg.message_id,

                text=(
                    "❌ 群聊总结失败\n\n"
                    f"{str(e)}"
                )
            )

        except Exception:

            pass


# ============================================================
# 14. 注册 Handler
# ============================================================

def register_handlers(
    application: Application
):

    application.add_handler(
        CommandHandler(
            "summary",
            handle_summary
        )
    )

    application.add_handler(

        MessageHandler(
            filters.ALL,
            handle_message
        )
    )

    print(
        "[HANDLER] Telegram handlers 注册完成",
        flush=True
    )
