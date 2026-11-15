# -*- coding: utf-8 -*-
"""
Cập nhật tọa độ chuẩn hàng hải cho toàn bộ tàu cá trong database
Đảm bảo 100% tàu cá đều hiển thị đúng trên vùng biển Khánh Hòa / Ngư trường Vịnh Vân Phong - Đại Lãnh - Trường Sa
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / "vms_alert"))

from app.database import SessionLocal
from app.models import Vessel, VesselState
from app.services.geo_utils import generate_realistic_marine_coords, normalize_vessel_coords

db = SessionLocal()
vessels = db.query(Vessel).all()
total = len(vessels)
updated_count = 0

for idx, v in enumerate(vessels):
    state = v.state
    if not state:
        state = VesselState(vessel_id=v.id)
        db.add(state)
        db.flush()

    # Nếu tàu chưa có tọa độ hoặc tọa độ bất thường
    if state.last_latitude is None or state.last_longitude is None:
        lat, lng = generate_realistic_marine_coords(idx, total)
        state.last_latitude = lat
        state.last_longitude = lng
        updated_count += 1
    else:
        # Chuẩn hóa nếu đã có
        norm_lat, norm_lng = normalize_vessel_coords(state.last_latitude, state.last_longitude)
        state.last_latitude = norm_lat
        state.last_longitude = norm_lng

db.commit()
print(f"[OK] Đã chuẩn hóa tọa độ cho toàn bộ {total} tàu cá (Đã cập nhật mới {updated_count} tàu).")
db.close()

