# -*- coding: utf-8 -*-
# PowerShell script đẩy mã nguồn vms_alert lên GitHub chuẩn xác 100%
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$Host.UI.RawUI.WindowTitle = "HỖ TRỢ ĐẨY MÃ NGUỒN VMS ALERT LÊN GITHUB (RENDER DEPLOY)"

Clear-Host
Write-Host "===============================================================================" -ForegroundColor Cyan
Write-Host "         TIEN ICH DAY MA NGUON VMS ALERT LEN GITHUB (RENDER.COM)              " -ForegroundColor Yellow
Write-Host "===============================================================================" -ForegroundColor Cyan
Write-Host ""

# Chuyển về thư mục hiện tại
$currentDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -Path $currentDir
Write-Host "[*] Thu muc lam viec: $currentDir" -ForegroundColor Gray

# 1. Kiểm tra Git
$gitCmd = Get-Command git -ErrorAction SilentlyContinue
if (-not $gitCmd) {
    Write-Host "[LOI] May tinh chua cai dat Git!" -ForegroundColor Red
    Write-Host "Vui long tai va cai dat Git tu trang: https://git-scm.com/download/win" -ForegroundColor White
    Write-Host ""
    Read-Host "Nhan Enter de thoat..."
    exit 1
}

$gitVer = git --version
Write-Host "[OK] Da tim thay Git: $gitVer" -ForegroundColor Green
Write-Host ""

# 2. Kiểm tra cấu hình git user
$userName = git config --global user.name
$userEmail = git config --global user.email

if (-not $userName -or -not $userEmail) {
    Write-Host "[*] Thiet lap thong tin tac gia Git..." -ForegroundColor Yellow
    if (-not $userName) {
        $inputName = Read-Host "Nhap Ten cua ban tren GitHub (vi du: Tram Thuy San Ninh Hoa)"
        if (-not $inputName) { $inputName = "Tram Thuy San Ninh Hoa" }
        git config --global user.name "$inputName"
    }
    if (-not $userEmail) {
        $inputEmail = Read-Host "Nhap Email cua ban tren GitHub (vi du: adminnhvn@gmail.com)"
        if (-not $inputEmail) { $inputEmail = "adminnhvn@gmail.com" }
        git config --global user.email "$inputEmail"
    }
    Write-Host "[OK] Da luu cau hinh Git." -ForegroundColor Green
    Write-Host ""
}

# 3. Khởi tạo Git Repo
Write-Host "[Buoc 1] Khoi tao Git repository..." -ForegroundColor Yellow
if (-not (Test-Path ".git")) {
    git init
    git branch -M main
    Write-Host "[OK] Da khoi tao Git repository local va nhanh main." -ForegroundColor Green
} else {
    git branch -M main
    Write-Host "[OK] Git repository da ton tai san." -ForegroundColor Green
}
Write-Host ""

# 4. Add và Commit
Write-Host "[Buoc 2] Dang them ma nguon vao commit..." -ForegroundColor Yellow
git add .
$status = git status --porcelain
if ($status) {
    git commit -m "Deploy VMS Alert System Ninh Hoa to Render"
    Write-Host "[OK] Da commit toan bo ma nguon moi nhat." -ForegroundColor Green
} else {
    Write-Host "[INFO] Ma nguon da o trang thai commit moi nhat." -ForegroundColor Cyan
}
Write-Host ""

# 5. Nhập URL GitHub Repo
Write-Host "===============================================================================" -ForegroundColor Cyan
Write-Host "NHAP LINK GITHUB REPOSITORY CUA BAN:" -ForegroundColor Yellow
Write-Host "Vi du: https://github.com/ten-tai-khoan/vms-alert.git" -ForegroundColor White
Write-Host "(Luu y: Ban can vao https://github.com/new de tao Repository moi truoc)" -ForegroundColor Gray
Write-Host "===============================================================================" -ForegroundColor Cyan

$repoUrl = Read-Host "Dan link GitHub vao day roi nhan Enter"
$repoUrl = $repoUrl.Trim()

if (-not $repoUrl) {
    Write-Host ""
    Write-Host "[CANH BAO] Ban chua nhap link GitHub! Qua trinh tam dung." -ForegroundColor Red
    Write-Host "Hay tao Repository tren GitHub roi chay lai file nay." -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Nhan Enter de thoat..."
    exit 0
}

Write-Host ""
Write-Host "[Buoc 3] Dang ket noi toi: $repoUrl ..." -ForegroundColor Yellow
git remote remove origin 2>$null
git remote add origin $repoUrl

Write-Host ""
Write-Host "[Buoc 4] Dang day (push) code len nhanh main cua GitHub..." -ForegroundColor Yellow
Write-Host "(Neu GitHub yeu cau dang nhap, hay dang nhap bang trinh duyet Browser hoac Token)" -ForegroundColor Gray
Write-Host ""

git push -u origin main

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "===============================================================================" -ForegroundColor Green
    Write-Host "           [THANH CONG!] TOAN BO MA NGUON DA DUOC DAY LEN GITHUB!             " -ForegroundColor Green
    Write-Host "===============================================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "CAC BUOC TIEP THEO DE DEPLOY LEN RENDER (24/7 MIEN PHI):" -ForegroundColor Yellow
    Write-Host "1. Truy cap https://dashboard.render.com" -ForegroundColor White
    Write-Host "2. Bam 'New +' -> Chon 'Web Service' (hoac 'Blueprint')" -ForegroundColor White
    Write-Host "3. Ket noi voi Repository GitHub ban vua day len" -ForegroundColor White
    Write-Host "4. Render se tu dong doc file render.yaml / Dockerfile va khoi chay 100%!" -ForegroundColor White
    Write-Host ""
} else {
    Write-Host ""
    Write-Host "===============================================================================" -ForegroundColor Red
    Write-Host "                     [CHUA THE DAY CODE LEN GITHUB]                           " -ForegroundColor Red
    Write-Host "===============================================================================" -ForegroundColor Red
    Write-Host "Nguyen nhan thuong gap:" -ForegroundColor Yellow
    Write-Host "1. Repository tren GitHub chua duoc tao (Vao https://github.com/new tao moi)" -ForegroundColor White
    Write-Host "2. Chua dang nhap GitHub hoac sai quyen truy cap." -ForegroundColor White
    Write-Host "3. Neu Repository tren GitHub da co san file README/License, ban hay chay lenh:" -ForegroundColor White
    Write-Host "   git push -f -u origin main" -ForegroundColor Cyan
    Write-Host ""
}

Read-Host "Nhan Enter de dong cua so nay..."
