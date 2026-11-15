# BÁO CÁO KIỂM TRA MÃ NGUỒN (CODE AUDIT REPORT)
## Hệ Thống Giám Sát Tàu Cá VMS Alert
### Trạm Kiểm Ngư Ninh Hòa - Vạn Ninh • Chi cục Thủy sản và Biển đảo tỉnh Khánh Hòa
---
**Ngày kiểm tra:** 15/11/2026  
**Phiên bản hệ thống:** 2.0.0  
**Phạm vi:** Toàn bộ mã nguồn Python + Templates + Cấu hình  
**Kiểm tra viên:** Code Auditor (AI-Agent)

---

## TÓM TẮT ĐIỀU HÀNH

Hệ thống VMS Alert có kiến trúc tương đối gọn gàng (FastAPI + APScheduler + SQLite + Jinja2/Leaflet), phù hợp với quy mô trạm cấp huyện. Tuy nhiên, kết quả kiểm tra phát hiện **1 lỗ hổng bảo mật cực kỳ nghiêm trọng** (không có xác thực người dùng) và nhiều lỗi logic, hiệu năng cần xử lý khẩn.

| Mức độ | Số lượng vấn đề |
|--------|----------------|
| 🔴 CRITICAL | 4 |
| 🟠 HIGH | 8 |
| 🟡 MEDIUM | 9 |
| 🟢 LOW | 7 |
| **Tổng cộng** | **28** |

---

## PHẦN 1: LỖI CRITICAL (Nghiêm trọng – Cần xử lý ngay lập tức)

### C-01 🔴 CRITICAL — KHÔNG CÓ HỆ THỐNG XÁC THỰC (AUTHENTICATION)
**File:** Toàn hệ thống  
**Mô tả:**  
Hệ thống **không có bất kỳ cơ chế đăng nhập/phân quyền nào**. Toàn bộ endpoint API và giao diện web đều mở hoàn toàn cho bất kỳ ai truy cập mà không cần xác thực:
- `/api/vessels` – Xem, thêm, xóa tàu thoải mái
- `/api/dashboard/scan-now` – Bất kỳ ai cũng có thể kích hoạt chu kỳ quét thủ công
- `/api/alerts/simulate-recovery` – Có thể giả lập khắc phục tàu bất kỳ lúc nào
- `/api/vessels/gstc/login` – Lộ form đăng nhập GSTC ra internet
- `/api/alerts/view-email/{filename}` – Bất kỳ ai biết tên file đều xem được nội dung email cảnh báo

**Hậu quả:**  
- Kẻ xấu có thể xóa toàn bộ danh sách tàu
- Có thể thao túng trạng thái tàu (giả mạo khắc phục/mất tín hiệu)
- Lộ thông tin cá nhân (tên chủ tàu, số điện thoại, địa chỉ) vi phạm bảo mật dữ liệu
- Hệ thống deploy lên Render (internet công khai) → đặc biệt nguy hiểm

**Khuyến nghị:**  
Triển khai ngay FastAPI `HTTPBasicCredentials` hoặc JWT token auth. Tối thiểu dùng HTTP Basic Auth với username/password cấu hình qua `.env`.

---

### C-02 🔴 CRITICAL — LỖ HỔNG PATH TRAVERSAL (Đọc file tùy ý trên server)
**File:** `app/api/alerts.py` – dòng 44-50  
**Mô tả:**
```python
@router.get("/view-email/{filename}", response_class=HTMLResponse)
def view_email_html(filename: str):
    file_path = settings.EMAILS_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, ...)
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()
```
Tham số `filename` lấy trực tiếp từ URL không được sanitize. Kẻ tấn công có thể dùng:
```
GET /api/alerts/view-email/../../.env
GET /api/alerts/view-email/../../data/vms_alert.db
```
Để đọc file `.env` (lộ SMTP password, cookie GSTC, API keys) hoặc toàn bộ database SQLite.

**Khuyến nghị:**
```python
# Kiểm tra file có thực sự nằm trong EMAILS_DIR không
file_path = (settings.EMAILS_DIR / filename).resolve()
if not str(file_path).startswith(str(settings.EMAILS_DIR.resolve())):
    raise HTTPException(status_code=400, detail="Truy cập không hợp lệ")
# Chỉ cho phép đuôi .html
if not filename.endswith('.html') or '/' in filename or '..' in filename:
    raise HTTPException(status_code=400)
```

