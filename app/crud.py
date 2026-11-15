# -*- coding: utf-8 -*-
"""
CRUD Operations cho Cơ sở dữ liệu VMS Alert
Trạm Kiểm Ngư Ninh Hòa - Vạn Ninh • Chi cục Thủy sản và Biển đảo tỉnh Khánh Hòa
Bao gồm: Quản lý tàu cá, Lịch sử tọa độ, Cảnh báo, Thống kê ngày, Quản lý tài khoản người dùng
"""
import re
from typing import List, Optional, Dict, Any
from datetime import datetime, date
from sqlalchemy.orm import Session
from sqlalchemy import or_, func

from app.models import (
    Vessel, VesselState, VesselPosition, AlertHistory, DailyStats,
    StateEnum, ChannelEnum, User, UserRole
)
from app.schemas import VesselCreate
from app.auth import hash_password, verify_password


# ============================================================
# Tiện ích Chuẩn hóa Dữ liệu
# ============================================================

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


# ============================================================
# Quản lý Tàu Cá (Vessel CRUD)
# ============================================================

def get_vessel_by_plate(db: Session, plate: str) -> Optional[Vessel]:
    """Tìm tàu cá theo số đăng ký đã chuẩn hóa"""
    norm = normalize_plate(plate)
    return db.query(Vessel).filter(Vessel.plate_number == norm).first()


def get_all_vessels(db: Session) -> List[Vessel]:
    """Lấy danh sách tất cả tàu cá đang theo dõi"""
    return db.query(Vessel).order_by(Vessel.plate_number.asc()).all()


def get_vessels_with_pagination(
    db: Session,
    skip: int = 0,
    limit: int = 20,
    search: Optional[str] = None,
    status_filter: Optional[str] = None
) -> Dict[str, Any]:
    """
    Lấy danh sách tàu cá hỗ trợ phân trang, tìm kiếm và lọc trạng thái kết nối
    """
    query = db.query(Vessel)

    if search and search.strip():
        s = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Vessel.plate_number.ilike(s),
                Vessel.ship_name.ilike(s),
                Vessel.owner_name.ilike(s),
                Vessel.owner_phone.ilike(s),
                Vessel.owner_address.ilike(s)
            )
        )

    if status_filter and status_filter.upper() != "ALL":
        query = query.join(VesselState, Vessel.id == VesselState.vessel_id, isouter=True)\
                     .filter(VesselState.current_status == status_filter.upper())

    total = query.count()
    items = query.order_by(Vessel.plate_number.asc()).offset(skip).limit(limit).all()

    return {
        "items": items,
        "total": total,
        "skip": skip,
        "limit": limit
    }


def create_or_update_vessel(db: Session, vessel_in: VesselCreate) -> Vessel:
    """Thêm mới hoặc cập nhật thông tin tàu cá (chiều dài >= 15m)"""
    norm_plate = normalize_plate(vessel_in.plate_number)
    phone_clean = normalize_vietnam_phone(vessel_in.owner_phone)
    capt_phone_clean = normalize_vietnam_phone(vessel_in.captain_phone)
    vessel = get_vessel_by_plate(db, norm_plate)
    
    if vessel:
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
    """Xóa tàu cá và toàn bộ trạng thái / lịch sử liên quan (cascade)"""
    norm_plate = normalize_plate(plate)
    vessel = get_vessel_by_plate(db, norm_plate)
    if vessel:
        db.delete(vessel)
        db.commit()
        return True
    return False


# ============================================================
# Lịch sử Tọa độ & Nhật ký Cảnh báo
# ============================================================

def add_position_record(
    db: Session,
    vessel_id: int,
    lat: float,
    lng: float,
    recorded_at: datetime,
    ship_state: str = None,
    distance_to_boundary: float = None
):
    """Ghi nhận một điểm tọa độ trong hành trình tàu"""
    pos = VesselPosition(
        vessel_id=vessel_id,
        latitude=lat,
        longitude=lng,
        recorded_at=recorded_at,
        ship_state=ship_state,
        distance_to_boundary=distance_to_boundary
    )
    db.add(pos)
    db.flush()
    return pos


def get_vessel_track_history(db: Session, vessel_id: int, limit: int = 100) -> List[VesselPosition]:
    """Lấy danh sách các điểm tọa độ hành trình gần nhất của tàu"""
    return db.query(VesselPosition)\
             .filter(VesselPosition.vessel_id == vessel_id)\
             .order_by(VesselPosition.recorded_at.desc())\
             .limit(limit)\
             .all()


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
    """Ghi nhận sự kiện cảnh báo hoặc phục hồi vào nhật ký"""
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
    db.flush()
    return alert


def get_recent_alerts(db: Session, limit: int = 50, skip: int = 0) -> List[AlertHistory]:
    """Lấy danh sách cảnh báo gần đây"""
    return db.query(AlertHistory)\
             .order_by(AlertHistory.sent_at.desc())\
             .offset(skip)\
             .limit(limit)\
             .all()


def get_alerts_count(db: Session) -> int:
    """Đếm tổng số bản ghi cảnh báo"""
    return db.query(AlertHistory).count()


# ============================================================
# Thống kê Hàng ngày (DailyStats)
# ============================================================

