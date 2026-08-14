import os
import base64
import html
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

# ============================================================
# 兼容新版 ddgs
# ============================================================

try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS


# ============================================================
# 1. Agnes API 配置
# ============================================================

AGNES_API_KEY = os.environ.get("AGNES_API_KEY")

AGNES_BASE_URL = "https://integrate.api.nvidia.com/v1"

MODEL_NAME = "z-ai/glm-5.2"


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
# 3. Telegram 消息长度
# ============================================================

MAX_TELEGRAM_LENGTH = 4000


# ============================================================
# 4. 获取机器人用户名
# ============================================================

async def get_bot_username(context):

    try:
        me = await context.bot.get_me()
        return me.username

    except Exception as e:

        print("[BOT] 获取机器人用户名失败：", repr(e))

        return None


# ============================================================
# 5. 获取消息文字
# ============================================================

def get_message_text(message):

    if not message:
        return ""

    return (
        message.text
        or message.caption
        or ""
    )


# ============================================================
# 6. 获取引用消息内容
# ============================================================

def get_quoted_message(message):

    """
    获取当前消息引用/回复的原始消息。

    支持：
    - 普通文字
    - 图片 caption
    - 用户名
    - 消息 ID
    """

    if not message:
        return None

    replied = message.reply_to_message

    if not replied:
        return None

    quoted_text = get_message_text(replied)

    quoted_user = replied.from_user

    if quoted_user:

        quoted_name = (
            quoted_user.first_name
            or quoted_user.username
            or "未知用户"
        )

        if quoted_user.username:
            quoted_name += f" (@{quoted_user.username})"

    else:

        quoted_name = "未知用户"


    return {
        "user": quoted_name,
        "text": quoted_text,
        "message_id": replied.message_id,
        "has_photo": bool(replied.photo),
        "has_document": bool(replied.document),
        "has_video": bool(replied.video),
    }


# ============================================================
# 7. 构造引用上下文
# ============================================================

def build_quote_context(message):

    quote = get_quoted_message(message)

    if not quote:
        return ""


    text = quote["text"].strip()

    if not text:

        if quote["has_photo"]:
            text = "[这是一条图片消息，图片本身未提供文字内容。]"

        elif quote["has_document"]:
            text = "[这是一条文件消息。]"

        elif quote["has_video"]:
            text = "[这是一条视频消息。]"

        else:
            text = "[该消息没有文字内容。]"


    result = (
        "\n\n"
        "【用户引用的消息】\n"
        "--------------------\n"
        f"发送者：{quote['user']}\n"
        f"消息内容：{text}\n"
        "--------------------\n"
        "请结合这条被引用的消息理解用户的问题。\n"
    )


    print("=" * 60)
    print("[QUOTE] 检测到引用消息")
    print(f"[QUOTE] 发送者：{quote['user']}")
    print(f"[QUOTE] 消息 ID：{quote['message_id']}")
    print(f"[QUOTE] 内容：{text}")
    print("=" * 60)


    return result


# ============================================================
# 8. 联网搜索
# ============================================================

def search_web(query: str) -> str:

    try:

        results = []

        with DDGS() as ddgs:

            for r in ddgs.text(
                query,
                max_results=5
            ):

                results.append(r)


        if not results:

            return "未找到相关联网信息。"


        output = []


        for r in results:

            title = r.get("title", "")
            body = r.get("body", "")
            href = r.get("href", "")

            output.append(
                f"- {title}\n"
                f"  {body}\n"
                f"  链接：{href}"
            )


        return "\n\n".join(output)


    except Exception as e:

        print("=" * 60)
        print("[SEARCH] 联网搜索失败")
        print(repr(e))
        print("=" * 60)

        return f"联网搜索失败：{e}"


# ============================================================
# 9. 调用 Agnes
# ============================================================