---

### C-03 🔴 CRITICAL — GSTC COOKIE LƯU VÀO FILE .ENV (Credential Exposure)
**File:** `app/services/vms_client.py` – hàm `_save_cookie_to_env()` dòng 49-73  
**Mô tả:**  
Khi người dùng nhập Cookie GSTC qua giao diện web, hệ thống tự động ghi thẳng vào file `.env` trên disk:
```python
with open(env_path, "w", encoding="utf-8") as f:
    f.writelines(new_lines)
```
**Vấn đề nghiêm trọng:**
1. Nếu nhiều luồng (threads) đồng thời gọi hàm này → race condition → file `.env` bị hỏng/corrupt
2. Cookie (credential) bị ghi vào file plaintext có thể đọc bởi bất kỳ process nào có quyền đọc filesystem
3. Khi deploy Docker, file `.env` mount vào container → lộ credential ra ngoài
4. Không có file locking → potential data corruption

**Khuyến nghị:**  
Lưu cookie vào database (bảng `AppConfig`) hoặc dùng `threading.Lock` + atomic write.

---

### C-04 🔴 CRITICAL — LỖI LOGIC: MẤT TÍN HIỆU KHI KHÔNG CÓ DỮ LIỆU GSTC
**File:** `app/services/scheduler.py` – dòng 163-168  
**Mô tả:**
```python
if pos_dt:
    diff = (now - pos_dt).total_seconds() / 60.0
    if diff <= threshold_minutes:
        has_recent_signal = True
else:
    has_recent_signal = True  # ← BUG NGHIÊM TRỌNG!
```
Khi tàu **có** trong danh sách GSTC nhưng **không có trường thời gian** (`time` = null/empty) → `pos_dt = None` → `has_recent_signal = True` → hệ thống coi tàu là **bình thường** dù thực sự không rõ trạng thái.

**Hậu quả:** Bỏ sót cảnh báo khi API GSTC trả về dữ liệu thiếu timestamp.  
**Khuyến nghị:** Thay `has_recent_signal = True` bằng logic kiểm tra thêm hoặc coi là "không rõ" (UNKNOWN state).

---

## PHẦN 2: LỖI HIGH (Nghiêm trọng – Nên xử lý trong sprint gần nhất)

### H-01 🟠 HIGH — DUPLICATE ALERT: Gửi email trùng mỗi chu kỳ
**File:** `app/services/scheduler.py` – dòng 215-253  
**Mô tả:**  
Mỗi chu kỳ 2 giờ, hễ tàu còn trong trạng thái `LOST_SIGNAL` là lại gửi email và ghi `AlertHistory`. Không có cơ chế chặn gửi lại khi tàu đã `is_alerted = True` ở chu kỳ trước. Sau 10 chu kỳ (20 giờ), sẽ có 10 email cảnh báo cho cùng 1 tàu.

**Khuyến nghị:**  
Thêm điều kiện: chỉ gửi email nếu `state.is_alerted == False` (lần đầu phát hiện) HOẶC gửi email tổng hợp theo chu kỳ escalation (ví dụ: chu kỳ 1, 3, 6, 12...).

---

### H-02 🟠 HIGH — SSL VERIFICATION BỊ TẮT HOÀN TOÀN
**File:** `app/services/vms_client.py` – dòng 21, 86, 94, 139, 175  
**Mô tả:**
```python
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)
# Và mọi request đều có: verify=False
resp = self.session.get(url, timeout=15, verify=False)
```
Toàn bộ kết nối HTTPS tới `gstc.tongcucthuysan.gov.vn` đều tắt kiểm tra chứng chỉ SSL. Điều này mở ra nguy cơ **Man-in-the-Middle attack**: kẻ tấn công có thể chặn toàn bộ traffic, lộ cookie phiên đăng nhập GSTC.

**Khuyến nghị:** Dùng `verify=True` (mặc định). Nếu server GSTC dùng self-signed cert, chỉ định rõ `verify='/path/to/cert.pem'`.

---

### H-03 🟠 HIGH — CORS HOÀN TOÀN MỞ (`allow_origins=["*"]`)
**File:** `app/main.py` – dòng 111-117  
**Mô tả:**
```python
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, ...)
```
Kết hợp `allow_origins=["*"]` với `allow_credentials=True` là **cấu hình sai theo spec CORS** (browser sẽ từ chối). Hơn nữa, nếu hệ thống thêm auth cookie sau này thì CORS mở hoàn toàn sẽ cho phép CSRF attacks từ bất kỳ domain nào.

