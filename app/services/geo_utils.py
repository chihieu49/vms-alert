# -*- coding: utf-8 -*-
"""
Geo Utilities - Xử lý và chuẩn hóa tọa độ hàng hải VMS
- Chuyển đổi định dạng tọa độ đa dạng (Decimal, DMS, NMEA, tiếng Việt dấu phẩy)
- Tự động phát hiện và sửa lỗi đảo Kinh độ / Vĩ độ
- Kiểm tra tọa độ trong phạm vi vùng biển Việt Nam & Khánh Hòa
- Cung cấp tọa độ ngư trường thực tế ngoài khơi cho tàu cá Ninh Hòa - Vạn Ninh
"""
import re
import math
from typing import Optional, Tuple

# Phạm vi vùng biển đặc quyền kinh tế Việt Nam (EEZ)
VN_LAT_MIN = 6.0
VN_LAT_MAX = 23.5
VN_LNG_MIN = 102.0
VN_LNG_MAX = 118.0

# Phạm vi vùng biển Khánh Hòa / Ninh Hòa / Vạn Ninh / Quần đảo Trường Sa
KH_LAT_MIN = 8.5
KH_LAT_MAX = 13.5
KH_LNG_MIN = 109.30  # Ngoài mép biển, hoàn toàn không chạm đất liền
KH_LNG_MAX = 115.0

def parse_coordinate(val) -> Optional[float]:
    """
    Chuyển đổi các định dạng tọa độ thành số thực thập phân (Decimal Degrees)
    Hỗ trợ:
    - float/int: 12.5123
    - str có dấu phẩy: "12,5123"
    - Độ phút giây (DMS): 12°30'45"N hoặc 12 30.75 N
    - NMEA format: 1230.4567 (12 độ, 30.4567 phút)
    """
    if val is None:
        return None

    if isinstance(val, (int, float)):
        if math.isnan(val):
            return None
        return float(val)

    s = str(val).strip().replace(",", ".")
    if not s or s.lower() in ("nan", "none", "null", ""):
        return None

    # 1. Thử parse trực tiếp số thực
    try:
        return float(s)
    except ValueError:
        pass

    # 2. Xử lý dạng Độ Phút Giây: vd "12°34'56.7\"N" hoặc "109°20'30.5\"E"
    dms_match = re.search(r"(\d+)[\s°dD]+(\d+)[\s\'mM]+([\d\.]+)[\s\"sS]*([NSEWnsew]?)", s)
    if dms_match:
        deg = float(dms_match.group(1))
        minute = float(dms_match.group(2))
        sec = float(dms_match.group(3))
        direction = dms_match.group(4).upper()

        dec = deg + (minute / 60.0) + (sec / 3600.0)
        if direction in ("S", "W"):
            dec = -dec
        return dec

    # 3. Xử lý dạng Độ và Phút thập phân: vd "12° 34.567' N"
    dm_match = re.search(r"(\d+)[\s°dD]+([\d\.]+)[\s\'mM]*([NSEWnsew]?)", s)
    if dm_match:
        deg = float(dm_match.group(1))
        minute = float(dm_match.group(2))
        direction = dm_match.group(3).upper()

        dec = deg + (minute / 60.0)
        if direction in ("S", "W"):
            dec = -dec
        return dec

    # 4. Xử lý định dạng NMEA (ddmm.mmmm cho Lat hoặc dddmm.mmmm cho Lng)
    digits_only = re.sub(r"[^\d\.]", "", s)
    try:
        num = float(digits_only)
        if num > 1000:
            deg = math.floor(num / 100)
            mins = num - (deg * 100)
            dec = deg + (mins / 60.0)
            if "S" in s.upper() or "W" in s.upper():
                dec = -dec
            return dec
    except Exception:
        pass

    return None

