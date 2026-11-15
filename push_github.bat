@echo off
setlocal
cd /d "%~dp0"

REM Kiem tra PowerShell co san khong
where powershell >nul 2>nul
if %errorlevel% equ 0 (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0push_github.ps1"
    goto :eof
)

REM Fallback bang Batch thuan ASCII neu khong co PowerShell
title DAY MA NGUON LEN GITHUB
color 0a

echo ===============================================================================
echo                DAY MA NGUON VMS ALERT LEN GITHUB (RENDER DEPLOY)
echo ===============================================================================
echo.

where git >nul 2>nul
if %errorlevel% neq 0 (
    echo [LOI] May tinh chua cai dat Git!
    echo Vui long tai va cai dat Git tu: https://git-scm.com/
    pause
    exit /b
)

echo [1/4] Khoi tao Git repo...
if not exist ".git" (
    git init
    git branch -M main
) else (
    git branch -M main
)

echo.
echo [2/4] Commit ma nguon...
git add .
git commit -m "Deploy VMS Alert System Ninh Hoa to Render"

echo.
echo ===============================================================================
echo Nhap link GitHub Repository cua ban
echo (Vi du: https://github.com/username/vms-alert.git)
echo ===============================================================================
set /p REPO_URL="Dan link GitHub vao day roi nhan Enter: "

if "%REPO_URL%"=="" (
    echo [!] Chua nhap link. Qua trinh dung lai.
    pause
    exit /b
)

git remote remove origin >nul 2>nul
git remote add origin %REPO_URL%

echo.
echo [3/4] Dang day code len GitHub...
git push -u origin main

if %errorlevel% equ 0 (
    echo.
    echo ===============================================================================
    echo [THANH CONG] Toan bo ma nguon da duoc day len GitHub!
    echo Ban co the vao https://render.com de ket noi repo va deploy.
    echo ===============================================================================
) else (
    echo.
    echo [CANH BAO] Chua the push code len GitHub.
    echo Hay kiem tra xem ban da tao repo tren GitHub va dang nhap chua.
)

pause
