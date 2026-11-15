# -*- coding: utf-8 -*-
"""
Auth Router - Đăng nhập, Đăng xuất, Quản lý người dùng
Hệ thống VMS Alert - Trạm Kiểm Ngư Ninh Hòa - Vạn Ninh
"""
from datetime import timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.auth import (
    COOKIE_NAME, ACCESS_TOKEN_EXPIRE_HOURS,
    create_access_token, get_current_user_from_request,
    require_authenticated, require_admin
)
from app.crud import (
    authenticate_user, get_all_users, get_user_by_id,
    create_user, update_user, delete_user,
    reset_user_password, change_own_password, count_admin_users,
    get_user_by_username
)
from app.schemas import UserCreate, UserUpdate, UserOut, PasswordChange, PasswordReset
from app.config import settings

# Khởi tạo router và template engine
router = APIRouter()
templates = Jinja2Templates(directory=str(settings.BASE_DIR / "app" / "templates"))


# ============================================================
# Dependency: lấy database session
# ============================================================

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============================================================
# Trang đăng nhập
# ============================================================

@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, error: str = None):
    """Hiển thị trang đăng nhập. Nếu đã đăng nhập thì redirect về trang chủ."""
    user = get_current_user_from_request(request)
    if user:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("login.html", {
        "request": request,
        "error": error
    })


@router.post("/login")
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    """Xử lý form đăng nhập, tạo JWT cookie HttpOnly rồi redirect về trang chủ"""
    user = authenticate_user(db, username=username.strip(), password=password)
    if not user:
        # Trả về trang đăng nhập kèm thông báo lỗi
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Tên đăng nhập hoặc mật khẩu không đúng. Vui lòng thử lại!"
        }, status_code=400)

    # Tạo JWT token
    token = create_access_token(
        data={"sub": user.username, "role": user.role.value, "full_name": user.full_name},
        expires_delta=timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    )

    # Redirect về trang chủ và đặt cookie HttpOnly
    response = RedirectResponse(url="/", status_code=302)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,          # Bảo vệ chống XSS - JS không đọc được
        max_age=ACCESS_TOKEN_EXPIRE_HOURS * 3600,
        samesite="lax",         # Bảo vệ chống CSRF
        secure=False            # Đặt True khi dùng HTTPS trên production
    )
    return response


# ============================================================
# Đăng xuất
# ============================================================

@router.get("/logout")
def logout():
    """Xóa cookie JWT và redirect về trang đăng nhập"""
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie(key=COOKIE_NAME)
    return response


# ============================================================
# Thông tin tài khoản cá nhân
# ============================================================

@router.get("/me")
def get_me(request: Request, db: Session = Depends(get_db)):
    """Trả về thông tin user đang đăng nhập"""
    current_user = require_authenticated(request)
    user = get_user_by_username(db, current_user["sub"])
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản")
    return UserOut.model_validate(user)


@router.post("/me/change-password")
def change_my_password(
    request: Request,
    body: PasswordChange,
    db: Session = Depends(get_db)
):
    """Đổi mật khẩu cá nhân - yêu cầu nhập mật khẩu hiện tại"""
    current_user = require_authenticated(request)
    user = get_user_by_username(db, current_user["sub"])
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản")

    success = change_own_password(db, user, body.current_password, body.new_password)
    if not success:
        raise HTTPException(status_code=400, detail="Mật khẩu hiện tại không đúng!")
    return {"message": "Đổi mật khẩu thành công!"}


# ============================================================
# Quản lý người dùng (ADMIN ONLY)
# ============================================================

@router.get("/api/users", response_model=List[UserOut])
def list_users(request: Request, db: Session = Depends(get_db)):
    """Lấy danh sách tất cả tài khoản người dùng (Chỉ Admin)"""
    require_admin(request)
    return get_all_users(db)


@router.post("/api/users", response_model=UserOut, status_code=201)
def create_new_user(
    request: Request,
    body: UserCreate,
    db: Session = Depends(get_db)
):
    """Tạo tài khoản mới (Chỉ Admin)"""
    current_user = require_admin(request)
    # Kiểm tra username đã tồn tại chưa
    if get_user_by_username(db, body.username):
        raise HTTPException(
            status_code=400,
            detail=f"Tên đăng nhập '{body.username}' đã tồn tại trong hệ thống!"
        )
    # Kiểm tra role hợp lệ
    valid_roles = ["admin", "supervisor", "viewer"]
    if body.role not in valid_roles:
        raise HTTPException(status_code=400, detail=f"Vai trò không hợp lệ. Chọn: {valid_roles}")

    user = create_user(
        db,
        username=body.username,
        full_name=body.full_name,
        password=body.password,
        role=body.role,
        created_by=current_user["sub"]
    )
    return UserOut.model_validate(user)


@router.put("/api/users/{user_id}", response_model=UserOut)
def update_user_info(
    user_id: int,
    request: Request,
    body: UserUpdate,
    db: Session = Depends(get_db)
):
    """Cập nhật thông tin user (Chỉ Admin)"""
    require_admin(request)
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản người dùng")

    # Kiểm tra role nếu có thay đổi
    if body.role is not None:
        valid_roles = ["admin", "supervisor", "viewer"]
        if body.role not in valid_roles:
            raise HTTPException(status_code=400, detail=f"Vai trò không hợp lệ. Chọn: {valid_roles}")

    updated = update_user(
        db, user,
        full_name=body.full_name,
        role=body.role,
        is_active=body.is_active
    )
    return UserOut.model_validate(updated)


@router.delete("/api/users/{user_id}")
def delete_user_account(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Xóa tài khoản người dùng (Chỉ Admin).
    Không cho phép xóa admin cuối cùng.
    """
    current_user = require_admin(request)
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản người dùng")

    # Không cho xóa chính mình
    if user.username == current_user["sub"]:
        raise HTTPException(status_code=400, detail="Bạn không thể tự xóa tài khoản của chính mình!")

    # Bảo vệ admin cuối cùng
    if user.role.value == "admin" and count_admin_users(db) <= 1:
        raise HTTPException(
            status_code=400,
            detail="Không thể xóa Admin duy nhất còn lại trong hệ thống!"
        )

    delete_user(db, user)
    return {"message": f"Đã xóa tài khoản '{user.username}' thành công!"}


@router.post("/api/users/{user_id}/reset-password")
def reset_password(
    user_id: int,
    request: Request,
    body: PasswordReset,
    db: Session = Depends(get_db)
):
    """Reset mật khẩu cho bất kỳ user nào (Chỉ Admin)"""
    require_admin(request)
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản người dùng")
    reset_user_password(db, user, body.new_password)
    return {"message": f"Đã reset mật khẩu cho tài khoản '{user.username}' thành công!"}
