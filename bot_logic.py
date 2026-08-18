import re
import html

from telegram import Update
from telegram.constants import ChatType
from telegram.ext import ContextTypes

from config import (
    MAX_HISTORY,
)

from database import (
    add_message,
    get_summary_messages,
)

from ai_logic import (
    ask_agnes,
    analyze_image,
    get_user_model,
)

from utils import (
    get_message_text,
    build_quote_context,
    search_web,
    edit_ai_message,
    format_ai_reply,
)


# ============================================================
# 获取机器人用户名
# ============================================================

async def get_bot_username(
    context
):

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
# /summary
# ============================================================

async def handle_summary(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return


    chat = update.effective_chat

    chat_id = chat.id


    history = get_summary_messages(
        chat_id,
        MAX_HISTORY
    )


    if len(history) < 3:

        await update.message.reply_text(

            "📝 目前有效聊天内容太少，"
            "至少需要 3 条有意义的消息才能进行总结。"

        )

        return


    status_msg = (
        await update.message.reply_text(
            "📝 正在生成群聊总结……"
        )
    )


    # ========================================================
    # Telegram 消息链接
    # ========================================================

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


    # ========================================================
    # 构造聊天记录
    # ========================================================

    formatted_lines = []


    for index, item in enumerate(
        history,
        start=1
    ):

        formatted_lines.append(

            f"[MSG:{index}]\n"
            f"用户：{item['user_name']}\n"
            f"内容：{item['text']}"

        )


    formatted_history = "\n\n".join(
        formatted_lines
    )


    # ========================================================
    # 总结 Prompt
    # ========================================================

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

        "8. 每个主要话题必须使用：\n"
        "[TOPIC:话题标题|MSG:消息编号]\n\n"

        "9. MSG 必须是真实存在的 MSG 编号。\n"

        "10. 每个话题只选择一条最有代表性的消息。\n"

        "11. 不要输出完整 URL。\n"

        "12. 不要生成“相关消息”区域。\n"

        "13. 无意义的打招呼、寒暄、"
        "单独的“你好”“早”等内容已经被过滤，"
        "不要主动把这些内容重新加入总结。\n\n"

        "最后使用：\n"
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


        result = response.strip()


        # ====================================================
        # 删除 AI 生成的 Telegram URL
        # ====================================================

        result = re.sub(

            r"https?://t\.me/[^\s)\]>]+",

            "",

            result

        )


        # ====================================================
        # 删除相关消息区域
        # ====================================================

        result = re.sub(

            r"\n*🔗\s*(?:\*\*)?"
            r"相关消息(?:\*\*)?.*",

            "",

            result,

            flags=re.S

        ).strip()


        # ====================================================
        # 处理 TOPIC
        # ====================================================

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


            msg_index = int(
                match.group(2)
            )


            if (

                msg_index < 1

                or msg_index > len(history)

            ):

                return (
                    f"📌 {topic_title}"
                )


            target_message = (
                history[msg_index - 1]
            )


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


        # ====================================================
        # 统一排版
        # ====================================================

        final_text = format_ai_reply(
            result
        )


        # ====================================================
        # 恢复 Topic 链接
        # ====================================================

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


        # ====================================================
        # 发送总结
        # ====================================================

        try:

            await context.bot.edit_message_text(

                chat_id=chat_id,

                message_id=status_msg.message_id,

                text=final_text,

                parse_mode="HTML",

                disable_web_page_preview=True

            )

        except Exception:

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


    if not user:
        return


    chat_id = chat.id


    user_name = (

        user.first_name

        or user.username

        or "Anonymous"

    )


    # ========================================================
    # Bot username
    # ========================================================

    bot_username = await get_bot_username(
        context
    )


    # ========================================================
    # 当前消息
    # ========================================================

    text = get_message_text(
        update.message
    )


    # ========================================================
    # 引用
    # ========================================================

    quote_context = build_quote_context(
        update.message
    )


    # ========================================================
    # 私聊
    # ========================================================

    is_private = (
        chat.type == ChatType.PRIVATE
    )


    # ========================================================
    # @机器人
    # ========================================================

    is_mentioned = False


    if bot_username and text:

        is_mentioned = (

            f"@{bot_username.lower()}"

            in text.lower()

        )


    # ========================================================
    # 回复机器人
    # ========================================================

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


    # ========================================================
    # 图片分析
    # ========================================================

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
    # 记录群聊历史
    # ========================================================

    if chat.type in (

        ChatType.GROUP,

        ChatType.SUPERGROUP

    ):

        if not text.startswith("/"):

            add_message(

                chat_id,

                user.id,

                user_name,

                text,

                update.message.message_id

            )


    # ========================================================
    # 触发条件
    # ========================================================

    if not (

        is_private

        or is_mentioned

        or is_reply_to_bot

    ):

        return


    # ========================================================
    # 去除 @机器人
    # ========================================================

    prompt = text


    if bot_username:

        prompt = prompt.replace(

            f"@{bot_username}",

            ""

        )


    prompt = prompt.strip()


    if not prompt:

        if quote_context:

            prompt = (
                "请分析一下我引用的这条消息。"
            )

        else:

            return


    # ========================================================
    # 🤔 思考状态
    # ========================================================

    processing_msg = (

        await update.message.reply_text(

            "🤔"

        )

    )


    try:

        # ----------------------------------------------------
        # 搜索工具
        #
        # 注意：搜索结果只是提供给 AI 的额外上下文，
        # 并不意味着当前模型本身拥有原生联网能力。
        # ----------------------------------------------------

        search_results = search_web(
            prompt
        )


        # ----------------------------------------------------
        # 系统提示词
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

            "10. 如果用户引用了消息，"
            "必须结合引用内容。\n"

            "11. 不要编造搜索结果。\n\n"

            "下面是搜索工具返回的信息。"
            "如果内容为空或者不可靠，不要强行使用。\n\n"

            "联网搜索结果：\n"
            "--------------------\n"

            f"{search_results}\n"

            "--------------------"

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


        # ----------------------------------------------------
        # 当前模型
        # ----------------------------------------------------

        current_model = get_user_model(
            user.id
        )


        print("=" * 60)
        print("[AI] 收到用户问题")
        print(f"[AI] 用户：{user_name}")
        print(f"[AI] 模型：{current_model}")
        print(f"[AI] 问题：{prompt}")
        print("=" * 60)


        # ----------------------------------------------------
        # 调用 AI
        # ----------------------------------------------------

        reply = ask_agnes(

            final_prompt,

            user_id=user.id,

            system_prompt=system_prompt

        )


        # ----------------------------------------------------
        # 删除 🤔 并替换成 AI 内容
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
