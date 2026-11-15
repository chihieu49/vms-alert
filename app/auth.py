# -*- coding: utf-8 -*-
"""
Module Authentication - JWT (PyJWT) + PBKDF2-SHA256 Password Hashing
Hệ thống VMS Alert - Trạm Kiểm Ngư Ninh Hòa - Vạn Ninh • Chi cục Thủy sản và Biển đảo tỉnh Khánh Hòa
"""
import hmac
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional

import jwt
from fastapi import Request, HTTPException, status
from app.config import settings

# ============================================================
# Cấu hình bảo mật
# ============================================================
SECRET_KEY = getattr(settings, "SECRET_KEY", "vms-nhvn-2026-secure-jwt-key-khanh-hoa-fishery-999")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = getattr(settings, "ACCESS_TOKEN_EXPIRE_HOURS", 8)
COOKIE_NAME = "vms_access_token"  # Tên cookie HttpOnly lưu JWT

# ============================================================
# Hàm tiện ích mật khẩu (PBKDF2-HMAC-SHA256 chuẩn OWASP)
# ============================================================

def hash_password(plain_password: str) -> str:
    """Băm mật khẩu dạng PBKDF2-HMAC-SHA256 với salt ngẫu nhiên 16 bytes"""
    if not plain_password:
        return ""
    salt = secrets.token_hex(16)
    iterations = 100_000
    hash_bytes = hashlib.pbkdf2_hmac(
        "sha256",
        plain_password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations
    )
    return f"pbkdf2:sha256:{iterations}${salt}${hash_bytes.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Xác minh mật khẩu plain với chuỗi băm PBKDF2"""
    if not plain_password or not hashed_password:
        return False
    try:
        parts = hashed_password.split("$")
        if len(parts) == 3 and parts[0].startswith("pbkdf2:sha256:"):
            iterations = int(parts[0].split(":")[-1])
            salt = parts[1]
            stored_hex = parts[2]
            computed_bytes = hashlib.pbkdf2_hmac(
                "sha256",
                plain_password.encode("utf-8"),
                salt.encode("utf-8"),
                iterations
            )
            return hmac.compare_digest(computed_bytes.hex(), stored_hex)
        # Hỗ trợ plain text fallback cho tài khoản khởi tạo cũ (nếu có)
        return hmac.compare_digest(plain_password, hashed_password)
    except Exception:
        return False


# ============================================================
# Hàm tiện ích JWT (PyJWT)
# ============================================================

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Tạo JWT access token với thời hạn tùy chỉnh hoặc mặc định 8 giờ"""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS))
    to_encode.update({"exp": expire})
    token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    if isinstance(token, bytes):
        token = token.decode("utf-8")
    return token


def decode_access_token(token: str) -> Optional[dict]:
    """Giải mã JWT token, trả về None nếu không hợp lệ hoặc hết hạn"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except Exception:
        return None


# ============================================================
# Lấy thông tin user hiện tại từ Request (cookie hoặc header)
# ============================================================

def get_current_user_from_request(request: Request) -> Optional[dict]:
    """
    Đọc cookie 'vms_access_token' từ request (hoặc header Authorization: Bearer <token>)
    và giải mã JWT. Trả về dict payload (username, role, full_name) hoặc None nếu chưa đăng nhập.
    """
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        # Thử lấy từ Authorization header
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1].strip()

    if not token:
        return None
    return decode_access_token(token)


def require_authenticated(request: Request) -> dict:
    """Dependency: Yêu cầu user đã đăng nhập. Raise HTTP 401 nếu chưa đăng nhập."""
    user = get_current_user_from_request(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Chưa đăng nhập. Vui lòng đăng nhập để tiếp tục.",
        )
    return user


def require_supervisor_or_admin(request: Request) -> dict:
    """Dependency: Yêu cầu role SUPERVISOR hoặc ADMIN (được quét, tải báo cáo)."""
    user = require_authenticated(request)
    role = (user.get("role") or "").lower()
    if role not in ("supervisor", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản của bạn chỉ có quyền xem (Viewer), không được thực hiện thao tác này.",
        )
    return user


def require_admin(request: Request) -> dict:
    """Dependency: Yêu cầu role ADMIN (Toàn quyền quản trị)."""
    user = require_authenticated(request)
    role = (user.get("role") or "").lower()
    if role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ quản trị viên (Admin) mới có quyền thực hiện thao tác này.",
        )
    return user