**Khuyến nghị:** Giới hạn `allow_origins` theo domain thực tế của trạm hoặc dải IP nội bộ.

---

### H-04 🟠 HIGH — SEED INITIAL DATA CHẠY ĐỒNG BỘ KHI STARTUP (BLOCKING)
**File:** `app/main.py` – dòng 90  
**Mô tả:**
```python
seed_initial_vessels()  # Gọi đồng bộ trực tiếp ở module level (trước khi app tạo)
```
Hàm `seed_initial_vessels()` được gọi ở **module level**, nghĩa là chạy khi Python import module. Nếu database chưa tạo bảng (hoặc migration chưa xong), sẽ crash ở đây. Hơn nữa, `Base.metadata.create_all(bind=engine)` ở dòng 26 cũng chạy đồng bộ — nên dùng lifespan event.

**Khuyến nghị:** Chuyển cả `create_all` và `seed_initial_vessels` vào trong `lifespan()` async context manager.

---

### H-05 🟠 HIGH — SCHEDULER KHÔNG CÓ CONCURRENCY LOCK
**File:** `app/services/scheduler.py` – hàm `run_reconciliation_cycle()`  
**Mô tả:**  
Khi người dùng bấm "Quét Ngay" (`trigger_now()`) trong lúc scheduler đang tự chạy chu kỳ 2 giờ → 2 luồng cùng chạy `process_gstc_records()` đồng thời → race condition trên database SQLite (vốn chỉ hỗ trợ 1 writer tại 1 thời điểm) → có thể gây `OperationalError: database is locked`.

**Khuyến nghị:**
```python
import threading
self._lock = threading.Lock()

def run_reconciliation_cycle(self):
    if not self._lock.acquire(blocking=False):
        return {"status": "SKIPPED", "message": "Chu kỳ trước đang chạy"}
    try:
        return self.process_gstc_records(...)
    finally:
        self._lock.release()
```

---

### H-06 🟠 HIGH — MOCK DATA LUÔN ĐÁNH DẤU 1 TÀU LÀ MẤT KẾT NỐI (HARDCODE BUG)
**File:** `app/services/vms_client.py` – dòng 403  
**Mô tả:**
```python
is_lost = (idx == 1) or (state and state.current_status == "LOST_SIGNAL")
```
Hàm `_generate_mock_data()` được gọi khi không kết nối được GSTC (tình huống thường xuyên xảy ra). Điều kiện `idx == 1` hardcode tàu thứ 2 (index 1) luôn **bị đánh dấu mất kết nối**. Mỗi chu kỳ 2 giờ sẽ liên tục tạo cảnh báo giả cho tàu này, gây spam email khi hệ thống chạy không có kết nối GSTC.

**Khuyến nghị:** Xóa điều kiện `idx == 1`, chỉ giữ `state.current_status == "LOST_SIGNAL"`.

---

### H-07 🟠 HIGH — `datetime.utcnow()` SẼ DEPRECATED TRONG PYTHON 3.12+
**File:** `app/models.py` dòng 43-44, 63-64, 98; `app/crud.py` dòng 67, 142  
**Mô tả:**
```python
created_at = Column(DateTime, default=datetime.utcnow)
updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```
`datetime.utcnow()` đã bị deprecated từ Python 3.12 và sẽ bị xóa trong tương lai. Hơn nữa, cột `DateTime` không có `timezone=True` → toàn bộ timestamp trong DB là naive datetime, không rõ timezone → khó debug khi hệ thống chạy ở timezone khác UTC.

**Khuyến nghị:**
```python
from datetime import datetime, timezone
# Thay bằng:
default=lambda: datetime.now(timezone.utc)
```

---

### H-08 🟠 HIGH — IMPORT FILE EXCEL KHÔNG CÓ GIỚI HẠN KÍCH THƯỚC
**File:** `app/api/vessels.py` – dòng 56-171  
**Mô tả:**  
Endpoint `/api/vessels/import` nhận file upload không giới hạn kích thước:
```python
async def import_vessels_file(file: UploadFile = File(...), ...):
    content = await file.read()  # Đọc toàn bộ vào RAM không giới hạn
```
Kẻ tấn công có thể upload file Excel 1GB → crash server do hết RAM (Denial of Service).

