# VMS Alert System - Hệ Thống Giám Sát Tàu Cá Chuyên Dụng
### Trạm Thủy Sản Ninh Hòa - Chi Cục Thủy Sản Tỉnh Khánh Hòa

---

## 1. Giới thiệu
Ứng dụng giám sát hành trình tàu cá chuyên dụng theo chuẩn **FastAPI + APScheduler + SQLAlchemy + HTMX + Tailwind CSS + Leaflet**, theo dõi các tàu cá có **chiều dài lớn nhất từ 15 mét trở lên** theo quy định chống khai thác IUU:
- **Chu kỳ kiểm tra**: Định kỳ **mỗi 2 giờ** truy xuất dữ liệu từ API Cổng thông tin Tổng cục Thủy sản.
- **Phát hiện mất kết nối**: Sau chu kỳ 2 giờ không có tín hiệu vị trí cập nhật mới $\rightarrow$ tự động gửi thông báo qua Email tới **`adminnhvn@gmail.com`** với đầy đủ các trường bắt buộc:
  * **Số đăng ký** (`plate_number`)
  * **Tên chủ tàu** (`owner_name`)
  * **Số điện thoại** (`owner_phone`)
  * **Địa chỉ của tàu đó** (`owner_address`)
- **Cơ chế giám sát trạng thái khắc phục**: Nếu trong chu kỳ 2 giờ tiếp theo, tàu đã quay lại và báo vị trí bình thường $\rightarrow$ hệ thống **tự động chấm dứt việc gửi thông báo cho tàu đó**, đảm bảo chỉ cảnh báo khi có sự cố mất kết nối liên tục.

---

## 2. Cấu Trúc Dự Án
```
vms_alert/
├── app/
│   ├── main.py              # FastAPI Server + APScheduler Lifespan + Jinja2
│   ├── config.py            # Cấu hình nạp từ .env
│   ├── models.py            # Vessel, VesselState, VesselPosition, AlertHistory
│   ├── schemas.py           # Pydantic Schemas validation
│   ├── crud.py              # Thao tác cơ sở dữ liệu SQLAlchemy
│   ├── database.py          # Kết nối SQLAlchemy SQLite
│   ├── api/                 # Endpoints REST API
│   │   ├── dashboard.py     # KPI Cards & điều khiển quét ngay
│   │   ├── vessels.py       # Quản lý danh sách tàu & Nhập file Excel/CSV/JSON
│   │   └── alerts.py        # Nhật ký cảnh báo & xem email đã gửi
│   ├── services/
│   │   ├── vms_client.py    # Kết nối API GSTC (JSON + CSV + Excel + HTML)
│   │   ├── notifier.py      # Gửi cảnh báo: Email · Telegram · Zalo OA · SMS
│   │   └── scheduler.py     # Logic poll 2 giờ + đối chiếu + recovery
│   └── templates/           # Giao diện Jinja2 + HTMX + Leaflet + Tailwind
│       ├── base.html
│       ├── index.html
│       └── partials/
│           ├── stats_cards.html
│           ├── vessel_table.html
│           └── alert_feed.html
├── data/                    # Thư mục lưu DB SQLite & bản sao email đã gửi
├── docker-compose.yml       # Cấu hình chạy Docker container
├── Dockerfile               # Docker build file
├── requirements.txt         # Danh mục thư viện Python
├── .env.example             # Mẫu cấu hình môi trường
├── .env                     # File cấu hình hoạt động thực tế
├── run.bat                  # Khởi chạy 1-click trên Windows
└── README.md
```

---

## 3. Hướng Dẫn Khởi Chạy

### Cách 1: Chạy trực tiếp trên Windows (Khuyên dùng)
1. Mở thư mục `vms_alert/` và click đúp vào file **`run.bat`**.
2. Ứng dụng sẽ tự động chạy và mở trình duyệt web tại địa chỉ: `http://127.0.0.1:8000`.
3. Tài liệu API Swagger UI có sẵn tại: `http://127.0.0.1:8000/docs`.

### Cách 2: Chạy bằng lệnh Terminal
```bash
cd vms_alert
python -m app.main
```

### Cách 3: Chạy bằng Docker Compose
```bash
cd vms_alert
docker-compose up -d
```

