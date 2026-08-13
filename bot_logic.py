import os
from collections import defaultdict
from html import escape

from telegram import Update
from telegram.ext import ContextTypes

from openai import OpenAI
from ddgs import DDGS


# ============================================================
# 1. API 配置
# ============================================================

AGNES_API_KEY = os.environ.get("AGNES_API_KEY")

AGNES_BASE_URL = "https://apihub.agnes-ai.com/v1"

MODEL_NAME = "agnes-2.0-flash"


if not AGNES_API_KEY:
    print("警告：未检测到 AGNES_API_KEY")


# ============================================================
# 2. OpenAI 兼容客户端
# ============================================================

client = OpenAI(
    api_key=AGNES_API_KEY,
    base_url=AGNES_BASE_URL
)


# ============================================================
# 3. 群聊历史记录
# ============================================================

group_history = defaultdict(list)

MAX_HISTORY = 100


# ============================================================
# 4. /start
# ============================================================

async def handle_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not update.message:
        return

    await update.message.reply_text(
        "你好！我是 Agnes AI 🤖\n\n"
        "你可以直接和我聊天。\n"
        "在群聊中 @我 即可提问。\n\n"
        "可用命令：\n"
        "/start - 查看帮助\n"
        "/summary - 总结当前群聊"
    )


# ============================================================
# 5. DuckDuckGo 联网搜索
# ============================================================

def search_web(query: str) -> str:
    try:
        with DDGS() as ddgs:

            results = list(
                ddgs.text(
                    query,
                    max_results=3
                )
            )

            if not results:
                return "未找到相关联网信息。"

            search_summary = []

            for result in results:

                title = result.get(
                    "title",
                    "无标题"
                )

                body = result.get(
                    "body",
                    ""
                )

                href = result.get(
                    "href",
                    ""
                )

                search_summary.append(
                    f"- {title}: {body} ({href})"
                )

            return "\n".join(search_summary)

    except Exception as e:

        print(f"联网搜索错误: {e}")

        return f"搜索出错：{str(e)}"


# ============================================================
# 6. 普通消息 + 图片消息
# ============================================================

async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    # --------------------------------------------------------
    # 基础信息
    # --------------------------------------------------------

    chat = update.effective_chat

    if not chat:
        return

    chat_id = chat.id

    user = update.effective_user

    if user:
        user_name = user.first_name or "Anonymous"
    else:
        user_name = "Anonymous"

    message_id = update.message.message_id

    text = (
        update.message.text
        or update.message.caption
        or ""
    )

    bot_username = context.bot.username

    is_private = chat.type == "private"

    # --------------------------------------------------------
    # 判断是否 @机器人
    # --------------------------------------------------------

    is_mentioned = False

    if bot_username:

        if f"@{bot_username.lower()}" in text.lower():
            is_mentioned = True

        elif (
            update.message.reply_to_message
            and update.message.reply_to_message.from_user
            and update.message.reply_to_message.from_user.username
            and update.message.reply_to_message.from_user.username.lower()
            == bot_username.lower()
        ):
            is_mentioned = True

    # ========================================================
    # 7. 图片处理
    # ========================================================

    target_photo = None

    # 直接发送图片
    if update.message.photo:

        target_photo = update.message.photo[-1]

    # 回复别人的图片
    elif (
        update.message.reply_to_message
        and update.message.reply_to_message.photo
    ):

        target_photo = (
            update.message.reply_to_message.photo[-1]
        )

        # 回复图片时只使用当前消息文字
        text = update.message.text or ""

    # --------------------------------------------------------
    # 如果检测到图片
    # --------------------------------------------------------

    if target_photo:

        # 群聊里必须 @机器人或者回复机器人
        if not (is_private or is_mentioned):
            return

        processing_msg = await update.message.reply_text(
            "正在分析图片，请稍等……"
        )

        try:

            # 获取 Telegram 图片文件
            photo_file = await target_photo.get_file()

            image_url = (
                "https://api.telegram.org/file/bot"
                f"{context.bot.token}/"
                f"{photo_file.file_path}"
            )

            # 去掉 @机器人
            user_prompt = text

            if bot_username:

                user_prompt = user_prompt.replace(
                    f"@{bot_username}",
                    ""
                ).strip()

            if not user_prompt:

                user_prompt = (
                    "请详细分析这张图片，包括图片中的主要内容、"
                    "文字、人物、物体、场景以及值得注意的细节。"
                )

            # ------------------------------------------------
            # 调用 Agnes 多模态模型
            # ------------------------------------------------

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

            reply = (
                response.choices[0]
                .message
                .content
            )

            if not reply:
                reply = "模型没有返回有效内容。"

            # 普通回复不使用 HTML
            await context.bot.edit_message_text(

                chat_id=chat_id,

                message_id=processing_msg.message_id,

                text=reply
            )

        except Exception as e:

            print(f"图片分析错误: {e}")

            await context.bot.edit_message_text(

                chat_id=chat_id,

                message_id=processing_msg.message_id,

                text=f"图片分析出错：{str(e)}"
            )

        return

    # ========================================================
    # 8. 普通文本消息记录到群聊历史
    # ========================================================

    if text and not text.startswith("/"):

        group_history[chat_id].append({

            "user": user_name,

            "text": text,

            "message_id": message_id

        })

        # 限制历史消息数量
        if len(group_history[chat_id]) > MAX_HISTORY:

            group_history[chat_id].pop(0)

    # ========================================================
    # 9. 判断是否需要回复
    # ========================================================

    if not (is_private or is_mentioned):
        return

    # --------------------------------------------------------
    # 清理 @机器人
    # --------------------------------------------------------

    prompt = text

    if bot_username:

        prompt = prompt.replace(
            f"@{bot_username}",
            ""
        ).strip()

    if not prompt:
        return

    # ========================================================
    # 10. 发送处理中提示
    # ========================================================

    processing_msg = await update.message.reply_text(
        "正在联网查询并思考中……"
    )

    try:

        # ----------------------------------------------------
        # 联网搜索
        # ----------------------------------------------------

        search_results = search_web(prompt)

        # ----------------------------------------------------
        # AI System Prompt
        # ----------------------------------------------------

        system_prompt = (
            "你是 Agnes，一个聪明、准确、自然的 AI 助手。\n\n"

            "用户提出的问题可能需要实时信息。"
            "下面是通过搜索引擎获取的参考资料。\n\n"

            "请根据搜索结果回答用户，并注意：\n"
            "1. 不要编造搜索结果中不存在的信息。\n"
            "2. 如果搜索结果不足，请明确告诉用户。\n"
            "3. 回答要自然、清晰、有帮助。\n"
            "4. 如果用户的问题不需要实时信息，也可以结合自身知识回答。\n\n"

            "实时搜索结果：\n"
            f"{search_results}"
        )

        # ====================================================
        # 11. 调用 Agnes API
        # ====================================================

        response = client.chat.completions.create(

            model=MODEL_NAME,

            messages=[

                {
                    "role": "system",
                    "content": system_prompt
                },

                {
                    "role": "user",
                    "content": prompt
                }

            ]
        )

        reply = (
            response.choices[0]
            .message
            .content
        )

        if not reply:
            reply = "模型没有返回有效内容。"

        # ----------------------------------------------------
        # 返回 Telegram
        # ----------------------------------------------------

        # 这里故意不使用 parse_mode="HTML"
        # 防止 AI 输出 < > 等字符导致 Telegram 报错
        await context.bot.edit_message_text(

            chat_id=chat_id,

            message_id=processing_msg.message_id,

            text=reply
        )

    except Exception as e:

        print(f"AI 请求错误: {e}")

        await context.bot.edit_message_text(

            chat_id=chat_id,

            message_id=processing_msg.message_id,

            text=f"请求失败：{str(e)}"
        )


