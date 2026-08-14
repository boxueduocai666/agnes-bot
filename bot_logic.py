import os
import base64
import html
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
from duckduckgo_search import DDGS


# ============================================================
# 1. Agnes API 配置
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
# 3. 联网搜索
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

        print("联网搜索失败：", repr(e))

        return f"联网搜索失败：{e}"


# ============================================================
# 4. 调用 Agnes 文本模型
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

    return content


# ============================================================
# 5. 获取机器人用户名
# ============================================================

async def get_bot_username(context):

    try:

        me = await context.bot.get_me()

        return me.username

    except Exception:

        return None


# ============================================================
# 6. 图片识别
# ============================================================

async def analyze_image(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    target_photo,
    user_prompt: str
):

    processing_msg = await update.message.reply_text(
        "🖼️ 正在下载图片并进行分析……"
    )

    try:

        # ----------------------------------------------------
        # 第一步：从 Telegram 下载图片
        # ----------------------------------------------------

        photo_file = await target_photo.get_file()

        image_bytes = await photo_file.download_as_bytearray()

        if not image_bytes:

            raise RuntimeError(
                "Telegram 图片下载失败，得到的图片为空。"
            )


        # ----------------------------------------------------
        # 第二步：转 Base64
        # ----------------------------------------------------

        image_base64 = base64.b64encode(
            bytes(image_bytes)
        ).decode("utf-8")


        # ----------------------------------------------------
        # 第三步：构造 Data URL
        # ----------------------------------------------------

        image_url = (
            "data:image/jpeg;base64,"
            + image_base64
        )


        # ----------------------------------------------------
        # 第四步：默认问题
        # ----------------------------------------------------

        if not user_prompt.strip():

            user_prompt = (
                "请详细分析这张图片。"
                "描述图片中的主要内容、人物、物体、环境以及"
                "能够从图片中明确判断出的信息。"
                "不要凭空编造图片中不存在的内容。"
            )


        # ----------------------------------------------------
        # 第五步：发送给 Agnes 多模态模型
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


        # ----------------------------------------------------
        # 第六步：读取结果
        # ----------------------------------------------------

        if not response.choices:

            reply = "AI 没有返回图片分析结果。"

        else:

            reply = response.choices[0].message.content

            if not reply:
                reply = "AI 返回了空的图片分析结果。"


        # Telegram 单条消息长度限制
        if len(reply) > 4000:

            reply = reply[:3900] + "\n\n……内容过长，已截断。"


        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=processing_msg.message_id,
            text=reply
        )


    except Exception as e:

        print("=" * 60)
        print("图片分析失败：")
        print(repr(e))
        print("=" * 60)

        error_text = (
            "❌ 图片分析失败\n\n"
            f"{str(e)}"
        )

        if len(error_text) > 4000:
            error_text = error_text[:3900] + "\n……"

        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=processing_msg.message_id,
            text=error_text
        )


# ============================================================
# 7. 普通消息处理
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
    # 获取文本
    # --------------------------------------------------------

    text = (
        update.message.text
        or update.message.caption
        or ""
    )


    # --------------------------------------------------------
    # 判断是否私聊
    # --------------------------------------------------------

    is_private = (
        chat.type == ChatType.PRIVATE
    )


    # --------------------------------------------------------
    # 判断是否 @机器人
    # --------------------------------------------------------

    is_mentioned = False

    if bot_username and text:

        is_mentioned = (
            f"@{bot_username.lower()}"
            in text.lower()
        )


    # --------------------------------------------------------
    # 判断是否回复机器人
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


    # ========================================================
    # A. 图片处理
    # ========================================================

    target_photo = None


    # 直接发送图片
    if update.message.photo:

        target_photo = update.message.photo[-1]


    # 回复一张图片
    elif (
        update.message.reply_to_message
        and update.message.reply_to_message.photo
    ):

        target_photo = (
            update.message.reply_to_message.photo[-1]
        )


        # 当前消息的文字作为问题
        text = update.message.text or ""


    if target_photo:

        # 私聊可以直接分析
        # 群聊需要 @机器人、回复机器人，或者回复图片
        allowed = (
            is_private
            or is_mentioned
            or is_reply_to_bot
            or update.message.reply_to_message is not None
        )

        if not allowed:
            return


        # 去掉 @机器人
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
    # 判断是否需要机器人回复
    # --------------------------------------------------------

    if not (
        is_private
        or is_mentioned
        or is_reply_to_bot
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


    if not prompt:
        return


    # ========================================================
    # C. 联网搜索
    # ========================================================

    processing_msg = await update.message.reply_text(
        "🔎 正在联网查询……"
    )


    try:

        search_results = search_web(prompt)


        system_prompt = (
            "你是一个智能 Telegram AI 助手。\n\n"

            "用户的问题如下。\n"

            "你可以参考联网搜索结果回答问题。\n\n"

            "要求：\n"
            "1. 优先保证事实准确。\n"
            "2. 如果搜索结果不足以确定答案，要明确说明。\n"
            "3. 不要声称自己知道搜索结果之外的信息。\n"
            "4. 用自然、清晰的中文回答。\n"
            "5. 不要使用 HTML 标签。\n\n"

            "联网搜索结果：\n"
            "--------------------\n"
            f"{search_results}\n"
            "--------------------"
        )


        reply = ask_agnes(
            prompt,
            system_prompt
        )


        if len(reply) > 4000:

            reply = reply[:3900] + "\n\n……内容过长，已截断。"


        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=processing_msg.message_id,
            text=reply
        )


    except Exception as e:

        print("=" * 60)
        print("AI 请求失败：")
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
# 8. /summary 群聊总结
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


    # --------------------------------------------------------
    # 消息数量检查
    # --------------------------------------------------------

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
    # 让 AI 总结
    # --------------------------------------------------------

    system_prompt = (
        "你是一个群聊总结助手。\n\n"

        "请根据聊天记录总结最近的讨论内容。\n\n"

        "要求：\n"
        "1. 找出 3-5 个主要话题。\n"
        "2. 每个话题用简短的一两句话说明。\n"
        "3. 不要编造聊天记录中不存在的内容。\n"
        "4. 如果某个话题明显没有讨论，不要硬凑。\n"
        "5. 输出纯文本，不要使用 Markdown。\n\n"

        "输出格式严格如下：\n\n"

        "📝 群聊 AI 总结\n"
        f"💬 已分析 {len(history)} 条消息\n\n"

        "1. 话题名称\n"
        "内容描述\n"
        "相关消息：消息编号\n\n"

        "2. 话题名称\n"
        "内容描述\n"
        "相关消息：消息编号\n\n"

        "最后一句：点击下方消息链接可查看原消息。"
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
        # 给总结最后附上消息链接
        # ----------------------------------------------------

        links = []

        # 这里不让 AI 直接生成 HTML，
        # 防止 HTML 格式错误导致 Telegram 拒绝消息。

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
            + "🔗 相关消息链接：\n"
            + "\n".join(links)
        )


        if len(final_text) > 4000:

            final_text = final_text[:3900] + (
                "\n\n……总结过长，已截断。"
            )


        await context.bot.edit_message_text(

            chat_id=chat_id,

            message_id=status_msg.message_id,

            text=final_text
        )


    except Exception as e:

        print("=" * 60)
        print("群聊总结失败：")
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
# 9. 注册所有 Handler
# ============================================================

def register_handlers(
    application: Application
):

    # /summary
    application.add_handler(
        CommandHandler(
            "summary",
            handle_summary
        )
    )


    # 普通消息、图片、回复
    application.add_handler(

        MessageHandler(
            filters.ALL,
            handle_message
        )

        )
