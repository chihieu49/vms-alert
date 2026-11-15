# -*- coding: utf-8 -*-
"""
Dashboard API & HTMX Endpoints
"""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Vessel, VesselState, StateEnum
from app.services.scheduler import vms_scheduler

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])

@router.get("/summary")
def get_dashboard_summary(db: Session = Depends(get_db)):
    """Trả về số liệu thống kê cho KPI Cards"""
    vessels = db.query(Vessel).all()
    total = len(vessels)
    normal = 0
    lost = 0
    recovered = 0

    for v in vessels:
        if v.state:
            st = v.state.current_status
            if st == StateEnum.NORMAL:
                normal += 1
            elif st == StateEnum.LOST_SIGNAL:
                lost += 1
            elif st == StateEnum.RECOVERED:
                recovered += 1

    return {
        "total": total,
        "normal": normal,
        "lost": lost,
        "recovered": recovered,
        "scheduler": {
            "is_running": vms_scheduler.is_running,
            "last_scan_time": vms_scheduler.last_scan_time.strftime("%Y-%m-%d %H:%M:%S") if vms_scheduler.last_scan_time else None,
            "next_scan_time": vms_scheduler.get_next_run_time(),
            "last_status": vms_scheduler.last_status,
            "last_message": vms_scheduler.last_message
        }
    }

@router.post("/scan-now")
def trigger_scan_now():
    """Kích hoạt chu kỳ đối chiếu ngay lập tức"""
    res = vms_scheduler.trigger_now()
    return {"success": True, "result": res}

