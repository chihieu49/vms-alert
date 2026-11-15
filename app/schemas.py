# -*- coding: utf-8 -*-
"""
Pydantic Schemas cho Request/Response Validation
"""
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field

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

