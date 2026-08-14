import os
import base64
import html
import re
import time
import requests
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

AGNES_BASE_URL = "https://apihub.agnes-ai.com/v1"


# ------------------------------------------------------------
# 默认模型
#
# 你要求默认使用 2.0
# ------------------------------------------------------------

DEFAULT_TEXT_MODEL = "agnes-2.0-flash"


# ------------------------------------------------------------
# 文本模型
# ------------------------------------------------------------

TEXT_MODELS = {
    "2.0": "agnes-2.0-flash",
    "2.5": "agnes-2.5-flash",
    "pro": "agnes-2.5-pro",
    "alpha": "agnes-2.5-pro-alpha",
}


# ------------------------------------------------------------
# 图片生成模型
# ------------------------------------------------------------

IMAGE_MODELS = {
    "image": "agnes-image-2.1-flash",
    "image2": "agnes-image-2.0-flash",
}


# ------------------------------------------------------------
# 视频模型
# ------------------------------------------------------------

VIDEO_MODEL = "agnes-video-v2.0"


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
# 6. 解析模型指令
# ============================================================

def parse_model_command(text):

    """
    支持：

    2.0
    2.5
    pro
    alpha
    image
    image2
    video

    示例：

    2.5 解释一下二次函数
    pro 分析这段代码
    image 生成一只猫
    video 生成一段猫奔跑的视频
    """

    if not text:

        return DEFAULT_TEXT_MODEL, text, "text"


    original = text.strip()


    # --------------------------------------------------------
    # 模型关键词
    # --------------------------------------------------------

    pattern = re.compile(
        r"^(?:使用\s*)?"
        r"(2\.0|2\.5|pro|alpha|image2|image|video)"
        r"(?:\s+|[:：]\s*|\s*$)",
        re.IGNORECASE
    )


    match = pattern.match(original)


    if not match:

        return (
            DEFAULT_TEXT_MODEL,
            original,
            "text"
        )


    keyword = match.group(1).lower()


    # --------------------------------------------------------
    # 去掉模型关键词
    # --------------------------------------------------------

    prompt = original[
        match.end():
    ].strip()


    # --------------------------------------------------------
    # 文本模型
    # --------------------------------------------------------

    if keyword in TEXT_MODELS:

        return (
            TEXT_MODELS[keyword],
            prompt,
            "text"
        )


    # --------------------------------------------------------
    # 图片模型
    # --------------------------------------------------------

    if keyword in IMAGE_MODELS:

        return (
            IMAGE_MODELS[keyword],
            prompt,
            "image"
        )


    # --------------------------------------------------------
    # 视频模型
    # --------------------------------------------------------

    if keyword == "video":

        return (
            VIDEO_MODEL,
            prompt,
            "video"
        )


    return (
        DEFAULT_TEXT_MODEL,
        original,
        "text"
    )


# ============================================================
# 7. 模型名称显示
# ============================================================

def get_model_display_name(model):

    names = {

        "agnes-2.0-flash":
            "⚡ Agnes 2.0 Flash",

        "agnes-2.5-flash":
            "🧠 Agnes 2.5 Flash",

        "agnes-2.5-pro":
            "🧠 Agnes 2.5 Pro",

        "agnes-2.5-pro-alpha":
            "🧪 Agnes 2.5 Pro Alpha",

        "agnes-image-2.0-flash":
            "🎨 Agnes Image 2.0 Flash",

        "agnes-image-2.1-flash":
            "🎨 Agnes Image 2.1 Flash",

        "agnes-video-v2.0":
            "🎬 Agnes Video 2.0",

    }

    return names.get(
        model,
        model
    )


# ============================================================
# 8. /models
# ============================================================

