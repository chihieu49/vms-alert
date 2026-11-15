@echo off
chcp 65001 > nul
title HỆ THỐNG GIÁM SÁT TÀU CÁ CHUYÊN DỤNG (VMS ALERT) - TRẠM THỦY SẢN NINH HÒA
color 0b

echo ===============================================================================
echo          HỆ THỐNG GIÁM SÁT TÀU CÁ CHUYÊN DỤNG (VMS ALERT SYSTEM)
echo               TRẠM THỦY SẢN NINH HÒA - CHI CỤC THỦY SẢN
echo ===============================================================================
echo.

cd /d "%~dp0"

:: 1. Kiểm tra Python
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [LỖI] Máy tính này chưa cài đặt Python hoặc chưa tick "Add Python to PATH"!
    echo Vui lòng tải và cài đặt Python từ: https://www.python.org/downloads/
    echo Khi cài nhớ tích chọn: [x] Add Python to PATH.
    pause
    exit /b
)

:: 2. Kiểm tra và cài đặt dependencies tự động nếu thiếu
echo [*] Đang kiểm tra thư viện hệ thống...
python -c "import fastapi, uvicorn, sqlalchemy, apscheduler, pandas, openpyxl, httpx" >nul 2>nul
if %errorlevel% neq 0 (
    echo [*] Phát hiện thiết bị mới hoặc thiếu thư viện. Đang tự động cài đặt requirements...
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo [LỖI] Không thể cài đặt thư viện. Vui lòng kiểm tra kết nối mạng Internet.
        pause
        exit /b
    )
)
echo [OK] Thư viện hệ thống đầy đủ sẵn sàng.
echo.

:: 3. Lấy địa chỉ IP nội bộ của máy
for /f "tokens=*" %%a in ('powershell -Command "(Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.InterfaceAlias -notlike '*Loopback*' -and $_.IPAddress -notlike '169.*'}).IPAddress | Select-Object -First 1"') do set LOCAL_IP=%%a

echo ===============================================================================
echo  HƯỚNG DẪN TRUY CẬP HỆ THỐNG:
echo    - Truy cập trên máy tính này:     http://localhost:8000
if not "%LOCAL_IP%"=="" (
echo    - Truy cập từ ĐIỆN THOẠI / IPAD:  http://%LOCAL_IP%:8000  (Chung Wi-Fi)
echo    - Truy cập từ MÁY TÍNH KHÁC:      http://%LOCAL_IP%:8000  (Chung Wi-Fi)
)
echo ===============================================================================
echo.
echo [*] Khởi động ứng dụng VMS Alert (FastAPI + APScheduler 2h)...
echo [*] Nhấn Ctrl+C để dừng máy chủ khi cần.
echo.

python -m app.main

pause