**Khuyến nghị:**
```python
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10MB
content = await file.read(MAX_UPLOAD_SIZE + 1)
if len(content) > MAX_UPLOAD_SIZE:
    raise HTTPException(status_code=413, detail="File vượt quá giới hạn 10MB")
```

---

## PHẦN 3: LỖI MEDIUM (Trung bình – Nên xử lý trong 1-2 tháng tới)

### M-01 🟡 MEDIUM — XSS TIỀM NĂNG TRONG EMAIL HTML (Stored XSS)
**File:** `app/services/notifier.py` – hàm `build_email_payload()` dòng 83-93  
**Mô tả:**  
Dữ liệu từ database (plate_number, owner_name, phone, address) được nhúng trực tiếp vào chuỗi HTML không qua escape:
```python
rows_html += f"""
<td ...>{plate}</td>
<td ...>{owner}</td>
<td ...><a href="tel:{phone}">{phone}</a></td>
<td ...>{address}</td>
"""
```
Nếu dữ liệu import chứa payload XSS (`<script>alert(1)</script>`), nó sẽ được nhúng vào email HTML. Khi người nhận xem email → browser có thể thực thi script.

**Khuyến nghị:** Dùng `html.escape()` cho mọi dữ liệu động trong HTML template:
```python
import html
plate = html.escape(v.get("plate_number", ""))
```

---

### M-02 🟡 MEDIUM — `get_all_vessels()` KHÔNG CÓ PAGINATION
**File:** `app/crud.py` dòng 45-46; `app/api/vessels.py` dòng 35-37  
**Mô tả:**
```python
def get_all_vessels(db: Session) -> List[Vessel]:
    return db.query(Vessel).order_by(Vessel.plate_number.asc()).all()
```
Toàn bộ danh sách tàu luôn load 100% vào RAM và trả về JSON. Với hệ thống có 100-500 tàu, lượng data này (~50-200KB JSON) được tải mỗi 5 giây (do `setInterval(loadDashboardData, 5000)`). Trên Render Free Tier (512MB RAM) và mạng chậm sẽ gây lag.

**Khuyến nghị:** Thêm `skip`/`limit` hoặc cursor-based pagination. Tách riêng API lấy summary (KPI) và API lấy danh sách có phân trang.

---

### M-03 🟡 MEDIUM — POLLING 5 GIÂY LIÊN TỤC (PERFORMANCE)
**File:** `app/templates/index.html` – dòng 444  
**Mô tả:**
```javascript
setInterval(loadDashboardData, 5000);  // Cứ 5 giây gọi 2 API
setInterval(checkGSTCStatus, 10000);   // Cứ 10 giây gọi thêm 1 API
```
Mỗi lần `loadDashboardData()` gọi 2 API (`/api/dashboard/summary` và `/api/vessels`). Với 10 user đồng thời: 10 × (2 request/5s) = **4 request/giây** liên tục, chưa kể checkGSTCStatus. Trên Render Free Tier (single process) rất dễ bị throttle.

**Khuyến nghị:** Dùng WebSocket hoặc SSE (Server-Sent Events) để push update. Nếu giữ polling, tăng interval lên 30-60s.

---

### M-04 🟡 MEDIUM — KHÔNG CÓ DATABASE INDEX CHO CÁC TRUY VẤN THƯỜNG DÙNG
**File:** `app/models.py`  
**Mô tả:**  
Các cột thường xuyên dùng để lọc/join thiếu index:
- `VesselState.current_status` – dùng trong dashboard summary loop
- `VesselState.vessel_id` – có `unique=True` nhưng không phải query index riêng
- `AlertHistory.sent_at` – dùng để sort/limit recent alerts
- `VesselPosition.vessel_id` – dùng trong relationship load

**Khuyến nghị:**
```python
current_status = Column(Enum(StateEnum), ..., index=True)  # Thêm index=True
# AlertHistory:
sent_at = Column(DateTime, default=datetime.utcnow, index=True)
```

---

