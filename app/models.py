# -*- coding: utf-8 -*-
"""
SQLAlchemy Models
Bao gồm: Vessel, VesselState, VesselPosition, AlertHistory, DailyStats
"""
import enum
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime,
    ForeignKey, Text, Enum, Date, Index
)
from sqlalchemy.orm import relationship
from app.database import Base

class StateEnum(str, enum.Enum):
    NORMAL = "NORMAL"              # Hoạt động bình thường
    LOST_SIGNAL = "LOST_SIGNAL"    # Mất tín hiệu sau chu kỳ 2 giờ (Cảnh báo)
    RECOVERED = "RECOVERED"        # Đã khắc phục (Chấm dứt cảnh báo)

class ChannelEnum(str, enum.Enum):
    EMAIL = "EMAIL"
    TELEGRAM = "TELEGRAM"
    ZALO = "ZALO"
    SMS = "SMS"

class UserRole(str, enum.Enum):
    ADMIN = "admin"          # Toàn quyền: thêm/sửa/xóa tàu, quản lý người dùng, quét hệ thống
    SUPERVISOR = "supervisor" # Giám sát viên: xem bản đồ + danh sách tàu, kích hoạt quét thủ công, xuất báo cáo
    VIEWER = "viewer"        # Chỉ xem: tra cứu dashboard, bản đồ, danh sách tàu

class User(Base):
    """Bảng người dùng và tài khoản truy cập hệ thống"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    full_name = Column(String(100), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.VIEWER, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    created_by = Column(String(50), nullable=True)

class Vessel(Base):
    """Bảng danh sách tàu cá cần giám sát (chiều dài >= 15 mét)"""
    __tablename__ = "vessels"

    id = Column(Integer, primary_key=True, index=True)
    plate_number = Column(String(50), unique=True, index=True, nullable=False) # Số đăng ký
    ship_name = Column(String(100), nullable=True)                              # Tên tàu
    owner_name = Column(String(100), nullable=False)                            # Tên chủ tàu
    owner_phone = Column(String(50), nullable=True)                             # Số điện thoại chủ tàu
    owner_address = Column(String(255), nullable=True)                          # Địa chỉ chủ tàu
    captain_name = Column(String(100), nullable=True)                           # Tên thuyền trưởng
    captain_phone = Column(String(50), nullable=True)                           # Số điện thoại thuyền trưởng
    captain_address = Column(String(255), nullable=True)                        # Địa chỉ thuyền trưởng
    chieudaitoanbo = Column(Float, default=15.0)                                # Chiều dài lớn nhất (Lmax >= 15m)
    congsuat = Column(Float, default=0.0)                                       # Công suất (CV)
    device_id = Column(String(100), nullable=True)                             # Mã thiết bị VMS
    imei = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    state = relationship("VesselState", back_populates="vessel", uselist=False, cascade="all, delete-orphan")
    positions = relationship("VesselPosition", back_populates="vessel", cascade="all, delete-orphan", order_by="desc(VesselPosition.recorded_at)")
    alerts = relationship("AlertHistory", back_populates="vessel", cascade="all, delete-orphan")

class VesselState(Base):
    """Trạng thái hiện tại của tàu sau các chu kỳ giám sát 2 giờ"""
    __tablename__ = "vessel_states"

    id = Column(Integer, primary_key=True, index=True)
    vessel_id = Column(Integer, ForeignKey("vessels.id"), unique=True, nullable=False)
    current_status = Column(Enum(StateEnum), default=StateEnum.NORMAL, nullable=False)
    is_alerted = Column(Boolean, default=False)               # Đang trong trạng thái đã gửi email cảnh báo
    consecutive_lost_cycles = Column(Integer, default=0)       # Số chu kỳ mất kết nối liên tục
    last_signal_time = Column(DateTime, nullable=True)         # Thời gian vị trí gần nhất nhận từ VMS
    last_latitude = Column(Float, nullable=True)
    last_longitude = Column(Float, nullable=True)
    last_checked_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    vessel = relationship("Vessel", back_populates="state")

# Thêm index cho VesselState.current_status để tăng hiệu năng truy vấn
Index("ix_vessel_states_current_status", VesselState.current_status)

class VesselPosition(Base):
    """Lịch sử hành trình tọa độ vị trí thực tế của tàu từ VMS"""
    __tablename__ = "vessel_positions"

    id = Column(Integer, primary_key=True, index=True)
    vessel_id = Column(Integer, ForeignKey("vessels.id"), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    recorded_at = Column(DateTime, nullable=False)             # Thời điểm thiết bị ghi nhận
    ship_state = Column(String(100), nullable=True)            # Trạng thái di chuyển từ GSTC
    distance_to_boundary = Column(Float, nullable=True)        # Khoảng cách tới ranh giới biển
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship
    vessel = relationship("Vessel", back_populates="positions")

class AlertHistory(Base):
    """Nhật ký cảnh báo và giám sát trạng thái khắc phục"""
    __tablename__ = "alert_histories"

    id = Column(Integer, primary_key=True, index=True)
    vessel_id = Column(Integer, ForeignKey("vessels.id"), nullable=True)
    plate_number = Column(String(50), nullable=False)
    event_type = Column(String(50), nullable=False)            # 'ALERT_SENT', 'RECOVERED_DISCONTINUE'
    channel = Column(Enum(ChannelEnum), default=ChannelEnum.EMAIL)
    recipient = Column(String(200), default="adminnhvn@gmail.com")
    consecutive_cycles = Column(Integer, default=0)
    details = Column(Text, nullable=True)
    delivery_status = Column(String(50), default="SENT")       # 'SENT', 'SAVED_DRAFT', 'FAILED'
    sent_at = Column(DateTime, default=datetime.utcnow)

    # Relationship
    vessel = relationship("Vessel", back_populates="alerts")

# Thêm index cho AlertHistory.sent_at để tăng hiệu năng truy vấn lịch sử theo ngày
Index("ix_alert_histories_sent_at", AlertHistory.sent_at)
Index("ix_alert_histories_plate_number", AlertHistory.plate_number)

class DailyStats(Base):
    """Thống kê hàng ngày: tổng tàu, số mất kết nối, số phục hồi"""
    __tablename__ = "daily_stats"

    id = Column(Integer, primary_key=True, index=True)
    stat_date = Column(Date, nullable=False, unique=True, index=True)  # Ngày thống kê
    total_vessels = Column(Integer, default=0)                          # Tổng số tàu trong danh sách
    lost_count = Column(Integer, default=0)                             # Số tàu mất kết nối trong ngày
    recovered_count = Column(Integer, default=0)                        # Số tàu phục hồi trong ngày
    normal_count = Column(Integer, default=0)                           # Số tàu bình thường
    alert_emails_sent = Column(Integer, default=0)                      # Số email cảnh báo đã gửi
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