def ask_agnes(
    prompt: str,
    system_prompt: str = None
) -> str:

    messages = []


    if system_prompt:

        messages.append({
            "role": "system",
            "content": system_prompt
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


    return content.strip()


# ============================================================
# 10. AI 回复排版
# ============================================================

def format_ai_reply(text):

    """
    将 AI 常见 Markdown 排版转换成 Telegram HTML。

    支持：
    **加粗**
    *斜体*
    `代码`
    # 标题
    - 列表
    1. 列表
    """

    if not text:
        return "AI 没有返回内容。"


    text = text.strip()


    # --------------------------------------------------------
    # 防止 AI 自己输出 HTML
    # --------------------------------------------------------

    text = html.escape(text)


    # --------------------------------------------------------
    # 代码块
    # --------------------------------------------------------

    text = re.sub(
        r"```(?:\w+)?\n?(.*?)```",
        r"<pre>\1</pre>",
        text,
        flags=re.S
    )


    # --------------------------------------------------------
    # 行内代码
    # --------------------------------------------------------

    text = re.sub(
        r"`([^`\n]+)`",
        r"<code>\1</code>",
        text
    )


    # --------------------------------------------------------
    # Markdown 加粗
    # --------------------------------------------------------

    text = re.sub(
        r"\*\*(.+?)\*\*",
        r"<b>\1</b>",
        text
    )


    # --------------------------------------------------------
    # Markdown 标题
    # --------------------------------------------------------

    text = re.sub(
        r"(?m)^#{1,6}\s*(.+)$",
        r"<b>\1</b>",
        text
    )


    # --------------------------------------------------------
    # Markdown 斜体
    # --------------------------------------------------------

    text = re.sub(
        r"(?<!\*)\*([^*\n]+)\*(?!\*)",
        r"<i>\1</i>",
        text
    )


    # --------------------------------------------------------
    # 无序列表
    # --------------------------------------------------------

    text = re.sub(
        r"(?m)^[ \t]*[-*]\s+",
        "• ",
        text
    )


    # --------------------------------------------------------
    # 清理多余空行
    # --------------------------------------------------------

    text = re.sub(
        r"\n{3,}",
        "\n\n",
        text
    )


    # --------------------------------------------------------
    # Telegram 长度限制
    # --------------------------------------------------------

    if len(text) > MAX_TELEGRAM_LENGTH:

        text = (
            text[:3900]
            + "\n\n"
            + "……内容过长，已截断。"
        )


    return text


# ============================================================
# 11. 安全发送 AI 回复
# ============================================================

async def edit_ai_message(
    context,
    chat_id,
    message_id,
    text
):

    formatted = format_ai_reply(text)


    try:

        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=formatted,
            parse_mode="HTML",
            disable_web_page_preview=True
        )


    except Exception as e:

        print("=" * 60)
        print("[FORMAT] HTML 排版发送失败")
        print(repr(e))
        print("=" * 60)


        # HTML 出错时退回纯文本

        plain_text = re.sub(
            r"<[^>]+>",
            "",
            formatted
        )


        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=plain_text[:4000],
            disable_web_page_preview=True
        )


# ============================================================
# 12. 图片识别
# ============================================================

