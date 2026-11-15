# -*- coding: utf-8 -*-
import sys
import os
from pathlib import Path

# Thêm thư mục vms_alert vào PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi.testclient import TestClient
from app.main import app
from app.services.scheduler import vms_scheduler
from app.database import SessionLocal
from app.models import Vessel, VesselState, AlertHistory, StateEnum

client = TestClient(app)

print("=" * 70)
print("KIỂM THỬ HỆ THỐNG VMS ALERT (FASTAPI + APSCHEDULER + SQLALCHEMY)")
print("=" * 70)

# 1. Test GET /
res_home = client.get("/")
print(f"1. GET / (Trang chủ Dashboard): Status {res_home.status_code}")
assert res_home.status_code == 200

# 2. Test GET /api/dashboard/summary
res_summary = client.get("/api/dashboard/summary")
print(f"2. GET /api/dashboard/summary: Status {res_summary.status_code}")
print(f"   Dữ liệu: {res_summary.json()}")
assert res_summary.status_code == 200

# 3. Test GET /api/vessels
res_vessels = client.get("/api/vessels")
print(f"3. GET /api/vessels: Status {res_vessels.status_code}, số tàu: {len(res_vessels.json())}")
assert res_vessels.status_code == 200

# 4. Test Kích hoạt Chu kỳ đối chiếu VMS (Scan Cycle 1)
print("\n--- 4. CHU KỲ QUÉT ĐỐI CHIẾU 1 (PHÁT HIỆN TÀU MẤT TÍN HIỆU) ---")
res_scan = client.post("/api/dashboard/scan-now")
print("Kết quả quét:", res_scan.json())
assert res_scan.status_code == 200

# 5. Kiểm tra danh sách cảnh báo đã lưu
res_alerts = client.get("/api/alerts/history")
print(f"\n5. GET /api/alerts/history: {len(res_alerts.json())} sự kiện được ghi nhận:")
for a in res_alerts.json()[:3]:
    print(f"   [{a['sent_at']}] {a['event_type']}: {a['plate_number']} | Đến: {a['recipient']}")

# 6. Test Cơ Chế Giám Sát Trạng Thái Khắc Phục (Recovery)
print("\n--- 6. TEST CƠ CHẾ KHẮC PHỤC (RECOVERY: TỰ ĐỘNG CHẤM DỨT THÔNG BÁO) ---")
res_rec = client.post("/api/alerts/simulate-recovery")
print("Kết quả phục hồi:", res_rec.json())
assert res_rec.status_code == 200

# 7. Kiểm tra lại trạng thái sau phục hồi
res_summary_after = client.get("/api/dashboard/summary")
print("Thống kê sau phục hồi:", res_summary_after.json())

# 8. Xem danh sách email đã lưu
res_emails = client.get("/api/alerts/sent-emails")
print(f"\n8. GET /api/alerts/sent-emails: {len(res_emails.json())} bức thư cảnh báo đã lưu trong kho:")
if res_emails.json():
    em = res_emails.json()[0]
    print(f"   - Gửi tới: {em['to']}")
    print(f"   - Tiêu đề: {em['subject']}")
    print(f"   - Số tàu vi phạm: {em['vessel_count']}")

print("\n" + "=" * 70)
print("TẤT CẢ KIỂM THỬ THÀNH CÔNG 100%!")
print("=" * 70)

