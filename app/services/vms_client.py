# -*- coding: utf-8 -*-
"""
VMS Client Service
Truy xuất dữ liệu thời gian thực từ Cổng thông tin Tổng cục Thủy sản:
- Đăng nhập trực tiếp (Username & Password) tới gstc.tongcucthuysan.gov.vn
- Đồng bộ bằng Cookie phiên làm việc (ASP.NET_SessionId, .ASPXAUTH)
- Phân tích và nạp trực tiếp file xuất từ Tổng cục (.xlsx, .xls, .csv, json)
- Hỗ trợ đa định dạng dữ liệu GPS chuẩn hàng hải
"""
import io
import re
import csv
import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple, Optional
from urllib3.exceptions import InsecureRequestWarning
from app.config import settings

# Bỏ cảnh báo SSL
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

class VMSClient:
    def __init__(self):
        self.session = requests.Session()
        self.current_cookie: str = settings.GSTC_COOKIE or ""
        self.is_authenticated: bool = False
        self.last_sync_time: Optional[datetime] = None
        self.last_sync_count: int = 0
        self.last_sync_message: str = "Chưa kết nối Cổng Tổng cục Thủy sản"
        self._setup_session()

    def _setup_session(self):
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
            "Connection": "keep-alive"
        })
        if self.current_cookie:
            self.session.headers.update({"Cookie": self.current_cookie})

    def reload_cookie(self, new_cookie: Optional[str] = None):
        if new_cookie is not None:
            self.current_cookie = new_cookie.strip()
            self._save_cookie_to_env(self.current_cookie)
        self._setup_session()

    def _save_cookie_to_env(self, cookie_val: str):
        """Lưu cookie vào file .env để duy trì qua các lần khởi động lại"""
        try:
            env_path = settings.BASE_DIR / ".env"
            lines = []
            cookie_found = False
            if env_path.exists():
                with open(env_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()

            new_lines = []
            for line in lines:
                if line.strip().startswith("GSTC_COOKIE="):
                    new_lines.append(f'GSTC_COOKIE="{cookie_val}"\n')
                    cookie_found = True
                else:
                    new_lines.append(line)

            if not cookie_found:
                new_lines.append(f'\nGSTC_COOKIE="{cookie_val}"\n')

            with open(env_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
        except Exception as e:
            print(f"[VMS_CLIENT] Cảnh báo lưu file .env: {e}")

    def login_gstc(self, username: str, password: str) -> Tuple[bool, str]:
        """
        Đăng nhập trực tiếp vào Cổng thông tin Tổng cục Thủy sản:
        URL: https://gstc.tongcucthuysan.gov.vn/Account/Logon
        """
        login_url = "https://gstc.tongcucthuysan.gov.vn/Account/Logon"
        try:
            # 1. Khởi tạo session mới để lấy cookie phiên ban đầu
            self.session = requests.Session()
            self._setup_session()

            init_resp = self.session.get(login_url, timeout=15, verify=False)
            
            # 2. Gửi thông tin đăng nhập
            payload = {
                "Username": username.strip(),
                "Password": password.strip()
            }
            
            post_resp = self.session.post(
                login_url,
                data=payload,
                timeout=20,
                verify=False,
                allow_redirects=True
            )

            # 3. Kiểm tra xem đăng nhập thành công hay không
            # Nếu thành công thường có cookie .ASPXAUTH hoặc redirect ra khỏi trang /Account/Logon
            cookies_dict = self.session.cookies.get_dict()
            has_auth_cookie = any(".ASPXAUTH" in k or "auth" in k.lower() or "session" in k.lower() for k in cookies_dict.keys())
            not_on_logon = "/Account/Logon" not in post_resp.url

            if has_auth_cookie and not_on_logon:
                # Ghép chuỗi cookie
                cookie_str = "; ".join([f"{k}={v}" for k, v in cookies_dict.items()])
                self.current_cookie = cookie_str
                self.is_authenticated = True
                self._save_cookie_to_env(cookie_str)
                self._setup_session()
                self.last_sync_message = f"Đã đăng nhập GSTC thành công bằng tài khoản {username}"
                return True, self.last_sync_message
            else:
                # Kiểm tra thông báo lỗi trên trang
                if "Tên đăng nhập hoặc mật khẩu không đúng" in post_resp.text:
                    return False, "Tên đăng nhập hoặc mật khẩu Tổng cục Thủy sản không chính xác!"
                elif "/Account/Logon" in post_resp.url:
                    return False, "Đăng nhập không thành công, vui lòng kiểm tra lại tài khoản hoặc nạp Cookie trực tiếp."
                else:
                    cookie_str = "; ".join([f"{k}={v}" for k, v in cookies_dict.items()])
                    if cookie_str:
                        self.current_cookie = cookie_str
                        self.is_authenticated = True
                        self._save_cookie_to_env(cookie_str)
                        return True, "Đã lưu phiên kết nối GSTC."
                    return False, "Không nhận diện được phiên đăng nhập."

        except Exception as e:
            return False, f"Lỗi kết nối Cổng Tổng cục Thủy sản: {str(e)}"

    def test_connection(self) -> Tuple[bool, str, int]:
        """Kiểm tra xem kết nối và Cookie tới Tổng cục có hiệu lực hay không"""
        try:
            self._setup_session()
            resp = self.session.get(settings.GSTC_API_URL, timeout=15, verify=False, allow_redirects=False)

            if resp.status_code == 302:
                loc = resp.headers.get("Location", "")
                if "/Account/Logon" in loc:
                    self.is_authenticated = False
                    return False, "Phiên đăng nhập chưa được xác thực hoặc Cookie đã hết hạn (Redirect 302 Logon).", 0

            if resp.status_code == 200:
                if "/Account/Logon" in resp.url or "loginform" in resp.text.lower():
                    self.is_authenticated = False
                    return False, "Yêu cầu đăng nhập Tổng cục Thủy sản.", 0

                records, _, msg = self._parse_response_content(resp)
                if records:
                    self.is_authenticated = True
                    self.last_sync_time = datetime.now()
                    self.last_sync_count = len(records)
                    self.last_sync_message = f"Kết nối GSTC thành công: Nhận {len(records)} tàu trực tiếp"
                    return True, self.last_sync_message, len(records)

            return False, f"Máy chủ GSTC phản hồi mã trạng thái {resp.status_code}", 0
        except Exception as e:
            return False, f"Lỗi kết nối GSTC: {str(e)}", 0

    def fetch_realtime_vessels(self) -> Tuple[List[Dict[str, Any]], int, str]:
        """
        Truy xuất dữ liệu danh sách tàu từ GSTC API.
        Trả về: (records: list, status_code: int, message: str)
        """
        if settings.USE_MOCK_DATA:
            return self._generate_mock_data(), 200, "Đang dùng dữ liệu kiểm thử (Mock Mode)"

        self._setup_session()

        try:
            resp = self.session.get(settings.GSTC_API_URL, timeout=30, verify=False, allow_redirects=False)

            # 1. Kiểm tra redirect form đăng nhập
            if resp.status_code in (301, 302, 303, 307):
                loc = resp.headers.get("Location", "")
                if "/Account/Logon" in loc:
                    self.is_authenticated = False
                    msg = "Yêu cầu đăng nhập GSTC (Cookie hết hạn hoặc chưa đăng nhập). Đang dùng vị trí đã lưu."
                    return self._generate_mock_data(auth_needed=True), 401, msg

            if "/Account/Logon" in resp.url or "loginform" in resp.text.lower():
                self.is_authenticated = False
                msg = "Yêu cầu đăng nhập GSTC. Vui lòng cập nhật Cookie hoặc đăng nhập để đồng bộ thời gian thực."
                return self._generate_mock_data(auth_needed=True), 401, msg

            records, status, msg = self._parse_response_content(resp)
            if records:
                self.is_authenticated = True
                self.last_sync_time = datetime.now()
                self.last_sync_count = len(records)
                self.last_sync_message = msg
                return records, 200, msg

            return self._generate_mock_data(auth_needed=True), resp.status_code, f"Không đọc được bản ghi từ API GSTC ({msg})"

        except Exception as e:
            return self._generate_mock_data(network_error=True), 500, f"Lỗi mạng khi kết nối GSTC: {e}"

    def _parse_response_content(self, resp: requests.Response) -> Tuple[List[Dict[str, Any]], int, str]:
        """Phân tích nội dung phản hồi từ Cổng GSTC (JSON, Excel, CSV, HTML Table)"""
        content_type = resp.headers.get("Content-Type", "").lower()
        records = []

        # 1. Xử lý định dạng JSON
        if "application/json" in content_type or resp.text.strip().startswith("[") or resp.text.strip().startswith("{"):
            try:
                data = resp.json()
                if isinstance(data, list):
                    records = data
                elif isinstance(data, dict):
                    records = data.get("data") or data.get("rows") or data.get("items") or data.get("vessels") or []
                return self._normalize_gstc_records(records), resp.status_code, f"Đồng bộ thành công (JSON): {len(records)} tàu từ Tổng cục"
            except Exception:
                pass

        # 2. Xử lý định dạng Excel (.xlsx hoặc .xls)
        if "excel" in content_type or "spreadsheetml" in content_type or resp.content.startswith(b"PK\x03\x04") or resp.content.startswith(b"\xd0\xcf\x11\xe0"):
            try:
                df = pd.read_excel(io.BytesIO(resp.content))
                records = self._parse_dataframe_to_gstc_records(df)
                return records, resp.status_code, f"Đồng bộ thành công (Excel): {len(records)} tàu từ Tổng cục"
            except Exception as e:
                return [], resp.status_code, f"Lỗi đọc file Excel từ GSTC: {e}"

        # 3. Xử lý định dạng CSV
        if "text/csv" in content_type or ("," in resp.text and "\n" in resp.text and not resp.text.strip().startswith("<")):
            try:
                df = pd.read_csv(io.StringIO(resp.text))
                records = self._parse_dataframe_to_gstc_records(df)
                return records, resp.status_code, f"Đồng bộ thành công (CSV): {len(records)} tàu từ Tổng cục"
            except Exception:
                pass

        # 4. Xử lý bảng HTML
        if "<table" in resp.text.lower():
            try:
                dfs = pd.read_html(resp.text)
                if dfs:
                    records = self._parse_dataframe_to_gstc_records(dfs[0])
                    return records, resp.status_code, f"Đồng bộ thành công (Bảng HTML): {len(records)} tàu từ Tổng cục"
            except Exception as e:
                return [], resp.status_code, f"Lỗi phân tích bảng HTML: {e}"

        return [], resp.status_code, f"Không nhận diện được định dạng dữ liệu ({content_type})"

    def parse_gstc_file(self, file_bytes: bytes, filename: str) -> Tuple[List[Dict[str, Any]], str]:
        """
        Phân tích trực tiếp file xuất từ mục Map trên Tổng cục Thủy sản
        (Do cán bộ trạm tải về từ GSTC và nạp vào hệ thống)
        """
        fn = filename.lower()
        df = None

        try:
            if fn.endswith((".xlsx", ".xls")):
                # Đọc kiểm tra tiêu đề dòng
                df_raw = pd.read_excel(io.BytesIO(file_bytes), header=None)
                header_idx = 0
                for idx, row in df_raw.head(15).iterrows():
                    row_str = " ".join([str(val) for val in row.values]).lower()
                    if "số đk" in row_str or "biển số" in row_str or "plate" in row_str or "vĩ độ" in row_str or "latitude" in row_str:
                        header_idx = idx
                        break
                df = pd.read_excel(io.BytesIO(file_bytes), skiprows=header_idx)

            elif fn.endswith(".csv"):
                text = file_bytes.decode("utf-8", errors="ignore")
                lines = text.splitlines()
                header_idx = 0
                for idx, line in enumerate(lines[:15]):
                    l_lower = line.lower()
                    if "số đk" in l_lower or "biển số" in l_lower or "plate" in l_lower or "latitude" in l_lower or "vĩ độ" in l_lower:
                        header_idx = idx
                        break
                df = pd.read_csv(io.StringIO("\n".join(lines[header_idx:])))

            elif fn.endswith(".json"):
                import json
                raw_json = json.loads(file_bytes.decode("utf-8", errors="ignore"))
                records = raw_json if isinstance(raw_json, list) else (raw_json.get("data") or raw_json.get("vessels") or [])
                return self._normalize_gstc_records(records), f"Đã phân tích {len(records)} tàu từ file JSON"

            if df is None or df.empty:
                return [], "File không chứa bảng dữ liệu hợp lệ"

            records = self._parse_dataframe_to_gstc_records(df)
            self.last_sync_time = datetime.now()
            self.last_sync_count = len(records)
            self.last_sync_message = f"Đồng bộ thành công từ file xuất GSTC: {len(records)} tàu"
            return records, self.last_sync_message

        except Exception as e:
            return [], f"Lỗi phân tích file GSTC: {str(e)}"

    def _parse_dataframe_to_gstc_records(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Chuẩn hóa DataFrame từ Cổng GSTC thành danh sách Dict chuẩn"""
        # Ánh xạ cột linh hoạt
        col_map = {}
        for c in df.columns:
            cs = str(c).strip().lower()
            if any(k in cs for k in ["số đk", "số đăng ký", "biển số", "plate_number", "plate", "so_dk"]):
                col_map[c] = "plate_number"
            elif any(k in cs for k in ["vĩ độ", "latitude", "lat", "vi_do"]):
                col_map[c] = "latitude"
            elif any(k in cs for k in ["kinh độ", "longitude", "lng", "lon", "kinh_do"]):
                col_map[c] = "longitude"
            elif any(k in cs for k in ["thời gian", "time", "date", "thoi_gian", "vms_time"]):
                col_map[c] = "time"
            elif any(k in cs for k in ["trạng thái", "ship_state", "state", "trang_thai"]):
                col_map[c] = "ship_state"
            elif any(k in cs for k in ["khoảng cách", "boundary", "distancetoboundy", "khoang_cach"]):
                col_map[c] = "distanceToboundy"
            elif any(k in cs for k in ["chủ tàu", "owner", "chu_tau"]):
                col_map[c] = "ownerName"
            elif any(k in cs for k in ["điện thoại", "phone", "sđt", "so_dt"]):
                col_map[c] = "ownerPhone"
            elif any(k in cs for k in ["địa chỉ", "address", "dia_chi"]):
                col_map[c] = "ownerAddress"
            elif any(k in cs for k in ["thuyền trưởng", "captain", "thuyen_truong"]):
                col_map[c] = "captainName"
            elif any(k in cs for k in ["thiết bị", "device", "imei", "serial", "thiet_bi"]):
                col_map[c] = "deviceId"
            elif any(k in cs for k in ["chiều dài", "lmax", "chieudaitoanbo", "length"]):
                col_map[c] = "chieudaitoanbo"
            elif any(k in cs for k in ["công suất", "cv", "congsuat", "power"]):
                col_map[c] = "congsuat"

        df_renamed = df.rename(columns=col_map)
        raw_list = df_renamed.to_dict(orient="records")
        return self._normalize_gstc_records(raw_list)

    def _normalize_gstc_records(self, raw_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Làm sạch và chuẩn hóa danh sách bản ghi vị trí tàu"""
        from app.services.geo_utils import normalize_vessel_coords
        cleaned = []

        for r in raw_list:
            plate = str(r.get("plate_number") or r.get("Số ĐK") or r.get("Biển số") or "").strip()
            if not plate or plate.lower() == "nan":
                continue

            raw_lat = r.get("latitude") or r.get("Vĩ độ") or r.get("lat")
            raw_lng = r.get("longitude") or r.get("Kinh độ") or r.get("lng")
            norm_lat, norm_lng = normalize_vessel_coords(raw_lat, raw_lng)

            # Lấy thời gian
            t_val = r.get("time") or r.get("Thời gian") or r.get("date") or ""
            t_str = str(t_val).strip() if t_val and str(t_val).lower() != "nan" else ""

            # Khoảng cách đến ranh giới
            dist_val = r.get("distanceToboundy") or r.get("Khoảng cách") or None
            try:
                dist = float(dist_val) if dist_val is not None and str(dist_val).lower() != "nan" else None
            except Exception:
                dist = None

            cleaned.append({
                "plate_number": plate,
                "latitude": norm_lat,
                "longitude": norm_lng,
                "time": t_str,
                "ship_state": str(r.get("ship_state") or r.get("Trạng thái") or "Đang hoạt động").replace("nan", "").strip(),
                "distanceToboundy": dist,
                "ownerName": str(r.get("ownerName") or r.get("Chủ tàu") or "").replace("nan", "").strip(),
                "ownerPhone": str(r.get("ownerPhone") or r.get("Số điện thoại") or "").replace(".0", "").replace("nan", "").strip(),
                "ownerAddress": str(r.get("ownerAddress") or r.get("Địa chỉ") or "").replace("nan", "").strip(),
                "captainName": str(r.get("captainName") or r.get("Thuyền trưởng") or "").replace("nan", "").strip(),
                "deviceId": str(r.get("deviceId") or r.get("Mã thiết bị") or "").replace("nan", "").strip(),
                "chieudaitoanbo": r.get("chieudaitoanbo"),
                "congsuat": r.get("congsuat"),
                "is_real_gstc": True  # Đánh dấu dữ liệu GPS thực từ Tổng cục
            })
        return cleaned

    def _generate_mock_data(self, auth_needed=False, network_error=False, force_all_normal=False) -> List[Dict[str, Any]]:
        """
        Dữ liệu dự phòng khi chưa kết nối được Cổng GSTC:
        Lấy tọa độ gần nhất đã lưu trong cơ sở dữ liệu nếu có, hoặc tạo tọa độ tạm thời ngoài khơi
        """
        from app.database import SessionLocal
        from app.crud import get_all_vessels
        from app.services.geo_utils import generate_realistic_marine_coords

        db = SessionLocal()
        vessels = get_all_vessels(db)
        total_vessels = len(vessels)

        now = datetime.now()
        now_str = now.strftime("%Y-%m-%d %H:%M:%S")
        old_time_str = (now - timedelta(hours=4)).strftime("%Y-%m-%d %H:%M:%S")

        records = []
        for idx, v in enumerate(vessels):
            state = v.state
            if force_all_normal:
                is_lost = False
            else:
                is_lost = (idx == 1) or (state and state.current_status == "LOST_SIGNAL")

            # Ưu tiên lấy tọa độ đã có trong DB
            if state and state.last_latitude and state.last_longitude:
                lat = state.last_latitude
                lng = state.last_longitude
                is_real = True
            else:
                lat, lng = generate_realistic_marine_coords(idx, total_vessels)
                is_real = False

            t_val = now_str if not is_lost else (
                state.last_signal_time.strftime("%Y-%m-%d %H:%M:%S") if (state and state.last_signal_time) else old_time_str
            )

            records.append({
                "plate_number": v.plate_number,
                "shipName": v.ship_name,
                "ownerName": v.owner_name,
                "ownerPhone": v.owner_phone,
                "ownerAddress": v.owner_address,
                "captainName": v.captain_name,
                "captainPhone": v.captain_phone,
                "captainAddress": v.captain_address,
                "chieudaitoanbo": v.chieudaitoanbo,
                "congsuat": v.congsuat,
                "time": t_val,
                "latitude": lat,
                "longitude": lng,
                "ship_state": "Mất tín hiệu >2h" if is_lost else "Đang khai thác",
                "deviceId": v.device_id or f"VMS-{1000+idx}",
                "is_real_gstc": is_real
            })

        db.close()
        return records

vms_client = VMSClient()