### M-05 🟡 MEDIUM — `get_recent_alerts` CHỈ LẤY 50 BẢN GHI (HARDCODE)
**File:** `app/crud.py` dòng 148-149; `app/api/alerts.py` dòng 22-24  
**Mô tả:**
```python
def get_recent_alerts(db: Session, limit: int = 50) -> List[AlertHistory]:
    return db.query(AlertHistory).order_by(AlertHistory.id.desc()).limit(limit).all()
```
API có nhận `limit` param nhưng không có `skip`/`offset`. Sau vài tháng hoạt động, bảng `alert_histories` có thể chứa hàng ngàn bản ghi — không thể xem lịch sử cũ, không có phân trang.

---

### M-06 🟡 MEDIUM — `VesselPosition` KHÔNG CÓ CLEANUP/ROTATION
**File:** `app/models.py` + `app/crud.py`  
**Mô tả:**  
Hàm `add_position_record()` ghi mỗi chu kỳ 2 giờ cho mỗi tàu. Với 100 tàu × 12 lần/ngày × 365 ngày = **438,000 bản ghi/năm**. Không có cơ chế xóa dữ liệu cũ → database phình to, hiệu năng giảm, Render Free Tier 512MB RAM dễ OOM.

**Khuyến nghị:** Thêm cleanup job: xóa `VesselPosition` cũ hơn 30 ngày.

---

### M-07 🟡 MEDIUM — THÔNG TIN NHẠY CẢM IN RA CONSOLE (Credential Logging)
**File:** `app/main.py` – dòng 180  
**Mô tả:**
```python
print(f"[*] Email nhận cảnh báo tự động: {settings.ADMIN_EMAIL}")
```
Và trong `app/services/scheduler.py`:
```python
print(f"[ALERT] Phát hiện tàu mất kết nối: {norm_p} (Chủ: {v.owner_name}, SĐT: {v.owner_phone})")
```
Số điện thoại, tên chủ tàu in ra console log — trên cloud hosting (Render), log có thể xem được bởi team Render, vi phạm bảo vệ dữ liệu cá nhân.

**Khuyến nghị:** Dùng Python `logging` module với level phù hợp. Mask PII trong log production.

---

### M-08 🟡 MEDIUM — `normalize_vessel_coords` NHẬN CẢ TỌA ĐỘ ÂM RỒI `abs()` MÀ KHÔNG KIỂM TRA
**File:** `app/services/geo_utils.py` – dòng 115-116  
**Mô tả:**
```python
lat = abs(lat)
lng = abs(lng)
```
Hàm vô điều kiện lấy giá trị tuyệt đối của lat/lng. Điều này sẽ xử lý sai nếu tọa độ hợp lệ có giá trị âm (tuy vùng biển Việt Nam không có lat/lng âm, nhưng logic này không đúng về mặt toán học/hải đồ quốc tế, và có thể gây bug nếu mở rộng phạm vi).

---

### M-09 🟡 MEDIUM — `dispatch_all()` GỬI EMAIL HAI LẦN KHI CÓ SMTP
**File:** `app/services/scheduler.py` – dòng 261-262  
**Mô tả:**
```python
ok, email_msg = notifier.send_email_alert(lost_to_alert, scan_time_str)  # Gửi lần 1
notifier.dispatch_all(lost_to_alert, scan_time_str)  # Gửi lại lần 2 (gọi send_email_alert bên trong)
```
`dispatch_all()` lại gọi `send_email_alert()` bên trong → email được gửi **2 lần** cho cùng 1 chu kỳ nếu SMTP được cấu hình.

**Khuyến nghị:** Xóa dòng `notifier.dispatch_all(...)` hoặc thay thế `send_email_alert` bằng `dispatch_all`.

---

## PHẦN 4: LỖI LOW (Nhỏ – Nên xử lý khi có thời gian)

### L-01 🟢 LOW — `event` KHÔNG ĐƯỢC TRUYỀN VÀO HÀM JS
**File:** `app/templates/index.html` – dòng 527, 564  
**Mô tả:**
```javascript
async function submitGSTCFile() {
    const btn = event.target;  // 'event' là global implicit, không phải parameter
```
Dùng `event` global thay vì nhận tham số → không hoạt động đúng trong mọi browser/strict mode.

**Khuyến nghị:**
```html
<button onclick="submitGSTCFile(event)">...</button>
```
```javascript
async function submitGSTCFile(event) {
    const btn = event.target;
```

---

