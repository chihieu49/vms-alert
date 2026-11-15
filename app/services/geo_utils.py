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
    Sinh tọa độ phân bố cụm tự nhiên theo góc cực (Fibonacci spiral polar distribution)
    quanh các vịnh, bến cá, cảng neo đậu thực tế của Ninh Hòa & Khánh Hòa:
    - Vịnh Vân Phong (Ninh Thủy - Ninh Diêm - Bến bãi TX Ninh Hòa)
    - Cảng cá Vạn Giã & Đầm Môn (Huyện Vạn Ninh)
    - Đầm Nha Phu & Vịnh Hòn Khói
    - Vịnh Nha Trang & Đảo Hòn Tre ngoài khơi
    - Ngư trường Biển Đông / Quần đảo Trường Sa
    Tuyệt đối NẰM NGOÀI BIỂN/VŨNG VỊNH, tự nhiên như bến đỗ thực tế, không xếp thành hàng kẻ chỉ!
    """
    clusters = [
        {"lat": 12.62, "lng": 109.32, "spread": 0.05},  # Vịnh Vân Phong (TX Ninh Hòa)
        {"lat": 12.76, "lng": 109.34, "spread": 0.06},  # Cảng cá Vạn Giã & Đầm Môn
        {"lat": 12.46, "lng": 109.28, "spread": 0.05},  # Đầm Nha Phu & Hòn Khói
        {"lat": 12.24, "lng": 109.32, "spread": 0.07},  # Vịnh Nha Trang ngoài khơi
        {"lat": 12.35, "lng": 109.85, "spread": 0.25}   # Ngư trường Biển Đông xa bờ
    ]

    c = clusters[index % len(clusters)]

    # Phân tán tự nhiên góc vàng 137.5 độ (Golden Angle)
    angle = (index * 137.5) * (math.pi / 180.0)
    r = math.sqrt((index % 25) + 1) * (c["spread"] / 5.0)

    lat = c["lat"] + (r * math.sin(angle))
    lng = c["lng"] + (r * 1.35 * math.cos(angle))

    return round(lat, 5), round(lng, 5)

