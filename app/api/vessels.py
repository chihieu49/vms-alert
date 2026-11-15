# -*- coding: utf-8 -*-
"""
Vessels API
Quản lý danh sách tàu cá, Import Excel / CSV / JSON (Lọc chiều dài >= 15m)
"""
import io
import json
from datetime import datetime
import pandas as pd
from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Response, Query, Request
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Vessel, VesselState, StateEnum
from app.schemas import VesselCreate, VesselOut
from app.crud import (
    get_all_vessels, get_vessel_by_plate, create_or_update_vessel,
    delete_vessel, normalize_plate, normalize_vietnam_phone,
    get_vessels_with_pagination, get_vessel_track_history
)
from app.auth import get_current_user_from_request, require_supervisor_or_admin, require_admin
from app.config import settings
from app.services.vms_client import vms_client
from app.services.scheduler import vms_scheduler

router = APIRouter(prefix="/api/vessels", tags=["Vessels"])

class GSTCLoginRequest(BaseModel):
    username: str
    password: str

class GSTCCookieRequest(BaseModel):
    cookie: str

@router.get("", response_model=List[VesselOut])
def list_vessels(db: Session = Depends(get_db)):
    return get_all_vessels(db)

@router.get("/paginated")
def list_vessels_paginated(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Lấy danh sách tàu cá hỗ trợ phân trang, tìm kiếm và lọc trạng thái"""
    res = get_vessels_with_pagination(db, skip=skip, limit=limit, search=search, status_filter=status)
    # Serialize items
    items_out = []
    for v in res["items"]:
        items_out.append({
            "id": v.id,
            "plate_number": v.plate_number,
            "ship_name": v.ship_name or v.plate_number,
            "owner_name": v.owner_name,
            "owner_phone": v.owner_phone or "",
            "owner_address": v.owner_address or "",
            "chieudaitoanbo": v.chieudaitoanbo,
            "congsuat": v.congsuat or 0.0,
            "device_id": v.device_id or "",
            "created_at": v.created_at.isoformat() if v.created_at else None,
            "updated_at": v.updated_at.isoformat() if v.updated_at else None,
            "state": {
                "current_status": v.state.current_status.value if v.state else "NORMAL",
                "is_alerted": v.state.is_alerted if v.state else False,
                "consecutive_lost_cycles": v.state.consecutive_lost_cycles if v.state else 0,
                "last_signal_time": v.state.last_signal_time.isoformat() if v.state and v.state.last_signal_time else None,
                "last_latitude": v.state.last_latitude if v.state else None,
                "last_longitude": v.state.last_longitude if v.state else None
            } if v.state else None
        })
    return {
        "items": items_out,
        "total": res["total"],
        "skip": res["skip"],
        "limit": res["limit"]
    }

@router.get("/export-excel")
def export_vessels_excel(db: Session = Depends(get_db)):
    """Xuất toàn bộ danh sách tàu cá và trạng thái kết nối VMS ra file Excel (.xlsx)"""
    vessels = get_all_vessels(db)
    rows = []
    for idx, v in enumerate(vessels, start=1):
        st = v.state
        status_label = "Bình thường (< 2h)"
        lost_cycles = 0
        last_sig = "Chưa có"
        lat = ""
        lng = ""
        if st:
            lost_cycles = st.consecutive_lost_cycles
            if st.current_status == StateEnum.LOST_SIGNAL:
                status_label = f"MẤT KẾT NỐI ({lost_cycles} chu kỳ)"
            elif st.current_status == StateEnum.RECOVERED:
                status_label = "Đã khắc phục"
            if st.last_signal_time:
                last_sig = st.last_signal_time.strftime("%d/%m/%Y %H:%M:%S")
            if st.last_latitude:
                lat = f"{st.last_latitude:.5f}°N"
            if st.last_longitude:
                lng = f"{st.last_longitude:.5f}°E"

        rows.append({
            "STT": idx,
            "Số Đăng Ký (Biển số)": v.plate_number,
            "Tên Tàu": v.ship_name or v.plate_number,
            "Tên Chủ Tàu": v.owner_name,
            "Số Điện Thoại": v.owner_phone or "",
            "Địa Chỉ Thường Trú": v.owner_address or "",
            "Chiều Dài Lmax (m)": v.chieudaitoanbo,
            "Công Suất (CV)": v.congsuat or "",
            "Mã Thiết Bị VMS": v.device_id or "",
            "Trạng Thái Kết Nối": status_label,
            "Số Chu Kỳ Mất": lost_cycles,
            "Vĩ Độ Gần Nhất": lat,
            "Kinh Độ Gần Nhất": lng,
            "Thời Điểm Nhận Tín Hiệu Cuối": last_sig
        })

    df = pd.DataFrame(rows)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Danh_Sach_Tau_VMS')
    output.seek(0)

    filename = f"Danh_sach_tau_ca_VMS_NHVN_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    return Response(
        content=output.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.get("/{plate}/track-history")
def get_vessel_track(plate: str, limit: int = 50, db: Session = Depends(get_db)):
    """Lấy lịch sử tọa độ di chuyển của tàu để hiển thị hành trình trên bản đồ"""
    norm = normalize_plate(plate)
    vessel = get_vessel_by_plate(db, norm)
    if not vessel:
        raise HTTPException(status_code=404, detail="Không tìm thấy tàu")
    
    positions = get_vessel_track_history(db, vessel.id, limit=limit)
    return {
        "plate_number": vessel.plate_number,
        "ship_name": vessel.ship_name,
        "total_points": len(positions),
        "track": [
            {
                "latitude": p.latitude,
                "longitude": p.longitude,
                "recorded_at": p.recorded_at.strftime("%Y-%m-%d %H:%M:%S") if p.recorded_at else None,
                "ship_state": p.ship_state or "Bình thường",
                "distance_to_boundary": p.distance_to_boundary
            }
            for p in positions
        ]
    }

@router.post("", response_model=VesselOut)
def add_vessel(vessel_in: VesselCreate, db: Session = Depends(get_db)):
    if vessel_in.chieudaitoanbo < settings.MIN_VESSEL_LENGTH_METERS:
        raise HTTPException(
            status_code=400,
            detail=f"Chiều dài tàu là {vessel_in.chieudaitoanbo}m. Hệ thống chỉ giám sát tàu có chiều dài từ {settings.MIN_VESSEL_LENGTH_METERS} mét trở lên!"
        )
    return create_or_update_vessel(db, vessel_in)

@router.delete("/{plate}")
def remove_vessel(plate: str, db: Session = Depends(get_db)):
    ok = delete_vessel(db, plate)
    if not ok:
        raise HTTPException(status_code=404, detail="Không tìm thấy tàu cá để xóa")
    return {"success": True, "message": f"Đã xóa tàu {plate} khỏi danh sách theo dõi"}

@router.post("/import")
async def import_vessels_file(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Nhập danh sách tàu từ file Excel (.xlsx/.xls), CSV hoặc JSON với cơ chế tự động dò tìm Header"""
    content = await file.read()
    filename = file.filename.lower()
    df = None

    try:
        if filename.endswith(".csv"):
            text_data = content.decode("utf-8", errors="ignore")
            lines = text_data.splitlines()
            # Dò tìm dòng Header chứa 'Số ĐK' hoặc 'Số đăng ký' hoặc 'Chủ tàu'
            header_idx = 0
            for idx, line in enumerate(lines[:15]):
                if "Số ĐK" in line or "Số đăng ký" in line or "Chủ tàu" in line or "plate" in line.lower():
                    header_idx = idx
                    break
            df = pd.read_csv(io.StringIO("\n".join(lines[header_idx:])))

        elif filename.endswith((".xlsx", ".xls")):
            # Đọc không header để dò dòng tiêu đề
            df_raw = pd.read_excel(io.BytesIO(content), header=None)
            header_idx = 0
            for idx, row in df_raw.head(15).iterrows():
                row_str = " ".join([str(val) for val in row.values])
                if "Số ĐK" in row_str or "Số đăng ký" in row_str or "Chủ tàu" in row_str:
                    header_idx = idx
                    break
            df = pd.read_excel(io.BytesIO(content), skiprows=header_idx)

        elif filename.endswith(".json"):
            raw_json = json.loads(content.decode("utf-8", errors="ignore"))
            records = raw_json if isinstance(raw_json, list) else (raw_json.get("vessels") or raw_json.get("data") or [])
            df = pd.DataFrame(records)
        else:
            raise HTTPException(status_code=400, detail="Chỉ hỗ trợ file Excel (.xlsx, .xls), CSV hoặc JSON")

        if df is None or df.empty:
            raise HTTPException(status_code=400, detail="File không chứa dữ liệu hợp lệ")

        # Chuẩn hóa tên cột
        col_map = {}
        for c in df.columns:
            c_str = str(c).strip().lower()
            if "số đk" in c_str or "số đăng ký" in c_str or "biển số" in c_str or "so_dk" in c_str or "plate" in c_str:
                col_map[c] = "plate_number"
            elif "chủ tàu" in c_str or "owner" in c_str:
                col_map[c] = "owner_name"
            elif "điện thoại" in c_str or "sđt" in c_str or "phone" in c_str:
                col_map[c] = "owner_phone"
            elif "xã/phường" in c_str or "địa chỉ" in c_str or "address" in c_str:
                col_map[c] = "owner_address"
            elif "lmax" in c_str or "chiều dài" in c_str or "length" in c_str:
                col_map[c] = "chieudaitoanbo"
            elif "công suất" in c_str or "cv" in c_str or "power" in c_str:
                col_map[c] = "congsuat"
            elif "mã thiết bị" in c_str or "vms" in c_str or "device" in c_str:
                col_map[c] = "device_id"
            elif "trạng thái" in c_str or "status" in c_str:
                col_map[c] = "raw_status"

        df.rename(columns=col_map, inplace=True)

        imported_count = 0
        skipped_under_15m = 0

        for _, r in df.iterrows():
            plate = str(r.get("plate_number", "")).strip()
            if not plate or plate.lower() == "nan":
                continue

            try:
                length_val = float(r.get("chieudaitoanbo") or 15.0)
            except Exception:
                length_val = 15.0

            if length_val < settings.MIN_VESSEL_LENGTH_METERS:
                skipped_under_15m += 1
                continue

            owner = str(r.get("owner_name") or "Chưa rõ").strip()
            phone = normalize_vietnam_phone(r.get("owner_phone"))
            address = str(r.get("owner_address") or "").strip()

            v_obj = VesselCreate(
                plate_number=plate,
                ship_name=plate,
                owner_name=owner,
                owner_phone=phone,
                owner_address=address,
                chieudaitoanbo=length_val,
                congsuat=float(r.get("congsuat") or 0.0),
                device_id=str(r.get("device_id") or "").replace("nan", "").strip()
            )
            vessel = create_or_update_vessel(db, v_obj)

            # Cập nhật trạng thái ban đầu nếu có cột trạng thái
            raw_st = str(r.get("raw_status", "")).strip()
            if raw_st and vessel.state:
                if "mất kết nối" in raw_st.lower() or "chưa lắp vms" in raw_st.lower():
                    vessel.state.current_status = StateEnum.LOST_SIGNAL
                    vessel.state.is_alerted = True
                    vessel.state.consecutive_lost_cycles = 1

            imported_count += 1

        db.commit()

        return {
            "success": True,
            "message": f"Đã nhập thành công {imported_count} tàu cá có chiều dài ≥ 15 mét. (Đã bỏ qua {skipped_under_15m} tàu dưới 15m)."
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi đọc file: {str(e)}")

@router.get("/sample-template")
def download_sample_template():
    """Tạo và trả về file mẫu Excel"""
    file_path = settings.DATA_DIR / "Mau_Danh_Sach_Tau_Ca_Giam_Sat.xlsx"
    if not file_path.exists():
        # Tạo file mẫu
        df = pd.DataFrame([
            {
                "Số đăng ký": "KH-91234-TS",
                "Tên tàu": "Tàu Cá Ninh Thủy 01",
                "Tên chủ tàu": "Nguyễn Văn Hùng",
                "Số điện thoại": "0913456789",
                "Địa chỉ": "Tổ dân phố Mỹ Lương, Phường Ninh Thủy, TX Ninh Hòa",
                "Thuyền trưởng": "Nguyễn Văn Hùng",
                "SĐT thuyền trưởng": "0913456789",
                "Địa chỉ thuyền trưởng": "Tổ dân phố Mỹ Lương, Phường Ninh Thủy, TX Ninh Hòa",
                "Chiều dài (m)": 18.5,
                "Công suất (CV)": 450,
                "Mã thiết bị VMS": "VMS-KH-001"
            },
            {
                "Số đăng ký": "KH-96888-TS",
                "Tên tàu": "Tàu Cá Ninh Diêm 02",
                "Tên chủ tàu": "Trần Văn Nam",
                "Số điện thoại": "0905123456",
                "Địa chỉ": "Tổ dân phố Phú Thọ, Phường Ninh Diêm, TX Ninh Hòa",
                "Thuyền trưởng": "Trần Văn Nam",
                "SĐT thuyền trưởng": "0905123456",
                "Địa chỉ thuyền trưởng": "Tổ dân phố Phú Thọ, Phường Ninh Diêm, TX Ninh Hòa",
                "Chiều dài (m)": 16.8,
                "Công suất (CV)": 380,
                "Mã thiết bị VMS": "VMS-KH-002"
            }
        ])
        df.to_excel(file_path, index=False)

    return FileResponse(
        path=str(file_path),
        filename="Mau_Danh_Sach_Tau_Ca_Giam_Sat.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# =====================================================================
# CÁC ENDPOINT ĐỒNG BỘ CHÍNH XÁC VỚI BẢN ĐỒ TỔNG CỤC THỦY SẢN (GSTC)
# =====================================================================

@router.get("/gstc/status")
def get_gstc_status():
    """Lấy trạng thái kết nối và phiên làm việc Tổng cục Thủy sản"""
    return {
        "is_authenticated": vms_client.is_authenticated,
        "has_cookie": bool(vms_client.current_cookie),
        "last_sync_time": vms_client.last_sync_time.strftime("%Y-%m-%d %H:%M:%S") if vms_client.last_sync_time else None,
        "last_sync_count": vms_client.last_sync_count,
        "last_message": vms_client.last_sync_message,
        "api_url": settings.GSTC_API_URL
    }

@router.post("/gstc/test")
def test_gstc_connection():
    """Kiểm tra gọi thử API Cổng Tổng cục Thủy sản với Cookie hiện có"""
    ok, msg, count = vms_client.test_connection()
    return {
        "success": ok,
        "message": msg,
        "vessels_count": count
    }

@router.post("/gstc/cookie")
def update_gstc_cookie(req: GSTCCookieRequest):
    """Cập nhật Cookie phiên làm việc GSTC và kiểm tra kết nối ngay"""
    raw_cookie = req.cookie.strip()
    if not raw_cookie:
        raise HTTPException(status_code=400, detail="Vui lòng cung cấp chuỗi Cookie")

    vms_client.reload_cookie(raw_cookie)
    ok, msg, count = vms_client.test_connection()
    if ok:
        # Nếu test kết nối thành công, kích hoạt chu kỳ đối chiếu cập nhật luôn tọa độ thật
        vms_scheduler.trigger_now()

    return {
        "success": ok,
        "message": f"Đã lưu Cookie. {msg}",
        "vessels_count": count
    }

@router.post("/gstc/login")
def login_gstc_account(req: GSTCLoginRequest):
    """Đăng nhập trực tiếp vào hệ thống Tổng cục Thủy sản để lấy phiên kết nối"""
    if not req.username or not req.password:
        raise HTTPException(status_code=400, detail="Vui lòng nhập Tên đăng nhập và Mật khẩu GSTC")

    ok, msg = vms_client.login_gstc(req.username, req.password)
    if ok:
        # Tự động kích hoạt đối chiếu đồng bộ tọa độ GPS thật ngay lập tức
        res = vms_scheduler.trigger_now()
        return {
            "success": True,
            "message": f"{msg}. Đã tự động đồng bộ tọa độ GPS của các tàu trên bản đồ!",
            "result": res
        }
    else:
        raise HTTPException(status_code=400, detail=msg)

@router.post("/gstc/sync-file")
async def sync_vessels_from_gstc_file(file: UploadFile = File(...)):
    """
    ĐỒNG BỘ TỌA ĐỘ GPS CHÍNH XÁC 100% TỪ FILE XUẤT TỔNG CỤC THỦY SẢN:
    Cán bộ tải file xuất từ trang Map của Tổng cục Thủy sản (Excel .xlsx/.xls hoặc .csv)
    Hệ thống phân tích và cập nhật tọa độ thực tế tức thì lên bản đồ và cơ sở dữ liệu!
    """
    content = await file.read()
    filename = file.filename

    records, msg = vms_client.parse_gstc_file(content, filename)
    if not records:
        raise HTTPException(status_code=400, detail=f"Không đọc được dữ liệu tọa độ từ file: {msg}")

    # Chạy đối chiếu và cập nhật cơ sở dữ liệu
    result = vms_scheduler.process_gstc_records(records, source_name=f"File {filename}")

    return {
        "success": True,
        "message": f"Đã đồng bộ thành công tọa độ thực tế từ file Tổng cục ({filename}): Cập nhật {result.get('synced_coords', 0)} vị trí GPS chính xác!",
        "result": result
    }

