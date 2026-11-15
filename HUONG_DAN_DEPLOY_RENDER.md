# HƯỚNG DẪN TRIỂN KHAI VMS ALERT LÊN RENDER (RENDER.COM)
### THEO DÕI TÀU CÁ 24/7 LIÊN TỤC • KHÔNG PHỤ THUỘC VÀO MÁY TÍNH CÁ NHÂN

---

## 🌟 Vì Sao Nên Đưa Lên Render?
* **Hoạt động 24/7 liên tục**: Không lo bị gián đoạn khi tắt máy tính, sleep máy hoặc mất điện/mất mạng tại trạm.
* **Theo dõi mọi lúc mọi nơi**: Cán bộ trạm có thể mở link từ **Điện thoại, iPad, Laptop** ở bất cứ đâu (kể cả khi đi tuần tra, công tác ngoài biển).
* **Hoàn toàn miễn phí (Free Tier)**: Render hỗ trợ gói Free Web Service không tốn chi phí.
* **Tự động đối chiếu chu kỳ 2 giờ**: APScheduler chạy ngầm trên Cloud, tự động gửi email cảnh báo về `adminnhvn@gmail.com`.

---

## BƯỚC 1: Đưa Mã Nguồn `vms_alert` Lên GitHub

1. Truy cập [https://github.com](https://github.com) và đăng nhập tài khoản.
2. Bấm nút **New** (Tạo Repository mới):
   - Đặt tên repository: `vms-alert` (hoặc `gs-tauca-ninhhoa`).
   - Chọn chế độ: **Public** hoặc **Private**.
   - Bấm **Create repository**.
3. Mở thư mục `vms_alert` trên máy tính, mở PowerShell/CMD hoặc chạy file `push_github.bat` (được tạo sẵn), gõ các lệnh sau:

```bash
cd "D:\OneDrive - chccomputer\DATA TRẠM TS NINH HOÀ\Năm 2026\GS_TAUCA_NHVN\vms_alert"
git init
git add .
git commit -m "Khoi tao he thong VMS Alert Ninh Hoa"
git branch -M main
git remote add origin https://github.com/TÊN_GITHUB_CỦA_BẠN/vms-alert.git
git push -u origin main
```
*(Thay `TÊN_GITHUB_CỦA_BẠN` bằng username GitHub thực tế của bạn)*

---

## BƯỚC 2: Tạo Web Service Trên Render.com

1. Truy cập [https://render.com](https://render.com) và bấm **Get Started** hoặc **Log In** (nên chọn **Sign in with GitHub** để tự động liên kết tài khoản).
2. Tại màn hình Dashboard Render, bấm nút **New +** ở góc trên bên phải $\rightarrow$ Chọn **Web Service**.
3. Chọn mục **Build and deploy from a Git repository** $\rightarrow$ Bấm **Next**.
4. Chọn repository `vms-alert` bạn vừa tải lên ở Bước 1 $\rightarrow$ Bấm **Connect**.
5. Điền thông tin cấu hình như sau:
   - **Name**: `vms-alert-ninhhoa` (hoặc tên tùy thích).
   - **Region**: Chọn **Singapore** (vị trí gần Việt Nam nhất, tốc độ kết nối API Tổng Cục Thủy Sản nhanh nhất).
   - **Branch**: `main`.
   - **Runtime**: `Python 3`.
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Instance Type**: Chọn **Free** ($0/month).

---

## BƯỚC 3: Cấu Hình Biến Môi Trường (Environment Variables)

Cuộn xuống phần **Environment Variables**, bấm nút **Add Environment Variable** để thêm các thông số:

| Tên biến (Key) | Giá trị (Value) | Giải thích |
| :--- | :--- | :--- |
| `ADMIN_EMAIL` | `adminnhvn@gmail.com` | Email nhận cảnh báo mất kết nối VMS |
| `POLL_INTERVAL_MINUTES` | `120` | Chu kỳ đối chiếu (120 phút = 2 giờ) |
| `LOST_SIGNAL_THRESHOLD_MINUTES` | `120` | Ngưỡng xác định mất kết nối (2 giờ) |
| `KEEP_ALIVE_ENABLED` | `true` | Tự động giữ ứng dụng luôn chạy 24/7 |
| `SMTP_USER` | *(Tài khoản Gmail của trạm)* | Ví dụ: `tramthuisanninhhoa@gmail.com` |
| `SMTP_PASSWORD` | *(Mật khẩu ứng dụng 16 số của Gmail)* | Mật khẩu ứng dụng Google App Password |
| `GSTC_COOKIE` | *(Cookie phiên đăng nhập GSTC nếu có)* | Cung cấp cookie nếu API yêu cầu |

Bấm nút **Create Web Service**.  
Render sẽ tự động tải mã nguồn, cài đặt thư viện và khởi chạy hệ thống trong vòng 1-2 phút.

---

## BƯỚC 4: Lấy Link Truy Cập & Giữ Ứng Dụng Chạy 24/7 Không Ngủ

1. Khi Render build xong, bạn sẽ thấy thông báo **Live** màu xanh lá và đường link website có dạng:  
   👉 `https://vms-alert-ninhhoa.onrender.com`
2. **Cơ chế chống ngủ đông (Keep-Alive)**:
   - Gói Render Free thường sẽ "ngủ" (Sleep) nếu sau 15 phút không có người vào web.
   - **Ứng dụng đã được tích hợp sẵn service `keep_alive.py`**: Mỗi 10 phút, hệ thống sẽ tự động ping vào endpoint `/health` của chính nó để giữ Web Service luôn thức (Always Active), đảm bảo chu kỳ quét 2 giờ chạy liên tục không bị dừng!
3. **Mẹo bổ sung để đảm bảo 100% không bao giờ gián đoạn**:
   - Truy cập trang web miễn phí [https://cron-job.org](https://cron-job.org) hoặc [https://uptimerobot.com](https://uptimerobot.com).
   - Tạo 1 cron job ping vào link: `https://vms-alert-ninhhoa.onrender.com/health` mỗi 10 phút/lần.
   - Khi đó ứng dụng sẽ hoạt động bền bỉ quanh năm suốt tháng 24/7 hoàn toàn miễn phí!

---

## BƯỚC 5: Hướng Dẫn Sử Dụng Trên Điện Thoại & Máy Tính Khác

* **Khi chạy trên Render (Khuyên dùng)**:  
  Chỉ cần gửi link Render (ví dụ `https://vms-alert-ninhhoa.onrender.com`) cho các cán bộ trong trạm. Mọi người có thể mở bằng bất kỳ trình duyệt nào trên điện thoại (Safari, Chrome...) hoặc máy tính để xem tọa độ các tàu trên bản đồ, danh sách mất kết nối và lịch sử xử lý.
* **Khi chạy trên mạng nội bộ tại Trạm (Local Wi-Fi)**:  
  Chỉ cần máy tính chủ click đúp `run.bat`. Màn hình sẽ hiện địa chỉ IP mạng nội bộ (ví dụ: `http://192.168.1.15:8000`). Các cán bộ khác chỉ cần kết nối cùng Wi-Fi trạm và gõ địa chỉ này vào điện thoại là truy cập được ngay lập tức.