def upsert_daily_stats(
    db: Session,
    stat_date: date,
    total: int,
    lost: int,
    recovered: int,
    normal: int,
    emails_sent: int = 0
):
    """Lưu hoặc cập nhật thống kê ngày phục vụ vẽ biểu đồ xu hướng 7 ngày"""
    existing = db.query(DailyStats).filter(DailyStats.stat_date == stat_date).first()
    if existing:
        existing.total_vessels = total
        existing.lost_count = lost
        existing.recovered_count = recovered
        existing.normal_count = normal
        existing.alert_emails_sent += emails_sent
        existing.updated_at = datetime.utcnow()
    else:
        stat = DailyStats(
            stat_date=stat_date,
            total_vessels=total,
            lost_count=lost,
            recovered_count=recovered,
            normal_count=normal,
            alert_emails_sent=emails_sent
        )
        db.add(stat)
    db.flush()


def get_last_7_days_stats(db: Session) -> List[DailyStats]:
    """Lấy dữ liệu thống kê 7 ngày gần nhất cho biểu đồ dashboard"""
    return db.query(DailyStats)\
             .order_by(DailyStats.stat_date.asc())\
             .limit(7)\
             .all()


# ============================================================
# Quản lý Người Dùng & Phân Quyền (User Management CRUD)
# ============================================================

def get_user_by_username(db: Session, username: str) -> Optional[User]:
    """Tìm người dùng theo username"""
    if not username:
        return None
    return db.query(User).filter(User.username == username.strip().lower()).first()


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    """Tìm người dùng theo ID"""
    return db.query(User).filter(User.id == user_id).first()


def get_all_users(db: Session) -> List[User]:
    """Lấy danh sách tất cả người dùng"""
    return db.query(User).order_by(User.created_at.desc()).all()


def count_admin_users(db: Session) -> int:
    """Đếm số lượng tài khoản có quyền ADMIN và đang active"""
    return db.query(User).filter(User.role == UserRole.ADMIN, User.is_active == True).count()


def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    """Xác thực đăng nhập bằng username và password"""
    user = get_user_by_username(db, username)
    if not user or not user.is_active:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    
    user.last_login = datetime.utcnow()
    db.commit()
    db.refresh(user)
    return user


def create_user(
    db: Session,
    username: str,
    full_name: str,
    password: str,
    role: str = "viewer",
    created_by: Optional[str] = None
) -> User:
    """Tạo người dùng mới với mật khẩu băm chuẩn an toàn"""
    role_enum = UserRole.VIEWER
    r = str(role).lower()
    if r == "admin":
        role_enum = UserRole.ADMIN
    elif r == "supervisor":
        role_enum = UserRole.SUPERVISOR

    user = User(
        username=username.strip().lower(),
        full_name=full_name.strip(),
        hashed_password=hash_password(password),
        role=role_enum,
        is_active=True,
        created_by=created_by,
        created_at=datetime.utcnow()
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_user(
    db: Session,
    user: User,
    full_name: Optional[str] = None,
    role: Optional[str] = None,
    is_active: Optional[bool] = None
) -> User:
    """Cập nhật thông tin người dùng"""
    if full_name is not None and full_name.strip():
        user.full_name = full_name.strip()
    if role is not None:
        r = str(role).lower()
        if r == "admin":
            user.role = UserRole.ADMIN
        elif r == "supervisor":
            user.role = UserRole.SUPERVISOR
        elif r == "viewer":
            user.role = UserRole.VIEWER
    if is_active is not None:
        user.is_active = is_active

    db.commit()
    db.refresh(user)
    return user


def delete_user(db: Session, user: User) -> bool:
    """Xóa tài khoản người dùng"""
    db.delete(user)
    db.commit()
    return True


def reset_user_password(db: Session, user: User, new_password: str) -> bool:
    """Reset mật khẩu người dùng"""
    user.hashed_password = hash_password(new_password)
    db.commit()
    return True


def change_own_password(db: Session, user: User, current_password: str, new_password: str) -> bool:
    """Đổi mật khẩu người dùng sau khi kiểm tra mật khẩu cũ"""
    if not verify_password(current_password, user.hashed_password):
        return False
    user.hashed_password = hash_password(new_password)
    db.commit()
    return True


def seed_default_users(db: Session):
    """Khởi tạo các tài khoản người dùng mặc định khi khởi động ứng dụng nếu bảng trống"""
    count = db.query(User).count()
    if count == 0:
        default_accounts = [
            {
                "username": "admin",
                "full_name": "Quản Trị Viên Hệ Thống",
                "password": "admin@nhvn2026",
                "role": "admin",
                "created_by": "hệ thống"
            },
            {
                "username": "giamsat",
                "full_name": "Kíp Trực Giám Sát VMS",
                "password": "gs@nhvn2026",
                "role": "supervisor",
                "created_by": "hệ thống"
            },
            {
                "username": "khach",
                "full_name": "Cán Bộ Tra Cứu (Chỉ Xem)",
                "password": "khach@nhvn2026",
                "role": "viewer",
                "created_by": "hệ thống"
            }
        ]
        for acc in default_accounts:
            create_user(
                db=db,
                username=acc["username"],
                full_name=acc["full_name"],
                password=acc["password"],
                role=acc["role"],
                created_by=acc["created_by"]
            )
        print(f"[AUTH] Đã khởi tạo thành công {len(default_accounts)} tài khoản mặc định (admin, giamsat, khach).")
