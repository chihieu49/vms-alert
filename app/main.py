# -*- coding: utf-8 -*-
"""
VMS Alert System - Trạm Thủy Sản Ninh Hòa
Main Application: FastAPI + APScheduler + Jinja2 Templates
"""
import os
import webbrowser
import threading
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import engine, Base, SessionLocal
from app.api import dashboard_router, vessels_router, alerts_router
from app.services.scheduler import vms_scheduler
from app.services.keep_alive import keep_alive_service
from app.models import Vessel, VesselState, StateEnum
from app.crud import create_or_update_vessel
from app.schemas import VesselCreate

# Khởi tạo bảng Database
Base.metadata.create_all(bind=engine)

def seed_initial_vessels():
    """Tự động nạp danh sách tàu mẫu tỉnh Khánh Hòa (chiều dài >= 15m) nếu DB trống"""
    db = SessionLocal()
    count = db.query(Vessel).count()
    if count == 0:
        sample_ships = [
            {
                "plate_number": "KH-91234-TS",
                "ship_name": "Tàu Cá Ninh Thủy 01",
                "owner_name": "Nguyễn Văn Hùng",
                "owner_phone": "0913456789",
                "owner_address": "Tổ dân phố Mỹ Lương, Phường Ninh Thủy, TX Ninh Hòa, Khánh Hòa",
                "chieudaitoanbo": 18.5,
                "congsuat": 450.0,
                "device_id": "VMS-KH-001"
            },
            {
                "plate_number": "KH-96888-TS",
                "ship_name": "Tàu Cá Ninh Diêm 02",
                "owner_name": "Trần Văn Nam",
                "owner_phone": "0905123456",
                "owner_address": "Tổ dân phố Phú Thọ, Phường Ninh Diêm, TX Ninh Hòa, Khánh Hòa",
                "chieudaitoanbo": 16.8,
                "congsuat": 380.0,
                "device_id": "VMS-KH-002"
            },
            {
                "plate_number": "KH-92579-TS",
                "ship_name": "Tàu Cá Ninh Hải 03",
                "owner_name": "Lê Văn Tuấn",
                "owner_phone": "0988776655",
                "owner_address": "Tổ dân phố Đông Hải, Phường Ninh Hải, TX Ninh Hòa, Khánh Hòa",
                "chieudaitoanbo": 19.2,
                "congsuat": 520.0,
                "device_id": "VMS-KH-003"
            },
            {
                "plate_number": "KH-93456-TS",
                "ship_name": "Tàu Cá Ninh Thọ 04",
                "owner_name": "Phạm Quốc Cường",
                "owner_phone": "0935112233",
                "owner_address": "Thôn Lạc Bình, Xã Ninh Thọ, TX Ninh Hòa, Khánh Hòa",
                "chieudaitoanbo": 15.6,
                "congsuat": 320.0,
                "device_id": "VMS-KH-004"
            },
            {
                "plate_number": "KH-97890-TS",
                "ship_name": "Tàu Cá Vĩnh Lương 05",
                "owner_name": "Đặng Hữu Phước",
                "owner_phone": "0942889900",
                "owner_address": "Thôn Lương Sơn, Xã Vĩnh Lương, TP Nha Trang, Khánh Hòa",
                "chieudaitoanbo": 21.0,
                "congsuat": 650.0,
                "device_id": "VMS-KH-005"
            }
        ]
        for s in sample_ships:
            create_or_update_vessel(db, VesselCreate(**s))
        print(f"[INIT] Đã nạp sẵn {len(sample_ships)} tàu cá mẫu chiều dài >= 15m.")
    db.close()

seed_initial_vessels()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Khởi động APScheduler chu kỳ 2 giờ
    vms_scheduler.start()
    # Khởi động cơ chế chống Sleep khi deploy lên Render Free Tier
    keep_alive_service.start()
    yield
    # Dừng các dịch vụ khi shutdown
    keep_alive_service.stop()
    vms_scheduler.stop()

app = FastAPI(
    title="Hệ Thống Giám Sát Tàu Cá Chuyên Dụng (VMS Alert)",
    description="Theo dõi tàu cá chiều dài >= 15 mét, đối chiếu định kỳ mỗi 2 giờ với API Tổng cục Thủy sản, tự động cảnh báo email tới adminnhvn@gmail.com và giám sát trạng thái khắc phục.",
    version="2.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Template engine Jinja2
templates = Jinja2Templates(directory=str(settings.BASE_DIR / "app" / "templates"))

# Đăng ký các router
app.include_router(dashboard_router)
app.include_router(vessels_router)
app.include_router(alerts_router)

@app.get("/health")
def health_check():
    """Endpoint Health Check cho Render, UptimeRobot, Keep-Alive ping"""
    return {
        "status": "healthy",
        "service": "VMS Alert Ninh Hoa",
        "scheduler_running": vms_scheduler.is_running,
        "last_scan": vms_scheduler.last_scan_time.strftime("%Y-%m-%d %H:%M:%S") if vms_scheduler.last_scan_time else None,
        "next_scan": vms_scheduler.get_next_run_time()
    }

@app.get("/", response_class=HTMLResponse)
def index_page(request: Request):
    """Trang chủ Dashboard"""
    return templates.TemplateResponse("index.html", {"request": request})

def get_local_ip():
    """Lấy địa chỉ IP nội bộ của máy trong mạng LAN (Wi-Fi)"""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def start_server():
    import uvicorn
    host = settings.APP_HOST
    port = settings.APP_PORT
    local_ip = get_local_ip()
    is_cloud = bool(os.getenv("RENDER") or os.getenv("PORT"))

    # Tự động mở trình duyệt web khi chạy ở máy tính cá nhân (không mở trên cloud)
    if not is_cloud:
        def open_browser():
            import time
            time.sleep(1.5)
            webbrowser.open(f"http://localhost:{port}")
        threading.Thread(target=open_browser, daemon=True).start()

    print(f"\n===============================================================================")
    print(f"       HỆ THỐNG GIÁM SÁT TÀU CÁ CHUYÊN DỤNG (VMS ALERT) - TRẠM NINH HÒA")
    print(f"===============================================================================")
    print(f"[*] Máy chủ đang chạy tại cổng: {port}")
    print(f"[*] 1. Truy cập trên máy này:                http://localhost:{port}")
    if local_ip != "127.0.0.1":
        print(f"[*] 2. Truy cập từ ĐIỆN THOẠI / MÁY KHÁC:    http://{local_ip}:{port}")
    if settings.RENDER_EXTERNAL_URL:
        print(f"[*] 3. Truy cập từ Internet qua Render:      {settings.RENDER_EXTERNAL_URL}")
    print(f"[*] Email nhận cảnh báo tự động:             {settings.ADMIN_EMAIL}")
    print(f"[*] Chu kỳ kiểm tra định kỳ:                 {settings.POLL_INTERVAL_MINUTES} phút (mỗi 2 giờ)")
    print(f"[*] Tài liệu API tương tác Swagger:          http://localhost:{port}/docs")
    print(f"===============================================================================\n")

    uvicorn.run("app.main:app", host=host, port=port, reload=False)

if __name__ == "__main__":
    start_server()

