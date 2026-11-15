# -*- coding: utf-8 -*-
"""
Cấu hình ứng dụng từ file .env
"""
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

class Settings:
    # 1. GSTC API
    GSTC_API_URL: str = os.getenv(
        "GSTC_API_URL",
        "https://gstc.tongcucthuysan.gov.vn/Map/exportdanhsachtau?exportFields=latitude%26longitude%26time%26ship_state%26distanceToboundy%26agency%26deviceId%26serial%26imei%26shipName%26ownerName%26captainName%26plate_number%26captainAddress%26ownerAddress%26captainPhone%26ownerPhone%26businessName%26chieudaitoanbo%26congsuat&sign=56ef085f11644f96b6b5f6200f71197c&ship_state=&state_kind="
    )
    GSTC_COOKIE: str = os.getenv("GSTC_COOKIE", "")
    USE_MOCK_DATA: bool = os.getenv("USE_MOCK_DATA", "false").lower() in ("true", "1", "yes")

    # 2. Ngưỡng chu kỳ
    POLL_INTERVAL_MINUTES: int = int(os.getenv("POLL_INTERVAL_MINUTES", "120"))
    LOST_SIGNAL_THRESHOLD_MINUTES: int = int(os.getenv("LOST_SIGNAL_THRESHOLD_MINUTES", "120"))
    MIN_VESSEL_LENGTH_METERS: float = float(os.getenv("MIN_VESSEL_LENGTH_METERS", "15.0"))

    # 3. Kênh Email
    ADMIN_EMAIL: str = os.getenv("ADMIN_EMAIL", "adminnhvn@gmail.com")
    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM_NAME: str = os.getenv("SMTP_FROM_NAME", "Trạm Kiểm Ngư Ninh Hòa - Vạn Ninh - Giám Sát VMS")

    # 4. Kênh mở rộng: Telegram / Zalo / SMS
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")
    ZALO_OA_ACCESS_TOKEN: str = os.getenv("ZALO_OA_ACCESS_TOKEN", "")
    SMS_API_KEY: str = os.getenv("SMS_API_KEY", "")

    # 5. Database & Server
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR}/data/vms_alert.db")
    # Bind 0.0.0.0 để cho phép thiết bị khác (điện thoại/máy khác trong mạng LAN) và Cloud (Render) truy cập
    APP_HOST: str = os.getenv("APP_HOST", "0.0.0.0")
    # Render tự cấp biến môi trường PORT; nếu không có thì dùng APP_PORT hoặc mặc định 8000
    APP_PORT: int = int(os.getenv("PORT") or os.getenv("APP_PORT") or "8000")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")

    # URL công khai khi deploy lên Render (Render tự sinh biến RENDER_EXTERNAL_URL)
    RENDER_EXTERNAL_URL: str = os.getenv("RENDER_EXTERNAL_URL", os.getenv("APP_URL", "")).rstrip("/")
    # Tự động ping để ngăn Render Free Web Service sleep sau 15 phút
    KEEP_ALIVE_ENABLED: bool = os.getenv("KEEP_ALIVE_ENABLED", "true").lower() in ("true", "1", "yes")

    BASE_DIR: Path = BASE_DIR
    DATA_DIR: Path = BASE_DIR / "data"
    EMAILS_DIR: Path = BASE_DIR / "data" / "sent_emails"

settings = Settings()

# Đảm bảo các thư mục tồn tại
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
settings.EMAILS_DIR.mkdir(parents=True, exist_ok=True)

