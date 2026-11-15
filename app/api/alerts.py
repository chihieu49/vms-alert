# -*- coding: utf-8 -*-
"""
Alerts API
Nhật ký cảnh báo, xem email lưu trữ, kiểm thử kịch bản khắc phục
"""
import io
import json
from datetime import datetime
from typing import List
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import HTMLResponse, FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AlertHistory, Vessel, VesselState, StateEnum
from app.schemas import AlertHistoryOut
from app.crud import get_recent_alerts, record_alert_event
from app.config import settings
from app.services.notifier import notifier

router = APIRouter(prefix="/api/alerts", tags=["Alerts"])

@router.get("/history", response_model=List[AlertHistoryOut])
def list_alert_history(limit: int = 50, skip: int = 0, db: Session = Depends(get_db)):
    return get_recent_alerts(db, limit=limit, skip=skip)

@router.get("/stats")
def get_alerts_stats(db: Session = Depends(get_db)):
    """Thống kê tổng quan về lịch sử cảnh báo và phục hồi"""
    total = db.query(AlertHistory).count()
    alerts_sent = db.query(AlertHistory).filter(AlertHistory.event_type == "ALERT_SENT").count()
    recovered = db.query(AlertHistory).filter(AlertHistory.event_type == "RECOVERED_DISCONTINUE").count()
    return {
        "total_events": total,
        "alerts_sent": alerts_sent,
        "recovered_discontinued": recovered,
        "recipient": settings.ADMIN_EMAIL
    }

@router.get("/export-excel")
def export_alerts_excel(db: Session = Depends(get_db)):
    """Xuất toàn bộ nhật ký cảnh báo và trạng thái khắc phục ra Excel (.xlsx)"""
    alerts = db.query(AlertHistory).order_by(AlertHistory.sent_at.desc()).limit(1000).all()
    rows = []
    for idx, a in enumerate(alerts, start=1):
        event_label = "Mất kết nối (> 2h)" if a.event_type == "ALERT_SENT" else "Đã khắc phục (Chấm dứt cảnh báo)"
        rows.append({
            "STT": idx,
            "Thời Gian": a.sent_at.strftime("%d/%m/%Y %H:%M:%S") if a.sent_at else "",
            "Số Đăng Ký (Biển số)": a.plate_number,
            "Loại Sự Kiện": event_label,
            "Kênh Thông Báo": a.channel.value if hasattr(a.channel, 'value') else str(a.channel),
            "Nơi Nhận": a.recipient,
            "Số Chu Kỳ Mất": a.consecutive_cycles,
            "Chi Tiết Nội Dung": a.details or "",
            "Trạng Thái Gửi": a.delivery_status
        })

    df = pd.DataFrame(rows)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Nhat_Ky_Canh_Bao')
    output.seek(0)

    filename = f"Nhat_ky_canh_bao_VMS_NHVN_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    return Response(
        content=output.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.get("/sent-emails")
def list_sent_emails():
    """Lấy danh sách các email cảnh báo đã gửi và lưu trữ"""
    results = []
    if not settings.EMAILS_DIR.exists():
        return results

    json_files = sorted(list(settings.EMAILS_DIR.glob("*.json")), reverse=True)
    for jf in json_files[:30]:
        try:
            with open(jf, "r", encoding="utf-8") as f:
                data = json.load(f)
                results.append(data)
        except Exception:
            pass
    return results

@router.get("/view-email/{filename}", response_class=HTMLResponse)
def view_email_html(filename: str):
    """Xem trực tiếp bản sao email HTML (Chống Path Traversal)"""
    from pathlib import Path
    clean_name = Path(filename).name
    if not clean_name.endswith(".html") or ".." in filename:
        raise HTTPException(status_code=400, detail="Tên file không hợp lệ")
    file_path = (settings.EMAILS_DIR / clean_name).resolve()
    if not str(file_path).startswith(str(settings.EMAILS_DIR.resolve())):
        raise HTTPException(status_code=403, detail="Không có quyền truy cập file này")
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Không tìm thấy email")
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()