### L-02 🟢 LOW — `docker-compose.yml` THIẾU HEALTH CHECK VÀ VOLUME DB
**File:** `docker-compose.yml`  
**Mô tả:**
```yaml
volumes:
  - ./data:/app/data  # Chỉ mount data, không persist database nếu DB_URL khác
```
Thiếu:
1. `healthcheck` để Docker biết khi nào app sẵn sàng
2. Không có `depends_on` nếu sau này thêm external DB
3. Không có resource limits (memory/cpu) → container có thể ăn hết RAM host

---

### L-03 🟢 LOW — `requirements.txt` KHÔNG PIN PHIÊN BẢN CỤ THỂ
**File:** `requirements.txt`  
**Mô tả:**
```
fastapi>=0.100.0
pandas>=1.5.0
```
Dùng `>=` không pin version cụ thể → có thể cài phiên bản mới nhất gây breaking changes. Nên dùng `==` hoặc `~=` và dùng `pip freeze` để tạo `requirements-lock.txt`.

---

### L-04 🟢 LOW — THIẾU THÔNG BÁO KHI GỬI EMAIL THẤT BẠI (Silent Failure)
**File:** `app/services/scheduler.py` – dòng 261  
**Mô tả:**
```python
ok, email_msg = notifier.send_email_alert(lost_to_alert, scan_time_str)
# Không có retry, không có log rõ ràng nếu ok == False
```
Nếu SMTP thất bại, chỉ ghi vào `self.last_message`. Không có cơ chế retry, không ghi vào database trạng thái thực (`FAILED`).

---

### L-05 🟢 LOW — `seed_initial_vessels()` KHÔNG KIỂM TRA LỖI DATABASE
**File:** `app/main.py` – dòng 28-88  
**Mô tả:**
```python
def seed_initial_vessels():
    db = SessionLocal()
    count = db.query(Vessel).count()
    if count == 0:
        ...
    db.close()  # Nếu có exception ở giữa → db.close() không được gọi!
```
Thiếu `try/finally` → database connection leak nếu có exception.

---

### L-06 🟢 LOW — URL API GSTC CHỨA SIGNED KEY TRONG CODE/CONFIG
**File:** `app/config.py` – dòng 14-17  
**Mô tả:**
```
GSTC_API_URL=...&sign=56ef085f11644f96b6b5f6200f71197c...
```
Giá trị `sign` được hardcode trong `.env.example`. Nếu repo này public trên GitHub → lộ signed key. Dù key này có thể do GSTC cấp cho trạm, cũng nên đưa vào biến môi trường riêng và không commit vào git.

---

### L-07 🟢 LOW — KHÔNG CÓ `.gitignore` CHO DATA VÀ `.env`
**File:** Thư mục gốc  
**Mô tả:**  
Không tìm thấy file `.gitignore`. Nếu dùng git, các file sau có thể bị commit nhầm:
- `data/vms_alert.db` (database chứa thông tin cá nhân ngư dân)
- `.env` (chứa SMTP password, cookie)
- `data/sent_emails/` (nội dung email cảnh báo)

---

## PHẦN 5: TÍNH NĂNG CẦN BỔ SUNG

### F-01 — HỆ THỐNG ĐĂNG NHẬP / PHÂN QUYỀN (Ưu tiên cao nhất)
- Login form với username/password
- JWT session token hoặc HTTP Session cookie (httponly, secure)
- Phân quyền: Admin (toàn quyền) / Viewer (chỉ xem)
- Logout + session timeout

### F-02 — EXPORT DỮ LIỆU (Excel/PDF)
- Export danh sách tàu ra Excel theo trạng thái
- Export nhật ký cảnh báo theo khoảng thời gian
- Export báo cáo tổng hợp hàng tháng (theo yêu cầu nghiệp vụ)

### F-03 — TÌM KIẾM VÀ PHÂN TRANG PHÍA SERVER
- Server-side search với index database
- Pagination API (offset/limit hoặc cursor-based)
- Lọc theo khoảng thời gian mất tín hiệu

### F-04 — LỊCH SỬ HÀNH TRÌNH TÀU (Track History)
- Hiển thị polyline lịch sử tọa độ của từng tàu trên bản đồ Leaflet
- Bộ lọc theo ngày để xem hành trình từng ngày