# ============================================================
# 12. /summary 群聊总结
# ============================================================

async def handle_summary(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    chat = update.effective_chat

    if not chat:
        return

    chat_id = chat.id

    history = group_history.get(
        chat_id,
        []
    )

    # --------------------------------------------------------
    # 消息太少
    # --------------------------------------------------------

    if len(history) < 3:

        await update.message.reply_text(
            "目前记录的群聊消息太少，至少需要 3 条消息才能进行总结。"
        )

        return

    # --------------------------------------------------------
    # 提示用户正在总结
    # --------------------------------------------------------

    status_msg = await update.message.reply_text(
        "正在生成群聊总结……"
    )

    # ========================================================
    # 13. 创建消息链接
    # ========================================================

    if chat.username:

        chat_link_prefix = (
            f"https://t.me/{chat.username}"
        )

    else:

        cid = (
            str(chat_id)
            .replace("-100", "")
            .replace("-", "")
        )

        chat_link_prefix = (
            f"https://t.me/c/{cid}"
        )

    # ========================================================
    # 14. 整理历史消息
    # ========================================================

    formatted_lines = []

    for item in history:

        msg_link = (
            f"{chat_link_prefix}/{item['message_id']}"
        )

        username = escape(
            str(item["user"])
        )

        message_text = escape(
            str(item["text"])
        )

        formatted_lines.append(

            f"• <a href=\"{msg_link}\">"
            f"{username}"
            f"</a>: "
            f"{message_text}"

        )

    formatted_history = "\n".join(
        formatted_lines
    )

    msg_count = len(history)

    # ========================================================
    # 15. 总结 Prompt
    # ========================================================

    system_prompt = (

        "你是一个群聊总结助手。\n\n"

        "请根据下面的群聊记录，生成简洁、准确的群聊总结。\n\n"

        "要求：\n"

        "1. 总结 3-5 个主要话题。\n"

        "2. 每个话题都需要有简短描述。\n"

        "3. 如果能确定相关消息，请使用对应的消息跳转链接。\n"

        "4. 必须使用 Telegram 支持的 HTML 格式。\n"

        "5. 不要使用 Markdown。\n\n"

        "输出格式：\n"

        "<b>📝 群聊 AI 总结</b>\n"
        f"💬 已分析 {msg_count} 条消息\n\n"

        "<b>1. <a href=\"消息链接\">话题名称</a></b>\n"
        "话题内容简短描述。\n\n"

        "<b>2. <a href=\"消息链接\">话题名称</a></b>\n"
        "话题内容简短描述。\n\n"

        "最后添加：\n"
        "<i>点击蓝色标题可跳转。</i>\n\n"

        "不要输出任何 Markdown 符号。"

    )

    # ========================================================
    # 16. 调用 AI
    # ========================================================

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
                        "以下是群聊记录：\n\n"
                        f"{formatted_history}"
                    )
                }

            ]
        )

        reply = (
            response.choices[0]
            .message
            .content
        )

        if not reply:
            reply = (
                "<b>📝 群聊 AI 总结</b>\n\n"
                "模型没有返回有效总结。"
            )

        # ----------------------------------------------------
        # Telegram HTML
        # ----------------------------------------------------

        await context.bot.edit_message_text(

            chat_id=chat_id,

            message_id=status_msg.message_id,

            text=reply,

            parse_mode="HTML",

            disable_web_page_preview=True
        )

    except Exception as e:

        print(f"群聊总结错误: {e}")

        await context.bot.edit_message_text(

            chat_id=chat_id,

            message_id=status_msg.message_id,

            text=f"总结失败：{str(e)}"
        )
