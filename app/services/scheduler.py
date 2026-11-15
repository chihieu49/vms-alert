# -*- coding: utf-8 -*-
"""
Scheduler Service (APScheduler)
Quản lý chu kỳ định kỳ 2 giờ: Poll GSTC API -> So khớp -> Cảnh báo -> Khắc phục (Recovery)
Hỗ trợ đồng bộ tọa độ chính xác thời gian thực từ Cổng GSTC (API trực tiếp hoặc File xuất Tổng cục)
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings
from app.database import SessionLocal
from app.models import Vessel, VesselState, StateEnum, ChannelEnum
from app.crud import normalize_plate, add_position_record, record_alert_event
from app.services.vms_client import vms_client
from app.services.notifier import notifier
from app.services.geo_utils import normalize_vessel_coords

class VMSSchedulerService:
    def __init__(self):
        self.scheduler = BackgroundScheduler(daemon=True)
        self.job = None
        self.is_running = False
        self.last_scan_time: Optional[datetime] = None
        self.last_status: str = "Chưa khởi động"
        self.last_message: str = ""

    def start(self):
        if self.is_running:
            return

        interval = settings.POLL_INTERVAL_MINUTES
        if interval < 1:
            interval = 1

        self.job = self.scheduler.add_job(
            func=self.run_reconciliation_cycle,
            trigger=IntervalTrigger(minutes=interval),
            id="vms_poll_job",
            name="Chu kỳ kiểm tra VMS 2 giờ",
            replace_existing=True,
            next_run_time=datetime.now() # Kích hoạt chu kỳ đầu tiên ngay lập tức
        )

        self.scheduler.start()
        self.is_running = True
        print(f"[SCHEDULER] Đã khởi động APScheduler. Chu kỳ: {interval} phút (mỗi 2 giờ).")

    def stop(self):
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
        self.is_running = False
        print("[SCHEDULER] Đã dừng APScheduler.")

    def reschedule(self, interval_minutes: int):
        if interval_minutes < 1:
            interval_minutes = 1
        if self.job and self.scheduler.running:
            self.scheduler.reschedule_job(
                "vms_poll_job",
                trigger=IntervalTrigger(minutes=interval_minutes)
            )
            print(f"[SCHEDULER] Đã cập nhật chu kỳ kiểm tra: {interval_minutes} phút.")

    def trigger_now(self) -> Dict[str, Any]:
        return self.run_reconciliation_cycle()

    def get_next_run_time(self) -> Optional[str]:
        if self.job and self.job.next_run_time:
            return self.job.next_run_time.strftime("%Y-%m-%d %H:%M:%S")
        return None

    def _parse_vms_datetime(self, time_raw) -> Optional[datetime]:
        if not time_raw:
            return None
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%d/%m/%Y %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%d-%m-%Y %H:%M:%S",
            "%Y/%m/%d %H:%M:%S",
            "%d/%m/%Y %H:%M",
            "%Y-%m-%d %H:%M"
        ]
        s = str(time_raw).strip()
        for fmt in formats:
            try:
                return datetime.strptime(s, fmt)
            except Exception:
                pass
        return None

    def process_gstc_records(self, raw_records: List[Dict[str, Any]], source_name: str = "GSTC") -> Dict[str, Any]:
        """
        Quy trình xử lý và đối chiếu dữ liệu tọa độ GSTC:
        1. Cập nhật tọa độ GPS chính xác 100% của từng tàu vào cơ sở dữ liệu và bản đồ.
        2. So khớp thời gian phát tín hiệu:
           - Tàu không có dữ liệu vị trí cập nhật sau 2 giờ -> tổng hợp và gửi email tới adminnhvn@gmail.com
           - Tàu trong chu kỳ 2 giờ tiếp theo đã quay lại báo vị trí bình thường -> tự động chấm dứt việc gửi thông báo.
        """
        now = datetime.now()
        scan_time_str = now.strftime("%Y-%m-%d %H:%M:%S")
        self.last_scan_time = now
        print(f"\n=======================================================")
        print(f"[VMS SCHEDULER] Bắt đầu đối chiếu dữ liệu ({source_name}): {scan_time_str}")
        print(f"=======================================================")

        db = SessionLocal()
        try:
            vessels = db.query(Vessel).all()
            if not vessels:
                msg = "Chưa có tàu cá nào trong danh sách theo dõi."
                self.last_status = "CHỜ DỮ LIỆU"
                self.last_message = msg
                return {"status": "NO_VESSELS", "message": msg}

            # Tạo bảng băm tra cứu dữ liệu GSTC theo số đăng ký chuẩn hóa
            gstc_map = {}
            for rec in raw_records:
                p_raw = (
                    rec.get("plate_number") or rec.get("Số đăng ký") or
                    rec.get("Biển số") or rec.get("BienSo") or rec.get("plate")
                )
                if p_raw:
                    gstc_map[normalize_plate(p_raw)] = rec

            lost_to_alert: List[Dict[str, Any]] = []
            recovered_list: List[str] = []
            normal_list: List[str] = []
            threshold_minutes = float(settings.LOST_SIGNAL_THRESHOLD_MINUTES)
            synced_coords_count = 0

            for v in vessels:
                norm_p = normalize_plate(v.plate_number)
                state = v.state
                if not state:
                    state = VesselState(vessel_id=v.id, current_status=StateEnum.NORMAL)
                    db.add(state)
                    db.flush()

                match_rec = gstc_map.get(norm_p)
                has_recent_signal = False
                pos_dt: Optional[datetime] = None
                lat: Optional[float] = state.last_latitude
                lng: Optional[float] = state.last_longitude

                if match_rec:
                    time_raw = (
                        match_rec.get("time") or match_rec.get("ThoiGian") or
                        match_rec.get("Thời gian") or match_rec.get("date")
                    )
                    pos_dt = self._parse_vms_datetime(time_raw)

                    # Chuẩn hóa tọa độ chuyên dụng hàng hải
                    raw_lat = match_rec.get("latitude") or match_rec.get("Vĩ độ") or match_rec.get("lat")
                    raw_lng = match_rec.get("longitude") or match_rec.get("Kinh độ") or match_rec.get("lng")
                    norm_lat, norm_lng = normalize_vessel_coords(raw_lat, raw_lng)
                    if norm_lat is not None and norm_lng is not None:
                        lat, lng = norm_lat, norm_lng
                        synced_coords_count += 1

                    if pos_dt:
                        diff = (now - pos_dt).total_seconds() / 60.0
                        if diff <= threshold_minutes:
                            has_recent_signal = True
                    else:
                        has_recent_signal = True

                    # Cập nhật thông tin bổ sung từ GSTC nếu thiếu
                    if match_rec.get("deviceId") and not v.device_id:
                        v.device_id = str(match_rec.get("deviceId")).strip()

                # Logic Chuyển Trạng Thái (State Engine)
                if has_recent_signal:
                    if state.is_alerted or state.current_status == StateEnum.LOST_SIGNAL:
                        # CƠ CHẾ GIÁM SÁT TRẠNG THÁI KHẮC PHỤC (RECOVERY):
                        # Trong chu kỳ 2 giờ tiếp theo, tàu đã quay lại và báo vị trí bình thường
                        # -> TỰ ĐỘNG CHẤM DỨT VIỆC GỬI THÔNG BÁO CHO TÀU ĐÓ!
                        state.current_status = StateEnum.RECOVERED
                        recovered_list.append(norm_p)
                        print(f"[RECOVERY] Tàu {norm_p} đã quay lại và báo vị trí bình thường lúc {pos_dt or now}. CHẤM DỨT CẢNH BÁO!")

                        lat_str = f"{lat:.4f}°N" if lat else "N/A"
                        lng_str = f"{lng:.4f}°E" if lng else "N/A"
                        record_alert_event(
                            db=db,
                            vessel_id=v.id,
                            plate_number=norm_p,
                            event_type="RECOVERED_DISCONTINUE",
                            recipient=settings.ADMIN_EMAIL,
                            consecutive_cycles=0,
                            details=f"Tàu đã quay lại và báo vị trí bình thường ({lat_str}, {lng_str}). Hệ thống tự động chấm dứt việc gửi thông báo.",
                            status="DISCONTINUED"
                        )
                    else:
                        state.current_status = StateEnum.NORMAL
                        normal_list.append(norm_p)

                    # Reset cờ cảnh báo và chu kỳ mất
                    state.is_alerted = False
                    state.consecutive_lost_cycles = 0
                    if pos_dt:
                        state.last_signal_time = pos_dt
                    state.last_latitude = lat
                    state.last_longitude = lng
                    state.last_checked_at = now

                    # Lưu lịch sử tọa độ chính xác vào cơ sở dữ liệu
                    if lat and lng:
                        st_text = match_rec.get("ship_state") if match_rec else "Bình thường"
                        dist_val = match_rec.get("distanceToboundy") if match_rec else None
                        add_position_record(db, v.id, lat, lng, pos_dt or now, st_text, dist_val)

                else:
                    # Tàu KHÔNG có dữ liệu vị trí cập nhật sau chu kỳ 2 giờ
                    state.consecutive_lost_cycles += 1
                    state.current_status = StateEnum.LOST_SIGNAL
                    state.is_alerted = True
                    state.last_checked_at = now
                    if lat and lng:
                        state.last_latitude = lat
                        state.last_longitude = lng

                    v_info = {
                        "vessel_id": v.id,
                        "plate_number": norm_p,
                        "ship_name": v.ship_name,
                        "owner_name": v.owner_name,
                        "owner_phone": v.owner_phone or v.captain_phone,
                        "owner_address": v.owner_address or v.captain_address,
                        "captain_name": v.captain_name,
                        "captain_phone": v.captain_phone,
                        "captain_address": v.captain_address,
                        "chieudaitoanbo": v.chieudaitoanbo,
                        "consecutive_lost_cycles": state.consecutive_lost_cycles,
                        "last_signal_time": state.last_signal_time.strftime("%Y-%m-%d %H:%M:%S") if state.last_signal_time else "Chưa có",
                        "last_latitude": state.last_latitude,
                        "last_longitude": state.last_longitude
                    }
                    lost_to_alert.append(v_info)
                    print(f"[ALERT] Phát hiện tàu mất kết nối: {norm_p} (Chủ: {v.owner_name}, SĐT: {v.owner_phone})")

                    record_alert_event(
                        db=db,
                        vessel_id=v.id,
                        plate_number=norm_p,
                        event_type="ALERT_SENT",
                        recipient=settings.ADMIN_EMAIL,
                        consecutive_cycles=state.consecutive_lost_cycles,
                        details=f"Mất tín hiệu vị trí sau chu kỳ 2 giờ lúc {scan_time_str}",
                        status="SENT" if settings.SMTP_USER else "SAVED_LOCAL"
                    )

            db.commit()

            # Tự động gửi email cảnh báo tới adminnhvn@gmail.com
            email_msg = "Không có cảnh báo mới."
            if lost_to_alert:
                print(f"[SCHEDULER] Đang gửi thông báo {len(lost_to_alert)} tàu mất kết nối tới {settings.ADMIN_EMAIL}...")
                ok, email_msg = notifier.send_email_alert(lost_to_alert, scan_time_str)
                notifier.dispatch_all(lost_to_alert, scan_time_str)

            self.last_status = "HOÀN TẤT"
            self.last_message = f"Đối chiếu {len(vessels)} tàu: {len(normal_list)} bình thường, {len(lost_to_alert)} mất kết nối, {len(recovered_list)} khôi phục. Đồng bộ {synced_coords_count} tọa độ. {email_msg}"
            print(f"[SCHEDULER] {self.last_message}\n")

            return {
                "total": len(vessels),
                "normal": len(normal_list),
                "lost": len(lost_to_alert),
                "recovered": len(recovered_list),
                "synced_coords": synced_coords_count,
                "lost_vessels": lost_to_alert,
                "email_status": email_msg
            }

        except Exception as e:
            db.rollback()
            self.last_status = "LỖI"
            self.last_message = f"Lỗi trong quá trình đối chiếu: {e}"
            print(f"[SCHEDULER ERROR] {e}")
            return {"status": "ERROR", "error": str(e)}
        finally:
            db.close()

    def run_reconciliation_cycle(self) -> Dict[str, Any]:
        """Chu kỳ định kỳ mỗi 2 giờ: Lấy dữ liệu từ VMSClient và đối chiếu"""
        raw_records, status_code, api_msg = vms_client.fetch_realtime_vessels()
        print(f"[SCHEDULER] Kết quả API ({status_code}): {api_msg}")
        return self.process_gstc_records(raw_records, source_name="GSTC API")

vms_scheduler = VMSSchedulerService()
