# -*- coding: utf-8 -*-
"""
CRUD Operations cho Cơ sở dữ liệu
"""
import re
from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from app.models import Vessel, VesselState, VesselPosition, AlertHistory, StateEnum, ChannelEnum
from app.schemas import VesselCreate

def normalize_plate(plate: str) -> str:
    """Chuẩn hóa biển số tàu dạng KH-xxxxx-TS"""
    if not plate:
        return ""
    p = str(plate).strip().upper()
    p = p.replace(" - ", "-").replace(" -", "-").replace("- ", "-").replace(" ", "-")
    while "--" in p:
        p = p.replace("--", "-")
    return p

def normalize_vietnam_phone(val) -> str:
    """
    Chuẩn hóa số điện thoại gồm đúng 10 số bắt đầu bằng số 0:
    - Bỏ khoảng trắng, dấu chấm, dấu gạch ngang, đuôi .0 của Excel.
    - Nếu 9 số thiếu 0 đầu (ví dụ: 333696771 -> 0333696771; 982635331 -> 0982635331).
    - Nếu có mã quốc gia 84 (ví dụ: 84982635331 -> 0982635331).
    """
    if not val:
        return ""
    s = str(val).strip().replace(".0", "")
    digits = re.sub(r"[^\d]", "", s)
    if not digits:
        return ""
    if digits.startswith("84") and len(digits) == 11:
        digits = "0" + digits[2:]
    elif len(digits) == 9 and not digits.startswith("0"):
        digits = "0" + digits
    return digits

def get_vessel_by_plate(db: Session, plate: str) -> Optional[Vessel]:
    norm = normalize_plate(plate)
    return db.query(Vessel).filter(Vessel.plate_number == norm).first()

def get_all_vessels(db: Session) -> List[Vessel]:
    return db.query(Vessel).order_by(Vessel.plate_number.asc()).all()

def create_or_update_vessel(db: Session, vessel_in: VesselCreate) -> Vessel:
    norm_plate = normalize_plate(vessel_in.plate_number)
    phone_clean = normalize_vietnam_phone(vessel_in.owner_phone)
    capt_phone_clean = normalize_vietnam_phone(vessel_in.captain_phone)
    vessel = get_vessel_by_plate(db, norm_plate)
    
    if vessel:
        # Cập nhật thông tin
        vessel.ship_name = vessel_in.ship_name or vessel.ship_name
        vessel.owner_name = vessel_in.owner_name
        vessel.owner_phone = phone_clean or vessel.owner_phone
        vessel.owner_address = vessel_in.owner_address or vessel.owner_address
        vessel.captain_name = vessel_in.captain_name or vessel.captain_name
        vessel.captain_phone = capt_phone_clean or vessel.captain_phone
        vessel.captain_address = vessel_in.captain_address or vessel.captain_address
        vessel.chieudaitoanbo = vessel_in.chieudaitoanbo
        vessel.congsuat = vessel_in.congsuat or vessel.congsuat
        vessel.device_id = vessel_in.device_id or vessel.device_id
        vessel.imei = vessel_in.imei or vessel.imei
        vessel.updated_at = datetime.utcnow()
    else:
        # Tạo mới
        vessel = Vessel(
            plate_number=norm_plate,
            ship_name=vessel_in.ship_name or norm_plate,
            owner_name=vessel_in.owner_name,
            owner_phone=phone_clean,
            owner_address=vessel_in.owner_address,
            captain_name=vessel_in.captain_name,
            captain_phone=capt_phone_clean,
            captain_address=vessel_in.captain_address,
            chieudaitoanbo=vessel_in.chieudaitoanbo,
            congsuat=vessel_in.congsuat,
            device_id=vessel_in.device_id,
            imei=vessel_in.imei
        )
        db.add(vessel)
        db.flush()

        # Tạo kèm trạng thái ban đầu
        state = VesselState(
            vessel_id=vessel.id,
            current_status=StateEnum.NORMAL,
            is_alerted=False,
            consecutive_lost_cycles=0
        )
        db.add(state)

    db.commit()
    db.refresh(vessel)
    return vessel

def delete_vessel(db: Session, plate: str) -> bool:
    norm_plate = normalize_plate(plate)
    vessel = get_vessel_by_plate(db, norm_plate)
    if vessel:
        db.delete(vessel)
        db.commit()
        return True
    return False

def add_position_record(db: Session, vessel_id: int, lat: float, lng: float, recorded_at: datetime, ship_state: str = None, distance_to_boundary: float = None):
    pos = VesselPosition(
        vessel_id=vessel_id,
        latitude=lat,
        longitude=lng,
        recorded_at=recorded_at,
        ship_state=ship_state,
        distance_to_boundary=distance_to_boundary
    )
    db.add(pos)
    db.commit()
    return pos

def record_alert_event(
    db: Session,
    vessel_id: Optional[int],
    plate_number: str,
    event_type: str,
    channel: ChannelEnum = ChannelEnum.EMAIL,
    recipient: str = "adminnhvn@gmail.com",
    consecutive_cycles: int = 0,
    details: str = "",
    status: str = "SENT"
):
    alert = AlertHistory(
        vessel_id=vessel_id,
        plate_number=plate_number,
        event_type=event_type,
        channel=channel,
        recipient=recipient,
        consecutive_cycles=consecutive_cycles,
        details=details,
        delivery_status=status,
        sent_at=datetime.utcnow()
    )
    db.add(alert)
    db.commit()
    return alert

def get_recent_alerts(db: Session, limit: int = 50) -> List[AlertHistory]:
    return db.query(AlertHistory).order_by(AlertHistory.id.desc()).limit(limit).all()

