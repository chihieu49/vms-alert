# -*- coding: utf-8 -*-
"""
Pydantic Schemas cho Request/Response Validation
Bao gồm: Vessel, AlertHistory, Dashboard, User, Token
"""
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field


# ============================================================
# Schemas: User Management & Authentication
# ============================================================

class UserBase(BaseModel):
    username: str = Field(..., description="Tên đăng nhập (duy nhất)")
    full_name: str = Field(..., description="Họ và tên đầy đủ")
    role: str = Field("viewer", description="Vai trò: admin / supervisor / viewer")
    is_active: bool = Field(True, description="Tài khoản đang hoạt động hay bị khóa")


class UserCreate(UserBase):
    """Schema tạo user mới (kèm mật khẩu)"""
    password: str = Field(..., min_length=6, description="Mật khẩu tối thiểu 6 ký tự")


class UserUpdate(BaseModel):
    """Schema cập nhật thông tin user (không thay mật khẩu)"""
    full_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


class UserOut(BaseModel):
    """Schema trả về thông tin user (không bao gồm mật khẩu)"""
    id: int
    username: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime] = None
    created_by: Optional[str] = None

    class Config:
        from_attributes = True


class PasswordChange(BaseModel):
    """Schema đổi mật khẩu cá nhân"""
    current_password: str = Field(..., description="Mật khẩu hiện tại")
    new_password: str = Field(..., min_length=6, description="Mật khẩu mới (tối thiểu 6 ký tự)")


class PasswordReset(BaseModel):
    """Schema reset mật khẩu (Admin dùng)"""
    new_password: str = Field(..., min_length=6, description="Mật khẩu mới")


class Token(BaseModel):
    """Schema JWT token response"""
    access_token: str
    token_type: str = "bearer"

class VesselBase(BaseModel):
    plate_number: str = Field(..., description="Số đăng ký tàu (ví dụ: KH-91234-TS)")
    ship_name: Optional[str] = None
    owner_name: str = Field(..., description="Tên chủ tàu")
    owner_phone: Optional[str] = Field(None, description="Số điện thoại chủ tàu")
    owner_address: Optional[str] = Field(None, description="Địa chỉ chủ tàu")
    captain_name: Optional[str] = None
    captain_phone: Optional[str] = None
    captain_address: Optional[str] = None
    chieudaitoanbo: float = Field(15.0, ge=15.0, description="Chiều dài lớn nhất Lmax (phải >= 15m)")
    congsuat: Optional[float] = 0.0
    device_id: Optional[str] = None
    imei: Optional[str] = None

class VesselCreate(VesselBase):
    pass

class VesselStateOut(BaseModel):
    current_status: str
    is_alerted: bool
    consecutive_lost_cycles: int
    last_signal_time: Optional[datetime] = None
    last_latitude: Optional[float] = None
    last_longitude: Optional[float] = None
    last_checked_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class VesselOut(VesselBase):
    id: int
    created_at: datetime
    updated_at: datetime
    state: Optional[VesselStateOut] = None

    class Config:
        from_attributes = True

class AlertHistoryOut(BaseModel):
    id: int
    plate_number: str
    event_type: str
    channel: str
    recipient: str
    consecutive_cycles: int
    details: Optional[str] = None
    delivery_status: str
    sent_at: datetime

    class Config:
        from_attributes = True

class DashboardSummaryOut(BaseModel):
    total_vessels: int
    normal_vessels: int
    lost_vessels: int
    recovered_vessels: int
    last_scan_time: Optional[str] = None
    next_scan_time: Optional[str] = None
    scheduler_running: bool

