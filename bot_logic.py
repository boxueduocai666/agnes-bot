import os
import base64
from collections import defaultdict

from telegram import Update
from telegram.ext import ContextTypes

from openai import OpenAI
from ddgs import DDGS


# ============================================================
# 1. Agnes AI 配置
# ============================================================

AGNES_API_KEY = os.environ.get("AGNES_API_KEY")

AGNES_BASE_URL = "https://apihub.agnes-ai.com/v1"

MODEL_NAME = "agnes-2.0-flash"


if not AGNES_API_KEY:
    raise RuntimeError(
        "未检测到 AGNES_API_KEY，请在 Render 的 Environment Variables 中配置。"
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
# 3. 网页搜索
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

        search_summary = "\n".join(
            [
                f"- {r.get('title', '')}: "
                f"{r.get('body', '')} "
                f"({r.get('href', '')})"
                for r in results
            ]
        )

        return search_summary

    except Exception as e:

        return f"搜索出错：{str(e)}"


# ============================================================
# 4. 普通消息 + 图片消息处理
# ============================================================

async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    # --------------------------------------------------------
    # 基础检查
    # --------------------------------------------------------

    if not update.message:
        return

    chat = update.effective_chat

    if not chat:
        return

    chat_id = chat.id

    user = update.effective_user

    user_name = (
        user.first_name
        if user and user.first_name
        else "Anonymous"
    )

    text = (
        update.message.text
        or update.message.caption
        or ""
    )

    message_id = update.message.message_id

    bot_username = context.bot.username

    is_private = chat.type == "private"

    # --------------------------------------------------------
    # 判断是否 @机器人
    # --------------------------------------------------------

    is_mentioned = False

    if bot_username:

        if f"@{bot_username}".lower() in text.lower():

            is_mentioned = True

        elif update.message.reply_to_message:

            reply_user = (
                update.message.reply_to_message.from_user
            )

            if (
                reply_user
                and reply_user.username
                and reply_user.username.lower()
                == bot_username.lower()
            ):

                is_mentioned = True


    # ========================================================
    # 5. 图片处理
    # ========================================================

    target_photo = None

    # 直接发送图片
    if update.message.photo:

        target_photo = update.message.photo[-1]

    # 回复别人发送的图片
    elif (
        update.message.reply_to_message
        and update.message.reply_to_message.photo
    ):

        target_photo = (
            update.message
            .reply_to_message
            .photo[-1]
        )

        # 回复图片时，只使用当前消息的文字
        text = update.message.text or ""


    # --------------------------------------------------------
    # 如果检测到图片
    # --------------------------------------------------------

    if target_photo:

        # 群聊中必须 @机器人或者回复机器人
        if not (is_private or is_mentioned):

            return


        processing_msg = await update.message.reply_text(
            "正在看图分析中，请稍等……"
        )


        try:

            # ------------------------------------------------
            # 从 Telegram 下载图片
            # ------------------------------------------------

            print("🔥 IMAGE HANDLER: BASE64 VERSION RUNNING")

            photo_file = await target_photo.get_file()

            image_bytes = await photo_file.download_as_bytearray()

            print(
                f"🔥 IMAGE SIZE: {len(image_bytes)} bytes"
            )


            # ------------------------------------------------
            # 转 Base64
            # ------------------------------------------------

            image_base64 = base64.b64encode(
                bytes(image_bytes)
            ).decode("utf-8")


            # ------------------------------------------------
            # 使用 Data URL
            #
            # 这样 Agnes 不需要再访问 Telegram 图片 URL
            # ------------------------------------------------

            image_url = (
                f"data:image/jpeg;base64,{image_base64}"
            )


            # ------------------------------------------------
            # 清理 @机器人
            # ------------------------------------------------

            user_prompt = text

            if bot_username:

                user_prompt = user_prompt.replace(
                    f"@{bot_username}",
                    ""
                )

            user_prompt = user_prompt.strip()


            if not user_prompt:

                user_prompt = (
                    "请详细分析这张图片的内容。"
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


            # ------------------------------------------------
            # 获取回答
            # ------------------------------------------------

            reply = response.choices[0].message.content

            if not reply:

                reply = "模型没有返回有效的分析结果。"


            # ------------------------------------------------
            # 返回 Telegram
            #
            # 普通 AI 回复不使用 HTML
            # 避免模型输出 < > 导致 Telegram 报错
            # ------------------------------------------------

            await context.bot.edit_message_text(

                chat_id=chat_id,

                message_id=processing_msg.message_id,

                text=reply

            )


        except Exception as e:

            print(
                f"❌ 图片分析错误: {repr(e)}"
            )


            await context.bot.edit_message_text(

                chat_id=chat_id,

                message_id=processing_msg.message_id,

                text=f"图片分析出错：\n{str(e)}"

            )


        return


    # ========================================================
    # 6. 普通文字消息记录
    # ========================================================

    if text and not text.startswith("/"):

        group_history[chat_id].append(

            {
                "user": user_name,
                "text": text,
                "message_id": message_id
            }

        )


        if len(group_history[chat_id]) > MAX_HISTORY:

            group_history[chat_id].pop(0)


    # ========================================================
    # 7. 普通聊天
    # ========================================================

    if is_private or is_mentioned:

        prompt = text

        if bot_username:

            prompt = prompt.replace(
                f"@{bot_username}",
                ""
            )

        prompt = prompt.strip()


        if not prompt:

            return


        processing_msg = await update.message.reply_text(
            "正在联网查询中……"
        )


        try:

            # ------------------------------------------------
            # 联网搜索
            # ------------------------------------------------

            search_results = search_web(prompt)


            # ------------------------------------------------
            # System Prompt
            # ------------------------------------------------

            system_prompt = (

                "你是一个精明、自然、可靠的 AI 助手。"

                "\n\n"

                "请根据下面的联网搜索结果回答用户的问题。"

                "\n"

                "如果搜索结果不足以确定答案，请明确说明。"

                "\n\n"

                "联网搜索结果：\n"

                f"{search_results}"

            )


            # ------------------------------------------------
            # 调用 Agnes
            # ------------------------------------------------

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


            reply = response.choices[0].message.content


            if not reply:

                reply = "模型没有返回有效回答。"


            # ------------------------------------------------
            # 返回消息
            # ------------------------------------------------

            await context.bot.edit_message_text(

                chat_id=chat_id,

                message_id=processing_msg.message_id,

                text=reply

            )


        except Exception as e:

            print(
                f"❌ AI 请求错误: {repr(e)}"
            )


            await context.bot.edit_message_text(

                chat_id=chat_id,

                message_id=processing_msg.message_id,

                text=f"请求失败：\n{str(e)}"

            )


# ============================================================
# 8. 群聊总结
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


    if len(history) < 3:

        await update.message.reply_text(
            "记录太少，至少需要 3 条消息才能进行总结。"
        )

        return


    status_msg = await update.message.reply_text(
        "正在生成群聊总结……"
    )


    # --------------------------------------------------------
    # 生成消息链接
    # --------------------------------------------------------

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


    # --------------------------------------------------------
    # 整理聊天记录
    # --------------------------------------------------------

    formatted_lines = []


    for item in history:

        msg_link = (
            f"{chat_link_prefix}/{item['message_id']}"
        )


        formatted_lines.append(

            f"• {item['user']}: "
            f"{item['text']} "
            f"[消息链接：{msg_link}]"

        )


    formatted_history = "\n".join(
        formatted_lines
    )


    msg_count = len(history)


    # --------------------------------------------------------
    # 总结提示词
    # --------------------------------------------------------

    system_prompt = (

        "你是一个专业的群聊总结助手。\n\n"

        f"本次一共分析 {msg_count} 条聊天消息。\n\n"

        "请总结这段群聊中的主要内容。\n"

        "列出 3-5 个主要话题。\n\n"

        "格式必须使用 Telegram HTML：\n\n"

        "<b>📝 群聊 AI 总结</b>\n"

        f"💬 已分析 {msg_count} 条消息\n\n"

        "<b>1. 话题名称</b>\n"

        "简短描述这个话题。\n\n"

        "<b>2. 话题名称</b>\n"

        "简短描述这个话题。\n\n"

        "最后添加：\n"

        "<i>以上内容由 AI 根据群聊记录整理。</i>\n\n"

        "不要使用 Markdown。"

    )


    try:

        # ----------------------------------------------------
        # 调用 AI
        # ----------------------------------------------------

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


        reply = response.choices[0].message.content


        if not reply:

            reply = "没有生成有效总结。"


        # ----------------------------------------------------
        # 返回总结
        # ----------------------------------------------------

        await context.bot.edit_message_text(

            chat_id=chat_id,

            message_id=status_msg.message_id,

            text=reply,

            parse_mode="HTML"

        )


    except Exception as e:

        print(
            f"❌ 群聊总结错误: {repr(e)}"
        )


        await context.bot.edit_message_text(

            chat_id=chat_id,

            message_id=status_msg.message_id,

            text=f"总结失败：\n{str(e)}"

            )
