# -*- coding: utf-8 -*-
"""
Keep-Alive Service (Chống Sleep khi deploy lên Render Free Tier)
Render Free Web Service tự động sleep sau 15 phút không có HTTP request.
Service này định kỳ mỗi 10 phút tự gửi HTTP GET tới endpoint /health của chính ứng dụng
để giữ tiến trình hoạt động 24/7 liên tục không bị gián đoạn chu kỳ giám sát VMS 2 giờ.
"""
import time
import threading
import requests
from app.config import settings

class KeepAliveService:
    def __init__(self):
        self.is_running = False
        self.thread = None
        self.interval_seconds = 10 * 60  # 10 phút / lần (dưới ngưỡng 15 phút của Render)

    def start(self):
        url = settings.RENDER_EXTERNAL_URL
        if not settings.KEEP_ALIVE_ENABLED:
            print("[KEEP-ALIVE] Tính năng Self-Ping đang bị tắt theo cấu hình.")
            return

        if not url:
            print("[KEEP-ALIVE] Không phát hiện RENDER_EXTERNAL_URL (Đang chạy Localhost). Không cần kích hoạt Self-Ping.")
            return

        if self.is_running:
            return

        self.is_running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        print(f"[KEEP-ALIVE] Đã kích hoạt cơ chế chống Sleep 24/7 cho Render URL: {url} (Chu kỳ {self.interval_seconds // 60} phút).")

    def stop(self):
        self.is_running = False
        print("[KEEP-ALIVE] Đã dừng Keep-Alive service.")

    def _loop(self):
        # Đợi 2 phút sau khi server khởi động xong rồi mới bắt đầu ping
        time.sleep(120)
        target_url = f"{settings.RENDER_EXTERNAL_URL}/health"

        while self.is_running:
            try:
                resp = requests.get(target_url, timeout=15)
                print(f"[KEEP-ALIVE] Ping thành công tới {target_url} (HTTP {resp.status_code}) - Giữ ứng dụng luôn hoạt động 24/7.")
            except Exception as e:
                print(f"[KEEP-ALIVE] Cảnh báo ping: {e}")

            # Chờ 10 phút
            for _ in range(self.interval_seconds):
                if not self.is_running:
                    break
                time.sleep(1)

keep_alive_service = KeepAliveService()

