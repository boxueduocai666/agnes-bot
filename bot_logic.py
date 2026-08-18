import html
import re

from collections import defaultdict

from telegram import Update
from telegram.constants import ChatType

from telegram.ext import ContextTypes

from config import (
    MAX_HISTORY,
    AUTO_SUMMARY_MESSAGE_COUNT,
)

from ai_logic import (
    ask_agnes,
    analyze_image,
    get_user_model,
)

from utils import (
    get_message_text,
    build_quote_context,
    edit_ai_message,
    format_ai_reply,
)

from database import (
    save_message,
    get_message_count,
    get_messages,
    clear_messages,
)


# ============================================================
# 群聊内存历史
# ============================================================

group_history = defaultdict(list)


# ============================================================
# 无意义消息
# ============================================================

IGNORED_MESSAGES = {

    "你好",
    "嗨",
    "哈喽",
    "hello",
    "hi",
    "早",
    "早上好",
    "晚上好",
    "晚安",
    "哈哈",
    "哈哈哈",
    "哈哈哈哈",
    "嗯",
    "哦",
    "噢",
    "啊",
    "好的",
    "好",
    "收到",
    "ok",
    "OK",
    "666",
    "6",

}


# ============================================================
# 判断是否有意义
# ============================================================

def is_meaningful_message(text):

    if not text:
        return False


    cleaned = text.strip()


    if not cleaned:
        return False


    if cleaned in IGNORED_MESSAGES:
        return False


    if len(cleaned) <= 1:
        return False


    return True


# ============================================================
# 获取机器人用户名
# ============================================================

async def get_bot_username(context):

    try:

        me = await context.bot.get_me()

        return me.username

    except Exception as e:

        print(
            "[BOT] 获取机器人用户名失败：",
            repr(e)
        )

        return None


# ============================================================
# 添加群聊历史
# ============================================================

def add_group_history(
    chat_id,
    user_name,
    text,
    message_id
):

    group_history[chat_id].append({

        "user": user_name,

        "text": text,

        "message_id": message_id

    })


    if len(group_history[chat_id]) > MAX_HISTORY:

        group_history[chat_id].pop(0)


# ============================================================
# 清理群聊内存历史
# ============================================================

def clear_group_history(chat_id):

    group_history.pop(
        chat_id,
        None
    )


# ============================================================
# 自动群聊总结
# ============================================================

