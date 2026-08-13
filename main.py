import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from bot_logic import handle_message, handle_summary

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

# 启动简易 HTTP 服务，响应 Render 健康检查，防止超时报错
def run_dummy_server():
    port = int(os.environ.get("PORT", 10000))
    class SimpleHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Bot is alive!")
        def log_message(self, format, *args):
            return

    server = HTTPServer(('0.0.0.0', port), SimpleHandler)
    server.serve_forever()

if __name__ == "__main__":
    # 开启后台保活服务
    threading.Thread(target=run_dummy_server, daemon=True).start()
    
    # 启动 Telegram 机器人（同时监听文本与图片消息）
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("summary", handle_summary))
    app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO, handle_message))
    
    print("Bot 已成功运行...")
    app.run_polling()