@router.post("/send-test")
def send_test_alert():
    """Tạo và gửi một email thử nghiệm đầy đủ thông tin tới adminnhvn@gmail.com"""
    sample = [
        {
            "plate_number": "KH-91234-TS",
            "owner_name": "Nguyễn Văn Hùng",
            "owner_phone": "0913456789",
            "owner_address": "Tổ dân phố Mỹ Lương, Phường Ninh Thủy, TX Ninh Hòa",
            "chieudaitoanbo": 18.5,
            "consecutive_lost_cycles": 1,
            "last_signal_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    ]
    ok, msg = notifier.send_email_alert(sample)
    return {"success": ok, "message": msg}

@router.post("/simulate-recovery")
def simulate_recovery(db: Session = Depends(get_db)):
    """
    Giả lập kịch bản:
    Tàu đang ở trạng thái LOST_SIGNAL quay lại báo vị trí bình thường
    -> Kích hoạt cơ chế TỰ ĐỘNG CHẤM DỨT THÔNG BÁO!
    """
    lost_state = db.query(VesselState).filter(VesselState.current_status == StateEnum.LOST_SIGNAL).first()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if lost_state:
        vessel = lost_state.vessel
        lost_state.current_status = StateEnum.RECOVERED
        lost_state.is_alerted = False
        lost_state.consecutive_lost_cycles = 0
        lost_state.last_signal_time = datetime.now()
        lost_state.last_checked_at = datetime.now()

        # Ghi log sự kiện tự động chấm dứt cảnh báo
        record_alert_event(
            db=db,
            vessel_id=vessel.id,
            plate_number=vessel.plate_number,
            event_type="RECOVERED_DISCONTINUE",
            recipient=settings.ADMIN_EMAIL,
            consecutive_cycles=0,
            details=f"KỊCH BẢN TEST: Tàu {vessel.plate_number} đã quay lại và báo vị trí bình thường. Hệ thống tự động chấm dứt việc gửi thông báo.",
            status="DISCONTINUED"
        )
        db.commit()
        return {
            "success": True,
            "message": f"Đã mô phỏng tàu {vessel.plate_number} quay lại báo vị trí bình thường -> Tự động chấm dứt cảnh báo (RECOVERED)."
        }
    else:
        # Nếu chưa có tàu nào mất, chọn 1 tàu bình thường chuyển sang LOST_SIGNAL để chuẩn bị test
        norm_state = db.query(VesselState).filter(VesselState.current_status == StateEnum.NORMAL).first()
        if norm_state:
            vessel = norm_state.vessel
            norm_state.current_status = StateEnum.LOST_SIGNAL
            norm_state.is_alerted = True
            norm_state.consecutive_lost_cycles = 1
            norm_state.last_checked_at = datetime.now()

            record_alert_event(
                db=db,
                vessel_id=vessel.id,
                plate_number=vessel.plate_number,
                event_type="ALERT_SENT",
                recipient=settings.ADMIN_EMAIL,
                consecutive_cycles=1,
                details=f"KỊCH BẢN TEST: Tàu {vessel.plate_number} mất kết nối quá 2 giờ.",
                status="SENT"
            )
            db.commit()

            # Gửi email cảnh báo
            v_dict = {
                "plate_number": vessel.plate_number,
                "owner_name": vessel.owner_name,
                "owner_phone": vessel.owner_phone or vessel.captain_phone,
                "owner_address": vessel.owner_address,
                "chieudaitoanbo": vessel.chieudaitoanbo,
                "consecutive_lost_cycles": 1,
                "last_signal_time": now_str
            }
            notifier.send_email_alert([v_dict])

            return {
                "success": True,
                "message": f"Đã mô phỏng tàu {vessel.plate_number} mất kết nối quá 2 giờ -> Hệ thống đã gửi email cảnh báo tới {settings.ADMIN_EMAIL}."
            }
        return {"success": False, "message": "Không tìm thấy tàu nào trong cơ sở dữ liệu."}