def normalize_vessel_coords(raw_lat, raw_lng) -> Tuple[Optional[float], Optional[float]]:
    """
    Chuẩn hóa cặp tọa độ Lat/Lng và tự động sửa lỗi đảo vị trí:
    - Vĩ độ tại Việt Nam luôn nằm trong khoảng ~ 6°N đến 23°N.
    - Kinh độ tại Việt Nam luôn nằm trong khoảng ~ 102°E đến 118°E.
    - Nếu Lat > 50 và Lng < 30 -> Tọa độ đang bị hoán đổi (Lat bị gán Kinh độ, Lng bị gán Vĩ độ)!
    """
    lat = parse_coordinate(raw_lat)
    lng = parse_coordinate(raw_lng)

    if lat is None or lng is None:
        return None, None

    # Phát hiện bị đảo: Kinh độ (~109) bị nhầm thành Vĩ độ, Vĩ độ (~12) bị nhầm thành Kinh độ
    if (lat > 50.0 and lng < 35.0):
        lat, lng = lng, lat

    # Kiểm tra tính hợp lệ trên địa cầu (-90 <= lat <= 90 và -180 <= lng <= 180)
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lng <= 180.0):
        return None, None

    # Đảm bảo vĩ độ dương (Bắc) và kinh độ dương (Đông) ở Biển Đông
    lat = abs(lat)
    lng = abs(lng)

    return round(lat, 5), round(lng, 5)

def is_in_vietnam_waters(lat: float, lng: float) -> bool:
    """Kiểm tra tọa độ có nằm trong vùng biển Việt Nam không"""
    if lat is None or lng is None:
        return False
    return (VN_LAT_MIN <= lat <= VN_LAT_MAX) and (VN_LNG_MIN <= lng <= VN_LNG_MAX)

def generate_realistic_marine_coords(index: int, total: int = 146) -> Tuple[float, float]:
    """
    Sinh tọa độ thực tế trên các ngư trường đánh bắt xa bờ truyền thống của tàu cá Khánh Hòa / Ninh Hòa / Vạn Ninh:
    - Vịnh Vân Phong & Đầm Môn: 12.60°N - 12.80°N, 109.32°E - 109.50°E
    - Bãi cạn Hòn Khói ngoài khơi: 12.50°N - 12.65°N, 109.35°E - 109.60°E
    - Vùng biển Vịnh Nha Phu - Đảo Khỉ ngoài khơi: 12.35°N - 12.48°N, 109.32°E - 109.55°E
    - Ngư trường xa bờ (Thềm lục địa Khánh Hòa, bãi ngầm Phúc Tần, Hoàng Sa - Trường Sa): 11.5°N - 13.5°N, 109.60°E - 112.50°E
    Tuyệt đối NẰM NGOÀI BIỂN, không bị cắm vào đất liền Ninh Hòa!
    """
    # Phân nhóm ngư trường thực tế
    zone = index % 5
    offset = (index * 7) % 100 / 100.0  # Tạo độ phân tán tự nhiên

    if zone == 0:
        # Ngư trường Vịnh Vân Phong - Mũi Đôi - Hòn Cổ (TX Ninh Hòa & H. Vạn Ninh)
        lat = 12.62 + (offset * 0.16)
        lng = 109.35 + (offset * 0.18)
    elif zone == 1:
        # Ngư trường Đảo Hòn Lớn - Hòn Tai - Vịnh Nha Trang ngoài khơi
        lat = 12.38 + (offset * 0.15)
        lng = 109.36 + (offset * 0.22)
    elif zone == 2:
        # Ngư trường Xã Đại Lãnh - Vũng Rô ngoài khơi
        lat = 12.82 + (offset * 0.18)
        lng = 109.42 + (offset * 0.25)
    elif zone == 3:
        # Vùng biển đánh bắt cá ngừ đại dương xa bờ (Cách bờ 30 - 80 hải lý)
        lat = 12.20 + (offset * 0.90)
        lng = 109.75 + (offset * 0.95)
    else:
        # Vùng biển thềm lục địa Khánh Hòa - Quần đảo Trường Sa
        lat = 11.80 + (offset * 1.10)
        lng = 110.20 + (offset * 1.40)

    return round(lat, 5), round(lng, 5)

