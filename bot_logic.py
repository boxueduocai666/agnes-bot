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

    target_photo = update.message.reply_to_message.photo[-1]

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

        # ------------------------------------------------
        # 从 Telegram 下载图片
        # ------------------------------------------------

        photo_file = await target_photo.get_file()

        image_bytes = await photo_file.download_as_bytearray()

        # ------------------------------------------------
        # 转换为 Base64
        # ------------------------------------------------

        image_base64 = base64.b64encode(
            bytes(image_bytes)
        ).decode("utf-8")

        # ------------------------------------------------
        # 使用 Data URL
        #
        # Agnes 不需要再访问 Telegram
        # ------------------------------------------------

        image_url = (
            f"data:image/jpeg;base64,{image_base64}"
        )

        # ------------------------------------------------
        # 清理用户问题
        # ------------------------------------------------

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

        # ------------------------------------------------
        # 返回 Telegram
        # ------------------------------------------------

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
