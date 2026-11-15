# HƯỚNG DẪN ĐỒNG BỘ CHÍNH XÁC VỚI BẢN ĐỒ TỔNG CỤC THỦY SẢN (GSTC)

> **Dành cho:** Trạm Kiểm ngư Ninh Hòa - Vạn Ninh / Chi cục Thủy sản và Biển đảo tỉnh Khánh Hòa  
> **Mục tiêu:** Đảm bảo bản đồ giám sát tàu cá của ứng dụng khớp **100% vị trí GPS thời gian thực** với Bản đồ của Tổng cục Thủy sản (`https://gstc.tongcucthuysan.gov.vn`).

---

## 🎯 TẠI SAO CẦN ĐỒNG BỘ TỌA ĐỘ VỚI TỔNG CỤC?

Cổng thông tin Giám sát tàu cá của Tổng cục Thủy sản (`gstc.tongcucthuysan.gov.vn`) yêu cầu **Phiên làm việc bảo mật (Session Cookie / Tài khoản trạm)** để cho phép truy xuất dữ liệu vị trí GPS thực tế. 

Nếu ứng dụng chưa được cấp phiên đăng nhập, hệ thống sẽ hiển thị vị trí mô phỏng ngư trường. Để bản đồ hiển thị **chính xác 100% từng mét tọa độ GPS thực tế**, cán bộ sử dụng 1 trong 2 cách sau:

---

## 🚀 CÁCH 1: NẠP FILE XUẤT TỪ BẢN ĐỒ TỔNG CỤC (NHANH NHẤT - 1 GIÂY LÀ XONG)

Đây là cách đơn giản và chính xác nhất, không cần phải nhớ cấu hình API hay Cookie:

### Bước 1: Xuất dữ liệu từ Bản đồ Tổng cục
1. Truy cập vào Cổng Tổng cục Thủy sản: **[https://gstc.tongcucthuysan.gov.vn/Map](https://gstc.tongcucthuysan.gov.vn/Map)**
2. Đăng nhập tài khoản của Trạm hoặc Chi cục.
3. Trên giao diện Bản đồ, bấm vào nút **"Xuất danh sách tàu"** (hoặc "Xuất Excel" / "Tải dữ liệu").
   - Trình duyệt sẽ tải về máy một file Excel (`.xlsx`, `.xls`) hoặc `.csv`.

### Bước 2: Nạp vào Ứng dụng VMS Alert
1. Mở giao diện ứng dụng VMS Alert (bản web).
2. Tại banner màu xanh trên cùng hoặc góc trên Bản đồ, bấm nút: **"⚡ Nạp File Tọa Độ GSTC"** (hoặc **"Đồng Bộ GSTC"** -> chọn thẻ *Cách 1: Nạp File Xuất Từ GSTC*).
3. Chọn file vừa tải về ở Bước 1 và nhấn: **"Đồng Bộ Tọa Độ Thực Tế Ngay"**.
4. **Kết quả:** Ngay lập tức toàn bộ 146 tàu cá sẽ nhảy về đúng tọa độ GPS thời gian thực trên bản đồ, hiển thị huy hiệu `🟢 GPS Thực Tế GSTC (WGS84)` kèm thời gian phát tín hiệu chuẩn xác!

---

## 🔑 CÁCH 2: KẾT NỐI API TỰ ĐỘNG MỖI 2 GIỜ (COOKIE HOẶC TÀI KHOẢN)

Để ứng dụng tự động kết nối máy chủ Tổng cục và lấy tọa độ GPS mới mỗi 2 giờ liên tục mà không cần nạp file thủ công:

### Lựa chọn 2A: Đăng nhập tài khoản GSTC trực tiếp
1. Bấm nút **"Đồng Bộ GSTC"** trên thanh tiêu đề ứng dụng.
2. Chọn thẻ: **"Cách 2: Kết Nối Trực Tiếp API (2H)"**.
3. Điền **Tên đăng nhập** và **Mật khẩu** của tài khoản Tổng cục Thủy sản.
4. Nhấn **"Đăng Nhập & Kết Nối GSTC"**.
   - Ứng dụng sẽ tự động gửi yêu cầu xác thực tới máy chủ GSTC, lưu phiên làm việc và duy trì chu kỳ quét mỗi 2 giờ.

### Lựa chọn 2B: Dán chuỗi Cookie từ trình duyệt
Nếu tài khoản có xác thực riêng hoặc không muốn nhập mật khẩu:
1. Đăng nhập vào `https://gstc.tongcucthuysan.gov.vn` trên trình duyệt Chrome / Cốc Cốc / Edge.
2. Nhấn phím **F12** (hoặc chuột phải chọn *Kiểm tra / Inspect*).
3. Chuyển sang tab **Application** (hoặc *Ứng dụng*) -> mục **Cookies** -> chọn `https://gstc.tongcucthuysan.gov.vn`.
4. Tìm giá trị của Cookie `.ASPXAUTH` hoặc copy toàn bộ chuỗi Cookie từ Network Tab.
5. Dán vào ô **"Dán Session Cookie từ trình duyệt"** trên ứng dụng VMS Alert và bấm **"Lưu Cookie & Đồng Bộ"**.

---

## 🗺️ TÍNH NĂNG TRÊN BẢN ĐỒ HẢI ĐỒ SAU KHI ĐỒNG BỘ

- **2 Lớp Bản Đồ:**
  - **Ảnh Vệ Tinh (Esri World Imagery):** Hình ảnh thực tế bờ biển, hải đảo giống hệt bản đồ vệ tinh của Tổng cục Thủy sản.
  - **Bản Đồ Đường Bộ (OpenStreetMap):** Chi tiết tên địa danh, xã, phường, cảng cá.
- **Lớp Hải Đồ OpenSeaMap:** Hiển thị phao luồng, hải đăng, độ sâu luồng tàu chạy.
- **Thước đo tỉ lệ Hải lý:** Giúp cán bộ trạm đo nhanh khoảng cách tàu đến bờ biển hoặc đến ranh giới cho phép.
- **Popup Chi Tiết Tàu:**
  - Số ĐK, Tên chủ tàu, Số điện thoại, Địa chỉ (đầy đủ theo quy chuẩn IUU).
  - Tọa độ GPS chuẩn WGS84 dạng thập phân: `12.58421°N, 109.31456°E`.
  - Tọa độ Hải đồ chuẩn Độ-Phút-Giây (DMS): `12°35'03.2"N - 109°18'52.4"E`.
  - Nguồn tọa độ: `🟢 GPS Thực Tế GSTC (WGS84)`.
  - Thời điểm phát tín hiệu cuối cùng.

---

## 📧 CƠ CHẾ CẢNH BÁO EMAIL VÀ KHẮC PHỤC

1. **Chu kỳ kiểm tra:** Định kỳ mỗi 2 giờ (120 phút).
2. **Cảnh báo mất kết nối:** Khi tàu có trong danh sách nhưng không có vị trí mới sau chu kỳ 2 giờ $\rightarrow$ Tự động gửi email cảnh báo tới **`adminnhvn@gmail.com`** với đầy đủ 4 trường:
   - **Số đăng ký** (`plate_number`)
   - **Tên chủ tàu** (`owner_name`)
   - **Số điện thoại** (`owner_phone`)
   - **Địa chỉ của tàu** (`owner_address`)
3. **Cơ chế khắc phục (Recovery):** Nếu trong chu kỳ 2 giờ tiếp theo, tàu đã quay lại và báo vị trí bình thường $\rightarrow$ Hệ thống **tự động chấm dứt việc gửi thông báo**, chuyển trạng thái sang `RECOVERED` và không gửi email làm phiền.