async def auto_summary(
    chat_id,
    context
):

    messages = get_messages(
        chat_id
    )


    if len(messages) < AUTO_SUMMARY_MESSAGE_COUNT:

        return False


    print("=" * 60)

    print(
        "[AUTO SUMMARY] 开始自动总结"
    )

    print(
        f"[AUTO SUMMARY] Chat ID：{chat_id}"
    )

    print(
        f"[AUTO SUMMARY] 消息数量：{len(messages)}"
    )

    print("=" * 60)


    formatted_lines = []


    for index, item in enumerate(
        messages,
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


    system_prompt = (

        "你是一个 Telegram 群聊总结助手。\n\n"

        "请总结下面这段群聊。\n\n"

        "要求：\n"

        "1. 过滤无意义的闲聊和打招呼。\n"
        "2. 找出主要讨论话题。\n"
        "3. 总结重要观点、问题和结论。\n"
        "4. 不要编造不存在的信息。\n"
        "5. 使用自然中文。\n"
        "6. 使用 Markdown 排版。\n"
        "7. 使用简洁的 emoji 小标题。\n"
        "8. 不需要输出消息链接。\n"
        "9. 不需要输出 MSG 编号。\n"
        "10. 如果聊天内容没有明确结论，不要强行制造结论。\n\n"

        "最后给出：\n"
        "💡 **总体结论**"

    )


    try:

        reply = ask_agnes(

            prompt=(

                "以下是需要总结的群聊记录：\n\n"

                + formatted_history

            ),

            system_prompt=system_prompt

        )


        if not reply:

            return False


        formatted_reply = format_ai_reply(
            reply
        )


        await context.bot.send_message(

            chat_id=chat_id,

            text=(
                "📝 <b>群聊自动总结</b>\n\n"
                + formatted_reply
            ),

            parse_mode="HTML",

            disable_web_page_preview=True

        )


        clear_messages(
            chat_id
        )


        clear_group_history(
            chat_id
        )


        print(
            "[AUTO SUMMARY] 总结完成，已清理旧消息"
        )


        return True


    except Exception as e:

        print("=" * 60)

        print(
            "[AUTO SUMMARY] 总结失败"
        )

        print(
            repr(e)
        )

        print("=" * 60)

        # 总结失败时绝对不删除数据库。

        return False


# ============================================================
# /summary
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


    # --------------------------------------------------------
    # 优先 SQLite
    # --------------------------------------------------------

    history = get_messages(
        chat_id
    )


    # --------------------------------------------------------
    # SQLite 没数据则使用内存
    # --------------------------------------------------------

    if not history:

        history = group_history.get(
            chat_id,
            []
        )


    if len(history) < 3:

        await update.message.reply_text(

            "📝 目前记录太少，至少需要 3 条有效消息才能进行总结。"

        )

        return


    status_msg = await update.message.reply_text(

        "📝 正在生成群聊总结……"

    )


    # --------------------------------------------------------
    # Telegram 消息链接
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

            cid = cid.replace(
                "-",
                ""
            )


        chat_link_prefix = (
            f"https://t.me/c/{cid}"
        )


    # --------------------------------------------------------
    # 构造聊天记录
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
    # Summary Prompt
    # --------------------------------------------------------

    system_prompt = (

        "你是一个群聊总结助手。\n\n"

        "请根据聊天记录总结最近的讨论内容。\n\n"

        "要求：\n"

        "1. 自动过滤无意义的打招呼、寒暄和简单回应。\n"

        "2. 找出 3-5 个主要话题。\n"

        "3. 每个话题简洁说明。\n"

        "4. 不要编造聊天记录中不存在的内容。\n"

        "5. 使用自然中文。\n"

        "6. 使用 Markdown 排版。\n"

        "7. 重要内容可以使用 **加粗**。\n"

        "8. 使用 emoji 小标题。\n\n"

        "9. 每个主要话题必须使用：\n"
        "[TOPIC:话题标题|MSG:消息编号]\n\n"

        "10. MSG 必须是真实存在的 MSG 编号。\n"

        "11. 每个话题只选择一条最有代表性的消息。\n"

        "12. 不要输出完整 URL。\n"

        "13. 不要生成“相关消息”区域。\n"

        "14. 最后使用：\n"
        "💡 **总体结论**\n\n"

        "然后给出整体总结。"

    )


    try:

        response = ask_agnes(

            prompt=(

                "以下是聊天记录：\n\n"

                + formatted_history

            ),

            system_prompt=system_prompt

        )


        if not response:

            raise RuntimeError(
                "AI 没有返回总结内容。"
            )


        result = response.strip()


        # ----------------------------------------------------
        # 删除 AI 生成的 Telegram URL
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

            r"\n*🔗\s*(?:\*\*)?相关消息(?:\*\*)?.*",

            "",

            result,

            flags=re.S

        ).strip()


        # ----------------------------------------------------
        # TOPIC
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

                return (
                    f"📌 {topic_title}"
                )


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
        # Markdown → HTML
        # ----------------------------------------------------

        final_text = format_ai_reply(
            result
        )


        # ----------------------------------------------------
        # 恢复 Topic 链接
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
                f'📌 {html.escape(topic_title)}'
                f'</a>'

            )


            final_text = final_text.replace(

                placeholder,

                anchor

            )


        # ----------------------------------------------------
        # 发送结果
        # ----------------------------------------------------

        try:

            await context.bot.edit_message_text(

                chat_id=chat_id,

                message_id=status_msg.message_id,

                text=final_text,

                parse_mode="HTML",

                disable_web_page_preview=True

            )

        except Exception as edit_error:

            print(
                "[SUMMARY] HTML 发送失败：",
                repr(edit_error)
            )


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

        print(
            "[SUMMARY] 群聊总结失败"
        )

        print(
            repr(e)
        )

        print("=" * 60)


        try:

            await context.bot.edit_message_text(

                chat_id=chat_id,

                message_id=status_msg.message_id,

                text=(

                    "❌ 群聊总结失败\n\n"

                    f"{str(e)}"

                )

            )

        except Exception as edit_error:

            print(
                "[SUMMARY] 错误消息发送失败：",
                repr(edit_error)
            )


# ============================================================
# 普通消息处理
# ============================================================

