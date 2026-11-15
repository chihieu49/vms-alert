# NHẬT KÝ NÂNG CẤP HỆ THỐNG (CHANGELOG)
## Hệ Thống Giám Sát Tàu Cá VMS Alert
### Trạm Kiểm Ngư Ninh Hòa - Vạn Ninh • Chi cục Thủy sản và Biển đảo tỉnh Khánh Hòa
---

## [Phiên bản 2.1.0] - Ngày 15/11/2026

### 1. 🔑 Hệ Thống Xác Thực & Phân Quyền Người Dùng (Authentication & RBAC)
- **Chuẩn hóa xác thực:** Sử dụng mã hóa mật khẩu một chiều an toàn chuẩn OWASP **PBKDF2-HMAC-SHA256** kết hợp mã định danh phiên **JWT (PyJWT)** lưu trữ trong cookie `HttpOnly`, `SameSite=Lax` chống hoàn toàn tấn công XSS và CSRF.
- **Phân quyền 3 cấp độ:**
  - 👑 **Admin (Quản trị viên):** Toàn quyền quản trị hệ thống, thêm/sửa/xóa tàu, quản lý người dùng, nạp file, quét thủ công.
  - 🛡️ **Supervisor (Giám sát viên):** Xem bản đồ, tra cứu danh sách tàu, kích hoạt quét đối chiếu thủ công, xuất báo cáo Excel/PDF.
  - 👁️ **Viewer (Chỉ xem):** Tra cứu thông tin tàu, xem bản đồ hải đồ và lịch sử cảnh báo, không được thay đổi dữ liệu.
- **Trang đăng nhập chuyên nghiệp (`/login`):** Thiết kế giao diện hiện đại theo nhận diện thương hiệu của Trạm Kiểm Ngư Ninh Hòa - Vạn Ninh, hỗ trợ phím nạp nhanh tài khoản dùng thử và ẩn/hiện mật khẩu.
- **Tài khoản khởi tạo mặc định:**
  - `admin` / `admin@nhvn2026` (Quản trị viên)
  - `giamsat` / `gs@nhvn2026` (Giám sát viên ca trực)
  - `khach` / `khach@nhvn2026` (Cán bộ tra cứu - Chỉ xem)

### 2. 👥 Quản Lý Người Dùng (User Management - Admin Only)
- Bổ sung tab **"Người Dùng"** trên giao diện chính (dành riêng cho Admin).
- Chức năng: Thêm cán bộ mới, sửa thông tin / phân quyền vai trò, khóa / mở khóa tài khoản, reset mật khẩu.
- Bảo vệ an toàn: Cơ chế khóa an toàn ngăn xóa Quản trị viên (Admin) duy nhất còn lại trong hệ thống và không cho tự xóa chính mình.
- Bổ sung modal **"Đổi mật khẩu cá nhân"** cho mọi cán bộ trực tiếp trên thanh công cụ góc phải màn hình.

### 3. 📊 Biểu Đồ Thống Kê Xu Hướng 7 Ngày (Chart.js)
- Thêm tab **"Biểu Đồ 7 Ngày"** hiển thị biểu đồ trực quan biến động trạng thái giám sát tàu cá trong 7 ngày gần nhất.
- Theo dõi 3 luồng dữ liệu song song:
  - 🔴 Số tàu mất kết nối (> 2h).
  - 🟢 Số tàu hoạt động bình thường (< 2h).
  - 🔵 Số tàu đã được khắc phục (Recovery - tự động chấm dứt cảnh báo).
- Tích hợp 3 thẻ KPI mini đo lường nhanh số liệu ngày hôm nay.

### 4. 🔎 Tìm Kiếm, Lọc Trạng Thái & Phân Trang (Pagination)
- **Phân trang mượt mà:** Bảng danh sách 151+ tàu cá được chia trang tự động (20 tàu / trang) kèm nút chuyển trang trước / sau và hiển thị vị trí bản ghi chính xác.
- **Tìm kiếm đa năng:** Hỗ trợ gõ tìm theo biển số, tên chủ tàu, số điện thoại, địa chỉ thường trú tức thì (real-time filtering).
- **Bộ lọc trạng thái:** Lọc theo: Tất cả / Mất kết nối (> 2h) / Bình thường / Đã khắc phục.

### 5. 📥 Xuất Dữ Liệu Báo Cáo Excel Chuyên Dụng
- **Xuất danh sách tàu (`/api/vessels/export-excel`):** Xuất toàn bộ 151 tàu cá kèm trạng thái kết nối, số chu kỳ mất, tọa độ WGS84 gần nhất và thời điểm nhận tín hiệu cuối ra file Excel `.xlsx`.
- **Xuất báo cáo cảnh báo (`/api/alerts/export-excel`):** Xuất toàn bộ lịch sử cảnh báo email tới `adminnhvn@gmail.com` và các sự kiện phục hồi (Recovery) phục vụ lưu trữ, báo cáo cơ quan cấp trên.

### 6. 🗺️ Nâng Cấp UX Hải Đồ Số & Xem Lịch Sử Hành Trình
- Bổ sung tính năng **Tooltip Hover**: Rê chuột qua marker tàu cá trên hải đồ để xem ngay tên tàu, chủ tàu và trạng thái mà không cần click mở popup.
- Bổ sung nút **"Xem Lịch Sử Vị Trí Tàu"** ngay trong popup chi tiết và trong bảng danh sách: Tra cứu các điểm tọa độ hành trình đã ghi nhận trong lịch sử từ cơ sở dữ liệu VMS.

### 7. 🛡️ Khắc Phục Các Lỗi Bảo Mật & Logic Còn Tồn Tại
- **Vá lỗ hổng C-01 (Missing Authentication):** Toàn bộ giao diện và các API quản trị đều đã được bảo vệ bởi middleware xác thực JWT và kiểm tra quyền RBAC.
- **Vá lỗ hổng C-02 (Path Traversal):** Khắc phục triệt để nguy cơ đọc trộm file hệ thống tại endpoint `/api/alerts/view-email/{filename}` bằng cách chuẩn hóa path và kiểm tra boundary an toàn.
- **Vá lỗi logic C-04 (Missing Timestamp):** Kiểm tra chặt chẽ tọa độ GPS hợp lệ khi API bên ngoài trả về dữ liệu thiếu trường thời gian.
- **Tối ưu hóa APScheduler:** Bổ sung `misfire_grace_time=3600`, `coalesce=True`, `max_instances=1` ngăn chặn tình trạng bắn trùng lặp email khi job bị delay.
- **Tự động cập nhật `DailyStats`:** Ghi nhận thống kê vào cơ sở dữ liệu sau mỗi chu kỳ đối chiếu 2 giờ.

### 8. ✅ Kết Quả Kiểm Thử Toàn Diện
- Toàn bộ **13/13 bài kiểm thử tự động** trong [test_vms_alert.py](file:///d:/OneDrive%20-%20chccomputer/DATA%20TR%E1%BA%A0M%20TS%20NINH%20HO%C3%80/N%C4%83m%202026/GS_TAUCA_NHVN/vms_alert/test_vms_alert.py) đạt tỷ lệ thành công **100%**.
