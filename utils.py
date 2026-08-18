import html
import re


# ============================================================
# 获取消息文本
# ============================================================

def get_message_text(message):

    if not message:
        return ""

    if message.text:
        return message.text

    if message.caption:
        return message.caption

    return ""


# ============================================================
# 获取引用消息
# ============================================================

def get_quoted_message(message):

    if not message:
        return None

    return message.reply_to_message


# ============================================================
# 构造引用上下文
# ============================================================

def build_quote_context(message):

    quoted = get_quoted_message(
        message
    )


    if not quoted:
        return ""


    quoted_user = (
        quoted.from_user
    )


    if quoted_user:

        quoted_name = (
            quoted_user.first_name
            or quoted_user.username
            or "用户"
        )

    else:

        quoted_name = "用户"


    quoted_text = get_message_text(
        quoted
    )


    if not quoted_text:

        quoted_text = (
            "[这是一条图片或其他媒体消息]"
        )


    return (

        "【引用的消息】\n"

        f"用户：{quoted_name}\n"

        f"内容：{quoted_text}\n\n"

    )


# ============================================================
# 联网搜索
#
# 当前项目只是保留搜索工具。
# AI 本身是否支持联网，由模型能力决定。
# ============================================================

def search_web(query):

    if not query:
        return ""


    try:

        from ddgs import DDGS

        results = []


        with DDGS() as ddgs:

            search_results = ddgs.text(

                query,

                max_results=5

            )


            for item in search_results:

                title = item.get(
                    "title",
                    ""
                )

                body = item.get(
                    "body",
                    ""
                )

                href = item.get(
                    "href",
                    ""
                )


                results.append(

                    f"标题：{title}\n"
                    f"摘要：{body}\n"
                    f"链接：{href}"

                )


        if not results:

            return (
                "没有找到相关搜索结果。"
            )


        return "\n\n".join(
            results
        )


    except Exception as e:

        print(
            "[SEARCH] 搜索失败：",
            repr(e)
        )

        return (
            "联网搜索暂时不可用。"
        )


# ============================================================
# Markdown → Telegram HTML
# ============================================================

def format_ai_reply(
    text,
    max_length=4000
):

    if not text:
        return ""


    text = text.strip()


    # --------------------------------------------------------
    # 保护代码块
    # --------------------------------------------------------

    code_blocks = []


    def save_code(match):

        index = len(code_blocks)

        code_blocks.append(
            match.group(1)
        )

        return (
            f"__CODE_BLOCK_{index}__"
        )


    text = re.sub(

        r"```(?:[a-zA-Z0-9_+-]+)?\n?"
        r"(.*?)```",

        save_code,

        text,

        flags=re.S

    )


    # --------------------------------------------------------
    # HTML 转义
    # --------------------------------------------------------

    text = html.escape(
        text,
        quote=False
    )


    # --------------------------------------------------------
    # 粗体
    # --------------------------------------------------------

    text = re.sub(

        r"\*\*(.+?)\*\*",

        r"<b>\1</b>",

        text

    )


    # --------------------------------------------------------
    # Markdown 行内代码
    # --------------------------------------------------------

    text = re.sub(

        r"`([^`\n]+)`",

        r"<code>\1</code>",

        text

    )


    # --------------------------------------------------------
    # 删除 Markdown 标题符号
    # --------------------------------------------------------

    text = re.sub(

        r"(?m)^\s*#{1,6}\s*",

        "",

        text

    )


    # --------------------------------------------------------
    # 恢复代码块
    # --------------------------------------------------------

    for index, code in enumerate(
        code_blocks
    ):

        placeholder = (
            f"__CODE_BLOCK_{index}__"
        )


        code = html.escape(
            code,
            quote=False
        )


        replacement = (
            "<pre>"
            + code
            + "</pre>"
        )


        text = text.replace(
            placeholder,
            replacement
        )


    # --------------------------------------------------------
    # Telegram 长度限制
    # --------------------------------------------------------

    if len(text) > max_length:

        text = (
            text[:max_length - 20]
            + "\n\n…"
        )


    return text


# ============================================================
# 编辑 AI 消息
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


    except Exception:

        # ----------------------------------------------------
        # HTML 失败时使用纯文本
        # ----------------------------------------------------

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