async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return


    chat = update.effective_chat

    user = update.effective_user


    if not chat or not user:
        return


    chat_id = chat.id


    user_name = (

        user.first_name

        or user.username

        or "Anonymous"

    )


    # --------------------------------------------------------
    # Bot Username
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

        mention = (
            f"@{bot_username.lower()}"
        )


        is_mentioned = (

            mention
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

                and bot_username

                and (

                    replied_user.username.lower()
                    == bot_username.lower()

                )

            ):

                is_reply_to_bot = True


    # ========================================================
    # 图片处理
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


        processing_msg = (

            await update.message.reply_text(

                "🖼️ 正在看图……"

            )

        )


        try:

            reply = await analyze_image(

                target_photo,

                user_prompt,

                quote_context

            )


            await edit_ai_message(

                context,

                chat_id,

                processing_msg.message_id,

                reply

            )


        except Exception as e:

            print(
                "[IMAGE] 图片分析失败：",
                repr(e)
            )


            await context.bot.edit_message_text(

                chat_id=chat_id,

                message_id=processing_msg.message_id,

                text=(

                    "❌ 图片分析失败\n\n"

                    f"{str(e)}"

                )

            )


        return


    # ========================================================
    # 普通文字
    # ========================================================

    if not text.strip():
        return


    # ========================================================
    # 群聊记录
    # ========================================================

    if chat.type in (

        ChatType.GROUP,

        ChatType.SUPERGROUP

    ):

        if not text.startswith("/"):

            if is_meaningful_message(text):

                # ------------------------------------------------
                # 内存
                # ------------------------------------------------

                add_group_history(

                    chat_id,

                    user_name,

                    text,

                    update.message.message_id

                )


                # ------------------------------------------------
                # SQLite
                # ------------------------------------------------

                try:

                    save_message(

                        chat_id,

                        update.message.message_id,

                        user_name,

                        text

                    )

                except Exception as e:

                    print(
                        "[DATABASE] 保存消息失败：",
                        repr(e)
                    )


                # ------------------------------------------------
                # 自动总结
                # ------------------------------------------------

                try:

                    message_count = (

                        get_message_count(
                            chat_id
                        )

                    )


                    if (

                        message_count
                        >= AUTO_SUMMARY_MESSAGE_COUNT

                    ):

                        await auto_summary(

                            chat_id,

                            context

                        )

                except Exception as e:

                    print(
                        "[AUTO SUMMARY] 检查失败：",
                        repr(e)
                    )


    # ========================================================
    # 判断是否触发 AI
    # ========================================================

    if not (

        is_private

        or is_mentioned

        or is_reply_to_bot

    ):

        return


    # ========================================================
    # 去掉 @机器人
    # ========================================================

    prompt = text


    if bot_username:

        prompt = prompt.replace(

            f"@{bot_username}",

            ""

        )


    prompt = prompt.strip()


    # --------------------------------------------------------
    # 空问题
    # --------------------------------------------------------

    if not prompt:

        if quote_context:

            prompt = (
                "请分析一下我引用的这条消息。"
            )

        else:

            return


    # ========================================================
    # 发送处理中消息
    # ========================================================

    processing_msg = (

        await update.message.reply_text(

            "🤔"

        )

    )


    try:

        # ----------------------------------------------------
        # System Prompt
        # ----------------------------------------------------

        system_prompt = (

            "你是一个智能 Telegram AI 助手。\n\n"

            "你的回答会直接发送到 Telegram。\n\n"

            "要求：\n"

            "1. 使用自然、清晰的中文。\n"
            "2. 不要输出 HTML 标签。\n"
            "3. 可以使用 Markdown。\n"
            "4. 重要结论可以加粗。\n"
            "5. 可以使用 emoji 小标题。\n"
            "6. 不要把内容挤成一大段。\n"
            "7. 每个主要观点之间留一个空行。\n"
            "8. 列表使用 - 或 1. 2. 3.。\n"
            "9. 简单问题直接回答。\n"
            "10. 如果用户引用了消息，必须结合引用内容。\n"

        )


        # ----------------------------------------------------
        # Final Prompt
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


        # ----------------------------------------------------
        # Current Model
        # ----------------------------------------------------

        current_model = get_user_model(
            user.id
        )


        print("=" * 60)

        print(
            "[AI] 收到用户问题"
        )

        print(
            f"[AI] 用户：{user_name}"
        )

        print(
            f"[AI] 模型：{current_model}"
        )

        print(
            f"[AI] 问题：{prompt}"
        )

        print("=" * 60)


        # ----------------------------------------------------
        # AI Request
        # ----------------------------------------------------

        reply = ask_agnes(

            final_prompt,

            user_id=user.id,

            system_prompt=system_prompt

        )


        # ----------------------------------------------------
        # Send Reply
        # ----------------------------------------------------

        await edit_ai_message(

            context,

            chat_id,

            processing_msg.message_id,

            reply

        )


    except Exception as e:

        print("=" * 60)

        print(
            "[AI] 请求失败"
        )

        print(
            repr(e)
        )

        print("=" * 60)


        try:

            await context.bot.edit_message_text(

                chat_id=chat_id,

                message_id=processing_msg.message_id,

                text=(

                    "❌ 请求失败\n\n"

                    f"{str(e)}"

                )

            )

        except Exception as edit_error:

            print(
                "[AI] 错误消息发送失败：",
                repr(edit_error)
            )
