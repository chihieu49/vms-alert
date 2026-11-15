# -*- coding: utf-8 -*-
import io
import sys
import os
import pandas as pd

# Thêm thư mục gốc vms_alert vào PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.services.vms_client import vms_client
from app.services.scheduler import vms_scheduler
from app.database import SessionLocal, Base, engine
from app.models import Vessel, VesselState
from app.crud import create_or_update_vessel
from app.schemas import VesselCreate

def test_sync():
    # Tạo bảng nếu chưa có
    Base.metadata.create_all(bind=engine)

    # Đảm bảo có 2 tàu này trong DB
    db = SessionLocal()
    v1_obj = VesselCreate(
        plate_number="KH-91288-TS",
        ship_name="KH-91288-TS",
        owner_name="LÊ NGỌC THẢO",
        owner_phone="0333696771",
        owner_address="Phường Bắc Nha Trang (NHVN)",
        chieudaitoanbo=21.65,
        congsuat=1135
    )
    v2_obj = VesselCreate(
        plate_number="KH-92079-TS",
        ship_name="KH-92079-TS",
        owner_name="DƯƠNG VĂN MINH",
        owner_phone="0982635331",
        owner_address="Phường Bắc Nha Trang (NHVN)",
        chieudaitoanbo=26.1,
        congsuat=1218
    )
    create_or_update_vessel(db, v1_obj)
    create_or_update_vessel(db, v2_obj)
    db.close()
    print("--- 1. TẠO FILE EXCEL GIẢ LẬP XUẤT TỪ BẢN ĐỒ TỔNG CỤC THỦY SẢN ---")
    gstc_sample_data = [
        {
            "Số ĐK": "KH-91288-TS",
            "Vĩ độ": 12.58421,
            "Kinh độ": 109.31456,
            "Thời gian": "2026-11-15 10:30:00",
            "Trạng thái": "Đang hoạt động",
            "Khoảng cách": 12.5,
            "Chủ tàu": "LÊ NGỌC THẢO",
            "Điện thoại": "0333696771",
            "Địa chỉ": "Phường Bắc Nha Trang (NHVN)"
        },
        {
            "Số ĐK": "KH-92079-TS",
            "Vĩ độ": "12°35'20.4\"N",
            "Kinh độ": "109°22'15.6\"E",
            "Thời gian": "2026-11-15 10:15:00",
            "Trạng thái": "Đang neo đậu",
            "Khoảng cách": 5.2,
            "Chủ tàu": "DƯƠNG VĂN MINH",
            "Điện thoại": "0982635331",
            "Địa chỉ": "Phường Bắc Nha Trang (NHVN)"
        }
    ]

    df = pd.DataFrame(gstc_sample_data)
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    file_bytes = buf.getvalue()

    print("--- 2. KIỂM TRA PARSE DỮ LIỆU TỪ FILE XUẤT GSTC ---")
    records, msg = vms_client.parse_gstc_file(file_bytes, "GSTC_Map_Export_Test.xlsx")
    print("Thông báo:", msg)
    print("Số lượng bản ghi:", len(records))
    assert len(records) == 2, "Lỗi: Không parse đủ 2 bản ghi"
    for r in records:
        print(f"  [+] Tàu: {r['plate_number']} | Lat: {r['latitude']} | Lng: {r['longitude']} | Time: {r['time']}")

    print("\n--- 3. ĐỒNG BỘ TỌA ĐỘ VÀO HỆ THỐNG VÀ CƠ SỞ DỮ LIỆU ---")
    res = vms_scheduler.process_gstc_records(records, source_name="Test GSTC Map Export")
    print("Kết quả Scheduler:", res)

    print("\n--- 4. KIỂM TRA TRONG CƠ SỞ DỮ LIỆU SQLITE ---")
    db = SessionLocal()
    v1 = db.query(Vessel).filter(Vessel.plate_number == "KH-91288-TS").first()
    assert v1 is not None, "Không tìm thấy tàu KH-91288-TS"
    assert v1.state is not None, "Tàu chưa có state"
    print(f"  KH-91288-TS: Lat={v1.state.last_latitude}, Lng={v1.state.last_longitude}, Time={v1.state.last_signal_time}, Status={v1.state.current_status}")
    assert abs(v1.state.last_latitude - 12.58421) < 0.0001, "Sai vĩ độ KH-91288-TS"
    assert abs(v1.state.last_longitude - 109.31456) < 0.0001, "Sai kinh độ KH-91288-TS"

    v2 = db.query(Vessel).filter(Vessel.plate_number == "KH-92079-TS").first()
    assert v2 is not None, "Không tìm thấy tàu KH-92079-TS"
    print(f"  KH-92079-TS: Lat={v2.state.last_latitude}, Lng={v2.state.last_longitude}, Time={v2.state.last_signal_time}, Status={v2.state.current_status}")
    assert v2.state.last_latitude is not None and v2.state.last_longitude is not None, "Không parse được DMS sang Decimal"

    db.close()
    print("\n>>> TẤT CẢ CÁC BÀI TEST ĐỒNG BỘ TỌA ĐỘ GSTC ĐÃ ĐẠT 100%! <<<")

if __name__ == "__main__":
    test_sync()