async def analyze_image(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    target_photo,
    user_prompt: str
):

    processing_msg = await update.message.reply_text(
        "🖼️ 正在分析图片……"
    )


    try:

        # ----------------------------------------------------
        # 下载图片
        # ----------------------------------------------------

        photo_file = await target_photo.get_file()

        image_bytes = await photo_file.download_as_bytearray()


        if not image_bytes:

            raise RuntimeError(
                "Telegram 图片下载失败。"
            )


        # ----------------------------------------------------
        # Base64
        # ----------------------------------------------------

        image_base64 = base64.b64encode(
            bytes(image_bytes)
        ).decode("utf-8")


        image_url = (
            "data:image/jpeg;base64,"
            + image_base64
        )


        # ----------------------------------------------------
        # 默认问题
        # ----------------------------------------------------

        if not user_prompt.strip():

            user_prompt = (
                "请详细分析这张图片。"
                "描述图片中的主要内容、人物、物体、环境，"
                "以及能够从图片中明确判断出的信息。"
                "不要凭空编造不存在的信息。"
            )


        # ----------------------------------------------------
        # 如果是回复一张图片
        # ----------------------------------------------------

        quote_context = build_quote_context(
            update.message
        )


        if quote_context:

            user_prompt = (
                quote_context
                + "\n"
                + "用户的问题：\n"
                + user_prompt
            )


        # ----------------------------------------------------
        # 多模态请求
        # ----------------------------------------------------

        response = client.chat.completions.create(

            model=MODEL_NAME,

            messages=[

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

            reply = "AI 没有返回图片分析结果。"

        else:

            reply = response.choices[0].message.content

            if not reply:

                reply = "AI 返回了空的图片分析结果。"


        await edit_ai_message(
            context,
            update.effective_chat.id,
            processing_msg.message_id,
            reply
        )


    except Exception as e:

        print("=" * 60)
        print("[IMAGE] 图片分析失败")
        print(repr(e))
        print("=" * 60)


        await context.bot.edit_message_text(

            chat_id=update.effective_chat.id,

            message_id=processing_msg.message_id,

            text=(
                "❌ 图片分析失败\n\n"
                f"{str(e)}"
            )
        )


# ============================================================
# 13. 普通消息处理
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


    # --------------------------------------------------------
    # 获取机器人用户名
    # --------------------------------------------------------

    bot_username = await get_bot_username(context)


    # --------------------------------------------------------
    # 获取当前消息文字
    # --------------------------------------------------------

    text = get_message_text(
        update.message
    )


    # --------------------------------------------------------
    # 获取引用内容
    # --------------------------------------------------------

    quote_context = build_quote_context(
        update.message
    )


    # --------------------------------------------------------
    # 私聊
    # --------------------------------------------------------

    is_private = (
        chat.type == ChatType.PRIVATE
    )


    # --------------------------------------------------------
    # @机器人
    # --------------------------------------------------------

    is_mentioned = False


    if bot_username and text:

        is_mentioned = (
            f"@{bot_username.lower()}"
            in text.lower()
        )


    # --------------------------------------------------------
    # 是否回复机器人
    # --------------------------------------------------------

    is_reply_to_bot = False


    if update.message.reply_to_message:

        replied_user = (
            update.message.reply_to_message.from_user
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
    # 是否回复任何消息
    # --------------------------------------------------------

    is_reply = (
        update.message.reply_to_message
        is not None
    )


    # ========================================================
    # A. 图片处理
    # ========================================================

    target_photo = None


    # 直接发送图片

    if update.message.photo:

        target_photo = (
            update.message.photo[-1]
        )


    # 回复图片

    elif (

        update.message.reply_to_message
        and update.message.reply_to_message.photo

    ):

        target_photo = (
            update.message.reply_to_message.photo[-1]
        )


    if target_photo:

        # ----------------------------------------------------
        # 群聊中：
        # @机器人 / 回复任何消息 / 直接回复图片
        # 都可以触发
        # ----------------------------------------------------

        allowed = (

            is_private
            or is_mentioned
            or is_reply
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
            user_prompt
        )


        return


    # ========================================================
    # B. 普通文字
    # ========================================================

    if not text.strip():
        return


    # --------------------------------------------------------
    # 记录群聊历史
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
    # 关键修改：
    #
    # 回复任何人的消息，都允许机器人回答
    #
    # 原来这里只允许 is_reply_to_bot
    # 现在改成 is_reply
    # --------------------------------------------------------

    if not (

        is_private
        or is_mentioned
        or is_reply

    ):

        return


    # --------------------------------------------------------
    # 去掉 @机器人
    # --------------------------------------------------------

    prompt = text


    if bot_username:

        prompt = prompt.replace(
            f"@{bot_username}",
            ""
        )


    prompt = prompt.strip()


    # --------------------------------------------------------
    # 如果用户只是回复了一条消息，
    # 没有输入问题
    # --------------------------------------------------------

    if not prompt:

        if quote_context:

            prompt = (
                "请分析一下我引用的这条消息。"
            )

        else:

            return


    # ========================================================
    # C. 联网查询
    # ========================================================

    processing_msg = await update.message.reply_text(
        "🔎 正在思考并查询相关信息……"
    )


    try:

        search_results = search_web(
            prompt
        )


        # ----------------------------------------------------
        # 系统提示词
        # ----------------------------------------------------

        system_prompt = (

            "你是一个智能 Telegram AI 助手。\n\n"

            "你的回答会直接发送到 Telegram 群聊。\n\n"

            "请严格遵守以下排版要求：\n\n"

            "1. 使用自然、清晰的中文。\n"

            "2. 不要输出 HTML 标签。\n"

            "3. 可以使用 Markdown，例如 **加粗**。\n"

            "4. 重要结论可以加粗。\n"

            "5. 使用 emoji 作为小标题，例如：\n"
            "💡 核心观点\n"
            "📌 具体原因\n"
            "🔍 进一步分析\n\n"

            "6. 不要把所有内容挤成一大段。\n"

            "7. 每个主要观点之间留一个空行。\n"

            "8. 列表使用 - 或 1. 2. 3.。\n"

            "9. 如果问题比较简单，直接回答，不要故意写得很长。\n"

            "10. 如果用户是在询问被引用的消息，"
            "必须结合【用户引用的消息】回答。\n\n"

            "11. 如果引用内容与用户的问题有关，"
            "不要让用户重新复制引用内容。\n\n"

            "12. 如果联网搜索结果不足，"
            "明确告诉用户，不要编造。\n\n"

            "联网搜索结果：\n"
            "--------------------\n"
            f"{search_results}\n"
            "--------------------\n"

        )


        # ----------------------------------------------------
        # 最终 Prompt
        # ----------------------------------------------------

        final_prompt = ""


        if quote_context:

            final_prompt += quote_context


        final_prompt += (

            "\n【用户当前问题】\n"
            "--------------------\n"
            f"{prompt}\n"
            "--------------------"

        )


        print("=" * 60)
        print("[AI] 收到用户问题")
        print(f"[AI] 用户：{user_name}")
        print(f"[AI] 问题：{prompt}")

        if quote_context:

            print("[AI] 本次问题包含引用消息")

        print("=" * 60)


        # ----------------------------------------------------
        # 调用 AI
        # ----------------------------------------------------

        reply = ask_agnes(

            final_prompt,

            system_prompt

        )


        # ----------------------------------------------------
        # Telegram 排版
        # ----------------------------------------------------

        await edit_ai_message(

            context,

            chat_id,

            processing_msg.message_id,

            reply

        )


    except Exception as e:

        print("=" * 60)
        print("[AI] 请求失败")
        print(repr(e))
        print("=" * 60)


        await context.bot.edit_message_text(

            chat_id=chat_id,

            message_id=processing_msg.message_id,

            text=(
                "❌ 请求失败\n\n"
                f"{str(e)}"
            )

        )


# ============================================================
# 14. /summary 群聊总结
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
            "📝 目前记录太少，至少需要 3 条消息才能进行总结。"
        )

        return


    status_msg = await update.message.reply_text(
        "📝 正在生成群聊总结……"
    )


    # --------------------------------------------------------
    # 创建消息链接
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
    # 格式化历史
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


    # --------------------------------------------------------
    # 总结 Prompt
    # --------------------------------------------------------

    system_prompt = (

        "你是一个群聊总结助手。\n\n"

        "请根据聊天记录总结最近的讨论内容。\n\n"

        "要求：\n"

        "1. 找出 3-5 个主要话题。\n"

        "2. 每个话题简洁说明。\n"

        "3. 不要编造聊天记录中不存在的内容。\n"

        "4. 使用自然中文。\n"

        "5. 使用 Markdown 排版。\n"

        "6. 重要内容可以使用 **加粗**。\n"

        "7. 使用 emoji 小标题。\n"

        "8. 不要使用 HTML。\n\n"

        "推荐格式：\n\n"

        "📝 **群聊 AI 总结**\n\n"

        "📌 **话题一**\n"
        "简要说明……\n\n"

        "📌 **话题二**\n"
        "简要说明……\n\n"

        "💡 **总体结论**\n"
        "……"

    )


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
                        "以下是聊天记录：\n\n"
                        + formatted_history
                    )
                }

            ]

        )


        if not response.choices:

            raise RuntimeError(
                "AI 没有返回总结。"
            )


        result = response.choices[0].message.content


        if not result:

            raise RuntimeError(
                "AI 返回了空总结。"
            )


        # ----------------------------------------------------
        # 添加消息链接
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
                f"{index}. {msg_link}"
            )


        final_text = (

            result

            + "\n\n"

            + "🔗 **相关消息**\n"

            + "\n".join(links)

        )


        await edit_ai_message(

            context,

            chat_id,

            status_msg.message_id,

            final_text

        )


    except Exception as e:

        print("=" * 60)
        print("[SUMMARY] 群聊总结失败")
        print(repr(e))
        print("=" * 60)


        await context.bot.edit_message_text(

            chat_id=chat_id,

            message_id=status_msg.message_id,

            text=(
                "❌ 群聊总结失败\n\n"
                f"{str(e)}"
            )

        )


# ============================================================
# 15. 注册 Handler
# ============================================================

def register_handlers(
    application: Application
):

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
    # 普通消息 / 图片 / 回复
    # --------------------------------------------------------

    application.add_handler(

        MessageHandler(
            filters.ALL,
            handle_message
        )

    )


    print("[HANDLER] Telegram handlers 注册完成")
