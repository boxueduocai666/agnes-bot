import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# --- 1. 专门用来应付 Render 端口检查的轻量网页服务 ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running!")
    
    def log_message(self, format, *args):
        # 屏蔽 HTTP 请求日志，避免刷屏
        pass

def start_dummy_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

# 在后台线程中启动网页服务（这样就不会阻塞你的 Bot 运行了）
threading.Thread(target=start_dummy_server, daemon=True).start()
