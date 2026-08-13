import os
import logging
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.exceptions import TelegramBadRequest

# 配置日志输出，方便在 Render 后台看排错信息
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    level=logging.INFO
)

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("未检测到 BOT_TOKEN 环境变量，请在后台配置！")

bot = Bot(token=TOKEN)
dp = Dispatcher()

@dp.message()
async def robust_message_handler(message: types.Message):
    """
    全链路容错的消息处理函数：
    无论中间的搜索、大模型调用或 Telegram API 怎么报错，
    绝不让整个进程退出（Exited with status 1）。
    """
    try:
        user_text = message.text or message.caption or ""
        if not user_text.strip():
            return

        logging.info(f"收到来自用户 {message.from_user.id} 的消息: {user_text}")

        # 发送处理中提示
        processing_msg = await message.answer("正在思考中...")

        # ==================== 你的核心业务逻辑区域 ====================
        # TODO: 这里放入你的联网搜索、大模型生成或总结代码
        response_text = f"收到你的指令：{user_text}"
        # ==============================================================

        # 1. 尝试用 Markdown 格式发送回复
        try:
            await message.answer(response_text, parse_mode="Markdown")
        except TelegramBadRequest:
            # 如果因为特殊字符（如未转义的 * 或 _）导致解析失败，降级为纯文本安全发送
            await message.answer(response_text)
        except Exception as e:
            logging.error(f"发送回复时发生网络或API错误: {e}")

        # 2. 尝试删除“正在思考中...”的提示消息（加 try 保护，防止消息已被删导致报错）
        try:
            await processing_msg.delete()
        except Exception:
            pass

    except Exception as e:
        # 捕捉所有意料之外的严重错误，确保 bot 活着
        logging.error(f"处理消息时发生未捕获的异常: {e}")
        try:
            await message.answer("系统开小差了，请稍后再试。")
        except Exception:
            pass

async def main():
    logging.info("Telegram Bot 正在启动长轮询...")
    # 清除启动前堆积的旧 Update，防止冲突
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot 已手动停止。")

