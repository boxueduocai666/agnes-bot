import logging
from aiogram import types
from aiogram.exceptions import TelegramBadRequest

async def handle_incoming_message(message: types.Message):
    """
    上一版稳定的消息处理逻辑：
    1. 包含基础的异常保护，防止单个请求崩溃导致整个 Bot 挂起。
    2. 针对 Markdown 解析失败做了优雅降级（若富文本格式出错，自动转为纯文本发送）。
    """
    try:
        # 获取用户输入的文本
        user_text = message.text or message.caption or ""
        if not user_text.strip():
            return

        # 提示正在处理（可选）
        processing_msg = await message.answer("正在思考中...")

        # TODO: 此处替换为你的 AI 调用、联网搜索或核心业务逻辑
        # 示例响应文本
        response_text = f"收到你的消息：{user_text}"

        # 尝试使用 Markdown 格式发送回复
        try:
            await message.answer(response_text, parse_mode="Markdown")
        except TelegramBadRequest:
            # 如果因为特殊字符（如未转义的 * 或 _）导致解析失败，降级为普通纯文本发送，绝对不崩溃
            await message.answer(response_text)
            
        # 删除“正在思考中...”的提示消息
        try:
            await processing_msg.delete()
        except Exception:
            pass

    except Exception as e:
        logging.error(f"处理消息时发生严重错误: {e}")
        try:
            await message.answer("服务暂时开小差了，请稍后再试。")
        except Exception:
            pass

