# -*- coding: utf-8 -*-
"""
Script xử lý và nạp 146 tàu cá thực tế của TX Ninh Hòa & H. Vạn Ninh
Đồng thời tạo file Excel chuẩn hóa
"""
import io
import csv
import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CSV_PATH = BASE_DIR / "data" / "danh_sach_tau_thuc_te_NHVN.csv"
EXCEL_PATH = BASE_DIR / "data" / "danh_sach_tau_thuc_te_NHVN.xlsx"

def parse_and_seed_real_vessels():
    # 1. Đọc nội dung CSV và tìm dòng Header thực sự
    with open(CSV_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()

    header_idx = -1
    for idx, line in enumerate(lines[:10]):
        if "Số ĐK" in line or "Số đăng ký" in line or "Chủ tàu" in line:
            header_idx = idx
            break

    if header_idx == -1:
        print("[ERROR] Không tìm thấy dòng Header trong file!")
        return

    csv_data = "".join(lines[header_idx:])
    df = pd.read_csv(io.StringIO(csv_data))
    
    # 2. Lưu thành file Excel chuẩn
    df.to_excel(EXCEL_PATH, index=False)
    print(f"[OK] Đã xuất file Excel chuẩn hóa: {EXCEL_PATH}")

    # 3. Nạp vào cơ sở dữ liệu vms_alert.db (FastAPI)
    import sys
    sys.path.insert(0, str(BASE_DIR))
    from app.database import SessionLocal, Base, engine
    from app.models import Vessel, VesselState, StateEnum
    from app.crud import create_or_update_vessel, normalize_plate
    from app.schemas import VesselCreate

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    total_imported = 0
    lost_count = 0
    normal_count = 0

    for _, row in df.iterrows():
        plate = str(row.get("Số ĐK", "")).strip()
        if not plate or plate.lower() == "nan":
            continue

        owner = str(row.get("Chủ tàu", "Chưa rõ")).strip()
        phone = str(row.get("Số điện thoại", "")).replace(".0", "").strip()
        address = str(row.get("Xã/Phường (Sau sáp nhập)", "")).strip()
        
        try:
            length = float(row.get("Lmax (m)") or 15.0)
        except Exception:
            length = 15.0

        try:
            power = float(row.get("Công suất (CV)") or 0.0)
        except Exception:
            power = 0.0

        device = str(row.get("Mã thiết bị VMS", "")).replace("nan", "").strip()
        status_text = str(row.get("Trạng thái VMS / GSTC", "")).strip()

        # Tạo / Cập nhật Vessel
        v_in = VesselCreate(
            plate_number=plate,
            ship_name=plate,
            owner_name=owner,
            owner_phone=phone,
            owner_address=address,
            chieudaitoanbo=length,
            congsuat=power,
            device_id=device
        )
        vessel = create_or_update_vessel(db, v_in)

        # Phân loại trạng thái ban đầu dựa trên cột Trạng thái VMS / GSTC thực tế
        state = vessel.state
        if state:
            is_lost = False
            # Kiểm tra các điều kiện mất tín hiệu
            if "mất kết nối" in status_text.lower() or "chưa lắp vms" in status_text.lower():
                is_lost = True
            elif "kết nối" in status_text.lower():
                # Xem kết nối bao nhiêu giờ trước
                try:
                    import re
                    m = re.search(r"kết nối\s+([\d\.]+)\s*h\s+trước", status_text.lower())
                    if m:
                        hours_ago = float(m.group(1))
                        if hours_ago > 2.0:
                            is_lost = True
                except Exception:
                    pass

            if is_lost:
                state.current_status = StateEnum.LOST_SIGNAL
                state.is_alerted = True
                state.consecutive_lost_cycles = 1
                lost_count += 1
            else:
                state.current_status = StateEnum.NORMAL
                state.is_alerted = False
                state.consecutive_lost_cycles = 0
                normal_count += 1

        total_imported += 1

    db.commit()
    db.close()

    print(f"\n=======================================================")
    print(f"[THÀNH CÔNG] ĐÃ NẠP {total_imported} TÀU CÁ THỰC TẾ VÀO HỆ THỐNG:")
    print(f"- Tàu hoạt động bình thường: {normal_count} tàu")
    print(f"- Tàu mất kết nối / không tín hiệu: {lost_count} tàu (Cần cảnh báo email)")
    print(f"=======================================================\n")

if __name__ == "__main__":
    parse_and_seed_real_vessels()