async def handle_models(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:

        return


    text = (
        "🤖 <b>Agnes AI 模型列表</b>\n\n"

        "⚡ <b>2.0</b>\n"
        "快速综合聊天\n"
        "指令：<code>2.0</code>\n\n"

        "🧠 <b>2.5</b>\n"
        "更强的推理、代码和综合能力\n"
        "指令：<code>2.5</code>\n\n"

        "🧠 <b>Pro</b>\n"
        "高级模型，适合复杂问题\n"
        "指令：<code>pro</code>\n\n"

        "🧪 <b>Pro Alpha</b>\n"
        "实验性 Pro 模型\n"
        "指令：<code>alpha</code>\n\n"

        "🎨 <b>Image 2.1</b>\n"
        "图片生成 / 编辑\n"
        "指令：<code>image</code>\n\n"

        "🎨 <b>Image 2.0</b>\n"
        "快速图片生成\n"
        "指令：<code>image2</code>\n\n"

        "🎬 <b>Video 2.0</b>\n"
        "视频生成\n"
        "指令：<code>video</code>\n\n"

        "📌 <b>默认模型：</b> "
        "Agnes 2.0 Flash\n\n"

        "示例：\n"
        "<code>@你的机器人 2.5 解释一下黑洞</code>\n"
        "<code>@你的机器人 pro 分析这段代码</code>\n"
        "<code>@你的机器人 image 生成一只猫</code>\n"
        "<code>@你的机器人 video 生成一段海边日落</code>"
    )


    await update.message.reply_text(
        text,
        parse_mode="HTML",
        disable_web_page_preview=True
    )


# ============================================================
# 9. 获取引用消息内容
# ============================================================

def get_quoted_message(message):

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

            quoted_name += (
                f" (@{quoted_user.username})"
            )

    else:

        quoted_name = "未知用户"


    return {

        "user": quoted_name,

        "text": quoted_text,

        "message_id":
            replied.message_id,

        "has_photo":
            bool(replied.photo),

        "has_document":
            bool(replied.document),

        "has_video":
            bool(replied.video),

    }


# ============================================================
# 10. 构造引用上下文
# ============================================================

def build_quote_context(message):

    quote = get_quoted_message(message)


    if not quote:

        return ""


    text = quote["text"].strip()


    if not text:

        if quote["has_photo"]:

            text = (
                "[这是一条图片消息，"
                "图片本身未提供文字内容。]"
            )

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
# 11. 联网搜索
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

            title = r.get(
                "title",
                ""
            )

            body = r.get(
                "body",
                ""
            )

            href = r.get(
                "href",
                ""
            )


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


        return (
            f"联网搜索失败：{e}"
        )


# ============================================================
# 12. 调用 Agnes 文本模型
# ============================================================

def ask_agnes(
    prompt: str,
    system_prompt: str = None,
    model: str = DEFAULT_TEXT_MODEL
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


    print(
        f"[MODEL] 使用模型：{model}"
    )


    response = client.chat.completions.create(

        model=model,

        messages=messages

    )


    if not response.choices:

        return (
            "AI 没有返回有效结果。"
        )


    content = (
        response.choices[0]
        .message
        .content
    )


    if not content:

        return "AI 返回了空内容。"


    return content.strip()


# ============================================================
# 13. 图片生成
# ============================================================

def generate_image(
    prompt: str,
    model: str
):

    if not prompt.strip():

        raise ValueError(
            "请提供图片生成描述。"
        )


    print("=" * 60)
    print("[IMAGE-GEN] 开始生成图片")
    print(f"[IMAGE-GEN] 模型：{model}")
    print(f"[IMAGE-GEN] Prompt：{prompt}")
    print("=" * 60)


    response = client.images.generate(

        model=model,

        prompt=prompt,

        size="1024x1024"

    )


    if not response.data:

        raise RuntimeError(
            "图片 API 没有返回结果。"
        )


    item = response.data[0]


    # --------------------------------------------------------
    # URL
    # --------------------------------------------------------

    image_url = getattr(
        item,
        "url",
        None
    )


    if image_url:

        return {
            "type": "url",
            "value": image_url
        }


    # --------------------------------------------------------
    # Base64
    # --------------------------------------------------------

    image_b64 = getattr(
        item,
        "b64_json",
        None
    )


    if image_b64:

        return {
            "type": "base64",
            "value": image_b64
        }


    raise RuntimeError(
        "图片 API 返回了结果，但没有 URL 或 Base64 数据。"
    )


# ============================================================
# 14. 视频生成
# ============================================================

def create_video(
    prompt: str
):

    url = (
        AGNES_BASE_URL.rstrip("/")
        + "/videos"
    )


    headers = {

        "Authorization":
            f"Bearer {AGNES_API_KEY}",

        "Content-Type":
            "application/json",

    }


    payload = {

        "model":
            VIDEO_MODEL,

        "prompt":
            prompt,

        "height":
            768,

        "width":
            1152,

        "num_frames":
            121,

        "frame_rate":
            24,

    }


    print("=" * 60)
    print("[VIDEO] 创建视频任务")
    print(f"[VIDEO] Prompt：{prompt}")
    print("=" * 60)


    response = requests.post(

        url,

        headers=headers,

        json=payload,

        timeout=60

    )


    if response.status_code >= 400:

        raise RuntimeError(

            f"视频 API 请求失败："
            f"{response.status_code}\n"
            f"{response.text[:1000]}"

        )


    data = response.json()


    video_id = (
        data.get("video_id")
        or data.get("id")
    )


    if not video_id:

        raise RuntimeError(

            "视频 API 没有返回 video_id。"

        )


    return video_id


# ============================================================
# 15. 查询视频任务
# ============================================================

def get_video_result(
    video_id: str
):

    url = (
        "https://apihub.agnes-ai.com"
        "/agnesapi"
    )


    headers = {

        "Authorization":
            f"Bearer {AGNES_API_KEY}",

    }


    response = requests.get(

        url,

        headers=headers,

        params={
            "video_id": video_id
        },

        timeout=60

    )


    if response.status_code >= 400:

        raise RuntimeError(

            f"视频状态查询失败："
            f"{response.status_code}\n"
            f"{response.text[:1000]}"

        )


    return response.json()


# ============================================================
# 16. 等待视频生成
# ============================================================

def wait_for_video(
    video_id: str,
    max_wait=600
):

    start_time = time.time()


    while (
        time.time() - start_time
        < max_wait
    ):

        data = get_video_result(
            video_id
        )


        # ----------------------------------------------------
        # 尝试读取状态
        # ----------------------------------------------------

        status = str(

            data.get("status")
            or data.get("state")
            or ""

        ).lower()


        print(
            f"[VIDEO] 状态：{status}"
        )


        # ----------------------------------------------------
        # 成功
        # ----------------------------------------------------

        if status in (
            "completed",
            "complete",
            "succeeded",
            "success",
            "done",
            "finished"
        ):

            video_url = (

                data.get("video_url")

                or data.get("url")

                or data.get("output_url")

            )


            if not video_url:

                video_data = (
                    data.get("data")
                )


                if isinstance(
                    video_data,
                    dict
                ):

                    video_url = (

                        video_data.get(
                            "video_url"
                        )

                        or

                        video_data.get(
                            "url"
                        )

                    )


            if video_url:

                return video_url


            raise RuntimeError(

                "视频生成成功，但没有找到视频 URL。"

            )


        # ----------------------------------------------------
        # 失败
        # ----------------------------------------------------

        if status in (
            "failed",
            "error",
            "cancelled",
            "canceled"
        ):

            error_message = (

                data.get("error")
                or data.get("message")
                or "未知错误"

            )


            raise RuntimeError(

                f"视频生成失败："
                f"{error_message}"

            )


        # ----------------------------------------------------
        # 等待
        # ----------------------------------------------------

        time.sleep(5)


    raise TimeoutError(
        "视频生成等待超时，请稍后再试。"
    )


# ============================================================
# 17. AI 回复排版
# ============================================================

def format_ai_reply(text):

    if not text:

        return "AI 没有返回内容。"


    text = text.strip()


    # --------------------------------------------------------
    # HTML Escape
    # --------------------------------------------------------

    text = html.escape(text)


    # --------------------------------------------------------
    # Markdown 链接
    # --------------------------------------------------------

    text = re.sub(

        r"\[([^\]]+)\]"
        r"\((https?://[^\s)]+)\)",

        r'<a href="\2">\1</a>',

        text

    )


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
    # 加粗
    # --------------------------------------------------------

    text = re.sub(

        r"\*\*(.+?)\*\*",

        r"<b>\1</b>",

        text

    )


    # --------------------------------------------------------
    # 标题
    # --------------------------------------------------------

    text = re.sub(

        r"(?m)^#{1,6}\s*(.+)$",

        r"<b>\1</b>",

        text

    )


    # --------------------------------------------------------
    # 斜体
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
    # 清理空行
    # --------------------------------------------------------

    text = re.sub(

        r"\n{3,}",

        "\n\n",

        text

    )


    # --------------------------------------------------------
    # Telegram 长度
    # --------------------------------------------------------

    if len(text) > MAX_TELEGRAM_LENGTH:

        text = (

            text[:3900]

            + "\n\n"

            + "……内容过长，已截断。"

        )


    return text


# ============================================================
# 18. 安全发送 AI 回复
# ============================================================

async def edit_ai_message(
    context,
    chat_id,
    message_id,
    text
):

    formatted = format_ai_reply(
        text
    )


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
# 19. 图片识别
# ============================================================

async def analyze_image(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    target_photo,
    user_prompt: str,
    model: str = DEFAULT_TEXT_MODEL
):

    processing_msg = await update.message.reply_text(
        "🖼️ 正在分析图片……"
    )


    try:

        # ----------------------------------------------------
        # 下载图片
        # ----------------------------------------------------

        photo_file = await target_photo.get_file()


        image_bytes = (
            await photo_file
            .download_as_bytearray()
        )


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
        # 引用上下文
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


        print(
            f"[VISION] 使用模型：{model}"
        )


        # ----------------------------------------------------
        # 多模态请求
        # ----------------------------------------------------

        response = client.chat.completions.create(

            model=model,

            messages=[

                {

                    "role":
                        "user",

                    "content": [

                        {

                            "type":
                                "text",

                            "text":
                                user_prompt

                        },

                        {

                            "type":
                                "image_url",

                            "image_url": {

                                "url":
                                    image_url

                            }

                        }

                    ]

                }

            ]

        )


        if not response.choices:

            reply = (
                "AI 没有返回图片分析结果。"
            )


        else:

            reply = (
                response
                .choices[0]
                .message
                .content
            )


            if not reply:

                reply = (
                    "AI 返回了空的图片分析结果。"
                )


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
# 20. 图片生成处理
# ============================================================

async def handle_image_generation(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    prompt: str,
    model: str
):

    status_msg = await update.message.reply_text(

        "🎨 正在生成图片……\n"
        f"模型：{get_model_display_name(model)}"

    )


    try:

        result = generate_image(

            prompt,

            model

        )


        # ----------------------------------------------------
        # URL
        # ----------------------------------------------------

        if result["type"] == "url":

            await context.bot.send_photo(

                chat_id=update.effective_chat.id,

                photo=result["value"],

                caption=(
                    "🎨 图片生成完成\n"
                    f"模型："
                    f"{get_model_display_name(model)}"
                )

            )


        # ----------------------------------------------------
        # Base64
        # ----------------------------------------------------

        elif result["type"] == "base64":

            image_bytes = base64.b64decode(

                result["value"]

            )


            await context.bot.send_photo(

                chat_id=update.effective_chat.id,

                photo=image_bytes,

                caption=(
                    "🎨 图片生成完成\n"
                    f"模型："
                    f"{get_model_display_name(model)}"
                )

            )


        await context.bot.delete_message(

            chat_id=update.effective_chat.id,

            message_id=status_msg.message_id

        )


    except Exception as e:

        print("=" * 60)
        print("[IMAGE-GEN] 图片生成失败")
        print(repr(e))
        print("=" * 60)


        await context.bot.edit_message_text(

            chat_id=update.effective_chat.id,

            message_id=status_msg.message_id,

            text=(

                "❌ 图片生成失败\n\n"
                f"{str(e)}"

            )

        )


# ============================================================
# 21. 视频生成处理
# ============================================================

async def handle_video_generation(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    prompt: str
):

    status_msg = await update.message.reply_text(

        "🎬 正在创建视频任务……\n"
        "视频生成可能需要一些时间。"

    )


    try:

        video_id = create_video(
            prompt
        )


        await context.bot.edit_message_text(

            chat_id=update.effective_chat.id,

            message_id=status_msg.message_id,

            text=(
                "🎬 视频正在生成……\n\n"
                f"任务 ID：<code>{html.escape(video_id)}</code>"
            ),

            parse_mode="HTML"

        )


        video_url = await asyncio.to_thread(

            wait_for_video,

            video_id

        )


        await context.bot.send_video(

            chat_id=update.effective_chat.id,

            video=video_url,

            caption="🎬 视频生成完成"

        )


        await context.bot.delete_message(

            chat_id=update.effective_chat.id,

            message_id=status_msg.message_id

        )


    except Exception as e:

        print("=" * 60)
        print("[VIDEO] 视频生成失败")
        print(repr(e))
        print("=" * 60)


        await context.bot.edit_message_text(

            chat_id=update.effective_chat.id,

            message_id=status_msg.message_id,

            text=(

                "❌ 视频生成失败\n\n"
                f"{str(e)}"

            )

        )


# ============================================================
# 22. 普通消息处理
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

    bot_username = await get_bot_username(
        context
    )


    # --------------------------------------------------------
    # 当前消息文字
    # --------------------------------------------------------

    text = get_message_text(
        update.message
    )


    # --------------------------------------------------------
    # 引用上下文
    # --------------------------------------------------------

    quote_context = build_quote_context(
        update.message
    )


    # --------------------------------------------------------
    # 私聊
    # --------------------------------------------------------

    is_private = (

        chat.type
        == ChatType.PRIVATE

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
    # 回复机器人
    # --------------------------------------------------------

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

                and

                bot_username

                and

                replied_user.username.lower()
                == bot_username.lower()

            ):

                is_reply_to_bot = True


    # ========================================================
    # A. 图片消息
    # ========================================================

    target_photo = None


    if update.message.photo:

        target_photo = (
            update.message.photo[-1]
        )


    elif (

        update.message.reply_to_message

        and

        update.message
        .reply_to_message
        .photo

    ):

        target_photo = (

            update.message
            .reply_to_message
            .photo[-1]

        )


    if target_photo:

        allowed = (

            is_private

            or

            is_mentioned

            or

            is_reply_to_bot

        )


        if not allowed:

            return


        user_prompt = text


        if bot_username:

            user_prompt = re.sub(

                rf"@{re.escape(bot_username)}",

                "",

                user_prompt,

                flags=re.IGNORECASE

            )


        user_prompt = user_prompt.strip()


        # ----------------------------------------------------
        # 图片识别也支持指定文本模型
        #
        # @Bot 2.5 这张图是什么？
        # ----------------------------------------------------

        model, user_prompt, action = (
            parse_model_command(
                user_prompt
            )
        )


        # image / video 对图片识别没有意义
        # 如果用户误输入，则仍使用默认视觉模型

        if action != "text":

            model = DEFAULT_TEXT_MODEL


        await analyze_image(

            update,

            context,

            target_photo,

            user_prompt,

            model

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

                "user":
                    user_name,

                "text":
                    text,

                "message_id":
                    update.message.message_id

            })


            if (

                len(group_history[chat_id])
                > MAX_HISTORY

            ):

                group_history[chat_id].pop(0)


    # --------------------------------------------------------
    # 触发规则
    # --------------------------------------------------------

    if not (

        is_private

        or

        is_mentioned

        or

        is_reply_to_bot

    ):

        return


    # --------------------------------------------------------
    # 去掉 @机器人
    # --------------------------------------------------------

    prompt = text


    if bot_username:

        prompt = re.sub(

            rf"@{re.escape(bot_username)}",

            "",

            prompt,

            flags=re.IGNORECASE

        )


    prompt = prompt.strip()


    # --------------------------------------------------------
    # 解析模型
    # --------------------------------------------------------

    model, prompt, action = (
        parse_model_command(
            prompt
        )
    )


    # --------------------------------------------------------
    # 没有问题
    # --------------------------------------------------------

    if not prompt:

        if quote_context:

            prompt = (
                "请分析一下我引用的这条消息。"
            )

        else:

            return


    # ========================================================
    # C. 图片生成
    # ========================================================

    if action == "image":

        await handle_image_generation(

            update,

            context,

            prompt,

            model

        )

        return


    # ========================================================
    # D. 视频生成
    # ========================================================

    if action == "video":

        await handle_video_generation(

            update,

            context,

            prompt

        )

        return


    # ========================================================
    # E. 普通文本 AI
    # ========================================================

    processing_msg = await update.message.reply_text(

        "🤖 正在思考……\n"
        f"模型：{get_model_display_name(model)}"

    )


    try:

        # ----------------------------------------------------
        # 联网搜索
        # ----------------------------------------------------

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

            "1. 使用自然、清晰的中文。\n\n"

            "2. 不要输出 HTML 标签。\n\n"

            "3. 可以使用 Markdown，例如 **加粗**。\n\n"

            "4. 重要结论可以加粗。\n\n"

            "5. 使用 emoji 作为小标题，例如：\n"
            "💡 核心观点\n"
            "📌 具体原因\n"
            "🔍 进一步分析\n\n"

            "6. 不要把所有内容挤成一大段。\n\n"

            "7. 每个主要观点之间留一个空行。\n\n"

            "8. 列表使用 - 或 1. 2. 3.。\n\n"

            "9. 如果问题比较简单，直接回答，"
            "不要故意写得很长。\n\n"

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
        print(f"[AI] 模型：{model}")
        print(f"[AI] 问题：{prompt}")


        if quote_context:

            print(
                "[AI] 本次问题包含引用消息"
            )


        print("=" * 60)


        # ----------------------------------------------------
        # 调用模型
        # ----------------------------------------------------

        reply = ask_agnes(

            final_prompt,

            system_prompt,

            model

        )


        # ----------------------------------------------------
        # 回复
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
# 23. /summary 群聊总结
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

            "📝 目前记录太少，"
            "至少需要 3 条消息才能进行总结。"

        )

        return


    status_msg = await update.message.reply_text(

        "📝 正在生成群聊总结……"

    )


    # --------------------------------------------------------
    # 创建 Telegram 消息链接
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
    # 聊天记录
    # --------------------------------------------------------

    formatted_lines = []


    for index, item in enumerate(

        history,

        start=1

    ):

        formatted_lines.append(

            f"[MSG:{index}]\n"
            f"用户：{item['user']}\n"
            f"内容：{item['text']}"

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

        "7. 使用 emoji 小标题。\n\n"

        "8. 每个主要话题必须使用以下格式：\n"

        "[TOPIC:话题标题|MSG:消息编号]\n"

        "然后下一行写该话题的总结内容。\n\n"

        "例如：\n"

        "[TOPIC:系统体验讨论|MSG:3]\n"

        "用户讨论了系统的流畅度和动画效果……\n\n"

        "[TOPIC:版本升级问题|MSG:7]\n"

        "用户讨论了系统升级限制……\n\n"

        "9. MSG 必须是聊天记录中真实存在的 MSG 编号。\n"

        "10. 每个话题只选择一条最有代表性的消息。\n"

        "11. 不要输出任何完整 URL。\n"

        "12. 不要生成“🔗 相关消息”区域。\n"

        "13. 不要在最后重复列出消息编号。\n"

        "14. 最后使用：\n"

        "💡 **总体结论**\n"

        "然后给出整体总结。"

    )


    try:

        response = client.chat.completions.create(

            model=DEFAULT_TEXT_MODEL,

            messages=[

                {

                    "role":
                        "system",

                    "content":
                        system_prompt

                },

                {

                    "role":
                        "user",

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


        result = (
            response
            .choices[0]
            .message
            .content
        )


        if not result:

            raise RuntimeError(
                "AI 返回了空总结。"
            )


        result = result.strip()


        # ----------------------------------------------------
        # 删除 Telegram URL
        # ----------------------------------------------------

        result = re.sub(

            r"https?://t\.me/[^\s)\]>]+",

            "",

            result

        )


        # ----------------------------------------------------
        # 删除相关消息区域
        # ----------------------------------------------------

        result = re.sub(

            r"\n*🔗\s*(?:\*\*)?"
            r"相关消息(?:\*\*)?.*",

            "",

            result,

            flags=re.S

        ).strip()


        # ----------------------------------------------------
        # 解析 Topic
        # ----------------------------------------------------

        topic_pattern = re.compile(

            r"\[TOPIC:(.*?)\|MSG:(\d+)\]"

        )


        topic_links = {}

        topic_counter = 0


        def replace_topic(match):

            nonlocal topic_counter


            topic_title = (

                match.group(1).strip()

            )


            try:

                msg_index = int(

                    match.group(2)

                )

            except ValueError:

                return match.group(0)


            if (

                msg_index < 1

                or

                msg_index > len(history)

            ):

                return (

                    f"📌 {topic_title}"

                )


            target_message = history[

                msg_index - 1

            ]


            msg_link = (

                f"{chat_link_prefix}/"
                f"{target_message['message_id']}"

            )


            placeholder = (

                f"TOPICLINKPLACEHOLDER"
                f"{topic_counter}"

            )


            topic_links[placeholder] = (

                topic_title,

                msg_link

            )


            topic_counter += 1


            return placeholder


        result = topic_pattern.sub(

            replace_topic,

            result

        )


        # ----------------------------------------------------
        # HTML Escape
        # ----------------------------------------------------

        final_text = html.escape(

            result,

            quote=False

        )


        # ----------------------------------------------------
        # 加粗
        # ----------------------------------------------------

        final_text = re.sub(

            r"\*\*(.+?)\*\*",

            r"<b>\1</b>",

            final_text

        )


        # ----------------------------------------------------
        # 标题
        # ----------------------------------------------------

        final_text = re.sub(

            r"(?m)^#{1,6}\s*(.+)$",

            r"<b>\1</b>",

            final_text

        )


        # ----------------------------------------------------
        # 列表
        # ----------------------------------------------------

        final_text = re.sub(

            r"(?m)^[ \t]*[-*]\s+",

            "• ",

            final_text

        )


        # ----------------------------------------------------
        # 恢复链接
        # ----------------------------------------------------

        for (

            placeholder,

            (

                topic_title,

                msg_link

            )

        ) in topic_links.items():


            anchor = (

                f'<a href="'
                f'{html.escape(msg_link, quote=True)}'
                f'">'
                f'📌 '
                f'{html.escape(topic_title)}'
                f'</a>'

            )


            final_text = final_text.replace(

                placeholder,

                anchor

            )


        # ----------------------------------------------------
        # 清理空行
        # ----------------------------------------------------

        final_text = re.sub(

            r"\n{3,}",

            "\n\n",

            final_text

        ).strip()


        if not final_text:

            raise RuntimeError(
                "AI 总结内容为空。"
            )


        # ----------------------------------------------------
        # Telegram 长度
        # ----------------------------------------------------

        if len(final_text) > MAX_TELEGRAM_LENGTH:

            final_text = (

                final_text[:3900]

                + "\n\n"

                + "……内容过长，已截断。"

            )


        # ----------------------------------------------------
        # 发送
        # ----------------------------------------------------

        try:

            await context.bot.edit_message_text(

                chat_id=chat_id,

                message_id=status_msg.message_id,

                text=final_text,

                parse_mode="HTML",

                disable_web_page_preview=True

            )


        except Exception as send_error:

            print("=" * 60)
            print("[SUMMARY] HTML 总结发送失败")
            print(repr(send_error))
            print("=" * 60)


            plain_text = re.sub(

                r"<[^>]+>",

                "",

                final_text

            )


            await context.bot.edit_message_text(

                chat_id=chat_id,

                message_id=status_msg.message_id,

                text=plain_text[:4000],

                disable_web_page_preview=True

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
# 24. 注册 Handler
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
    # /models
    # --------------------------------------------------------

    application.add_handler(

        CommandHandler(

            "models",

            handle_models

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
        "[HANDLER] Telegram handlers 注册完成"
    )
