# -*- coding: utf-8 -*-
"""
Bộ kiểm thử toàn diện Hệ Thống Giám Sát Tàu Cá VMS Alert
Trạm Kiểm Ngư Ninh Hòa - Vạn Ninh • Chi cục Thủy sản và Biển đảo tỉnh Khánh Hòa
Bao gồm: Xác thực phân quyền, Quản lý tài khoản, Đối chiếu chu kỳ, Xuất Excel, Biểu đồ thống kê
"""
import sys
import os
from pathlib import Path

# Thêm thư mục vms_alert vào PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

print("=" * 75)
print("KIỂM THỬ HỆ THỐNG VMS ALERT (FASTAPI + APSCHEDULER + SQLALCHEMY + JWT AUTH)")
print("=" * 75)

# 1. Test Kiểm tra Chuyển hướng khi chưa đăng nhập
res_unauth = client.get("/", follow_redirects=False)
print(f"1. GET / (Chưa đăng nhập): Status {res_unauth.status_code} (Chuyển hướng về {res_unauth.headers.get('location')})")
assert res_unauth.status_code == 302
assert "/login" in res_unauth.headers.get("location")

# 2. Test GET /login (Trang đăng nhập)
res_login_page = client.get("/login")
print(f"2. GET /login: Status {res_login_page.status_code}")
assert res_login_page.status_code == 200
assert "TRẠM KIỂM NGƯ NINH HÒA - VẠN NINH" in res_login_page.text

# 3. Test Đăng nhập bằng tài khoản Quản Trị Viên (Admin)
res_login = client.post("/login", data={"username": "admin", "password": "admin@nhvn2026"}, follow_redirects=False)
token_cookie = res_login.cookies.get("vms_access_token")
print(f"3. POST /login (Tài khoản Admin): Status {res_login.status_code}, Cookie HttpOnly: {bool(token_cookie)}")
assert res_login.status_code == 302
assert token_cookie is not None

# Thiết lập Cookie cho client
client.cookies.set("vms_access_token", token_cookie)

# 4. Test GET / sau khi đăng nhập
res_home = client.get("/")
print(f"4. GET / (Sau khi đăng nhập): Status {res_home.status_code}")
assert res_home.status_code == 200

# 5. Test GET /api/dashboard/summary
res_summary = client.get("/api/dashboard/summary")
print(f"5. GET /api/dashboard/summary: Status {res_summary.status_code}")
print(f"   Dữ liệu: {res_summary.json()}")
assert res_summary.status_code == 200

# 6. Test GET /api/dashboard/stats-chart (Biểu đồ 7 ngày)
res_chart = client.get("/api/dashboard/stats-chart")
chart_data = res_chart.json()
print(f"6. GET /api/dashboard/stats-chart: Status {res_chart.status_code}, {len(chart_data.get('labels', []))} ngày")
assert res_chart.status_code == 200
assert len(chart_data.get("labels", [])) == 7

# 7. Test GET /api/vessels (151 tàu)
res_vessels = client.get("/api/vessels")
print(f"7. GET /api/vessels: Status {res_vessels.status_code}, số tàu: {len(res_vessels.json())}")
assert res_vessels.status_code == 200
assert len(res_vessels.json()) >= 150

# 8. Test GET /api/vessels/paginated (Phân trang 20 tàu)
res_pag = client.get("/api/vessels/paginated?skip=0&limit=20")
print(f"8. GET /api/vessels/paginated: Status {res_pag.status_code}, tổng số: {res_pag.json().get('total')}")
assert res_pag.status_code == 200
assert len(res_pag.json().get("items", [])) <= 20

# 9. Test Xuất Excel Danh Sách Tàu Cá
res_exp_vessels = client.get("/api/vessels/export-excel")
print(f"9. GET /api/vessels/export-excel: Status {res_exp_vessels.status_code}, dung lượng: {len(res_exp_vessels.content)} bytes")
assert res_exp_vessels.status_code == 200
assert len(res_exp_vessels.content) > 1000

# 10. Test Quản Lý Người Dùng (Admin API)
res_users = client.get("/api/users")
print(f"10. GET /api/users (Danh sách tài khoản): Status {res_users.status_code}, số tài khoản: {len(res_users.json())}")
assert res_users.status_code == 200

# 11. Test Chu kỳ Quét Đối Chiếu VMS
print("\n--- 11. CHU KỲ QUÉT ĐỐI CHIẾU VMS (PHÁT HIỆN TÀU MẤT TÍN HIỆU) ---")
res_scan = client.post("/api/dashboard/scan-now")
print("Kết quả quét:", res_scan.json().get("result", {}).get("total"), "tàu được quét")
assert res_scan.status_code == 200

# 12. Test Cơ chế Tự Động Chấm Dứt Cảnh Báo (Recovery)
print("\n--- 12. TEST CƠ CHẾ PHỤC HỒI (RECOVERY: TỰ ĐỘNG CHẤM DỨT CẢNH BÁO) ---")
res_rec = client.post("/api/alerts/simulate-recovery")
print("Kết quả phục hồi:", res_rec.json())
assert res_rec.status_code == 200

# 13. Test Xuất Excel Báo Cáo Cảnh Báo
res_exp_alerts = client.get("/api/alerts/export-excel")
print(f"13. GET /api/alerts/export-excel: Status {res_exp_alerts.status_code}, dung lượng: {len(res_exp_alerts.content)} bytes")
assert res_exp_alerts.status_code == 200

print("\n" + "=" * 75)
print("TẤT CẢ 13/13 BÀI KIỂM THỬ ĐÃ VƯỢT QUA 100% THÀNH CÔNG!")
print("=" * 75)