### F-05 — NOTIFICATION CHO NHIỀU NGƯỜI NHẬN
- Hệ thống hiện chỉ gửi đến 1 email cứng (`adminnhvn@gmail.com`)
- Cần hỗ trợ danh sách nhiều email nhận (Trưởng trạm, Phó trạm, Chi cục...)
- Cấu hình qua giao diện web (không phải sửa `.env`)

### F-06 — AUDIT LOG (Nhật ký thao tác người dùng)
- Ghi lại ai thêm/xóa tàu, ai trigger scan thủ công
- Quan trọng cho hệ thống nghiệp vụ nhà nước (traceability)

### F-07 — BACKUP DATABASE TỰ ĐỘNG
- Tự động backup SQLite file theo lịch (hàng ngày/tuần)
- Compress và lưu sang thư mục backup hoặc cloud storage

### F-08 — DASHBOARD THỐNG KÊ NÂNG CAO
- Biểu đồ tỉ lệ tàu mất tín hiệu theo ngày/tháng
- Thống kê tàu hay mất tín hiệu nhất (top offenders)
- Thời gian trung bình từ mất đến khắc phục

### F-09 — QUẢN LÝ THUYỀN TRƯỞNG
- Giao diện hiện thiếu hoàn toàn phần nhập/sửa thông tin thuyền trưởng
- Form "Thêm Tàu" chỉ có thông tin chủ tàu, không có thuyền trưởng

### F-10 — CẢNH BÁO REALTIME QUA BROWSER (Push Notification / Sound)
- Khi trang web đang mở và có tàu mới mất tín hiệu → phát âm thanh cảnh báo
- Browser Notification API (nếu có permission)

---

## PHẦN 6: TỔNG HỢP THEO FILE

| File | Lỗi Critical | Lỗi High | Lỗi Medium | Lỗi Low |
|------|-------------|----------|------------|---------|
| `main.py` | — | H-04 | — | L-05 |
| `config.py` | — | — | — | L-06 |
| `models.py` | — | H-07 | M-04 | — |
| `crud.py` | — | H-07 | M-05 | — |
| `database.py` | — | — | — | — |
| `api/dashboard.py` | — | — | — | — |
| `api/vessels.py` | — | H-08 | — | — |
| `api/alerts.py` | C-02 | — | — | L-01 |
| `services/scheduler.py` | C-04 | H-01, H-05 | M-06, M-09 | L-04 |
| `services/notifier.py` | — | — | M-01 | — |
| `services/vms_client.py` | C-03 | H-02, H-06 | — | — |
| `services/geo_utils.py` | — | — | M-08 | — |
| `services/keep_alive.py` | — | — | — | — |
| `main.py` (CORS) | — | H-03 | M-07 | — |
| `templates/index.html` | — | — | M-03 | L-01 |
| `docker-compose.yml` | — | — | — | L-02 |
| `requirements.txt` | — | — | — | L-03 |
| **Toàn hệ thống** | **C-01** | — | M-02 | L-07 |

---

## PHẦN 7: KHUYẾN NGHỊ ƯU TIÊN XỬ LÝ

### 🔴 Tuần 1 (Khẩn cấp):
1. **Thêm HTTP Basic Auth** cho toàn bộ route (C-01)
2. **Fix Path Traversal** trong `/api/alerts/view-email/{filename}` (C-02)
3. **Fix bug duplicate email** mỗi chu kỳ (H-01, M-09)
4. **Fix hardcode `idx==1`** trong mock data (H-06)
5. **Fix bug logic `has_recent_signal = True`** khi không có timestamp (C-04)

### 🟠 Tuần 2-3 (Quan trọng):
6. Thêm `threading.Lock` cho scheduler (H-05)
7. Giới hạn kích thước file upload (H-08)
8. Thay `datetime.utcnow()` → `datetime.now(timezone.utc)` (H-07)
9. Bật SSL verification hoặc tìm cách xử lý cert GSTC đúng cách (H-02)
10. Lưu cookie vào DB thay vì file `.env` (C-03)

### 🟡 Tháng 2 (Cải thiện):
11. Thêm pagination cho vessels và alerts API
12. Giảm polling interval từ 5s lên 30s
13. Thêm database index cho các cột thường dùng
14. Thêm cleanup job cho `VesselPosition` cũ
15. Escape HTML trong email template

---

*Báo cáo được tạo tự động bởi hệ thống Code Audit. Mọi lỗi đề cập đều dựa trên phân tích tĩnh mã nguồn thực tế.*
