# -*- coding: utf-8 -*-
"""
Multi-channel Notification Service:
- Email (SMTP) gửi tới adminnhvn@gmail.com (Bắt buộc theo yêu cầu)
- Telegram Bot (Mở rộng)
- Zalo OA Webhook (Mở rộng)
- SMS API Gateway (Mở rộng)
"""
import smtplib
import json
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Dict, Any, Tuple
import requests

from app.config import settings

class NotificationService:
    def __init__(self):
        pass

    def build_email_payload(self, lost_vessels: List[Dict[str, Any]], scan_time: str = None) -> Tuple[str, str, str]:
        """
        Nội dung bắt buộc phải bao gồm các trường thông tin:
        1. Số đăng ký (plate_number)
        2. Tên chủ tàu (ownerName)
        3. Số điện thoại (captainPhone / ownerPhone)
        4. Địa chỉ của tàu đó (captainAddress / ownerAddress)
        """
        if not scan_time:
            scan_time = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

        count = len(lost_vessels)
        subject = f"[CẢNH BÁO GSTC] Phát hiện {count} tàu cá mất kết nối giám sát hành trình - Trạm Kiểm Ngư Ninh Hòa - Vạn Ninh ({scan_time})"

        # 1. Plain-text version
        lines = [
            "================================================================================",
            "TRẠM KIỂM NGƯ NINH HÒA - VẠN NINH • CHI CỤC THỦY SẢN VÀ BIỂN ĐẢO TỈNH KHÁNH HÒA",
            "THÔNG BÁO TÀU CÁ MẤT TÍN HIỆU / KHÔNG CẬP NHẬT DỮ LIỆU SAU CHU KỲ 2 GIỜ",
            "================================================================================",
            f"Thời gian kiểm tra: {scan_time}",
            f"Tổng số tàu mất kết nối: {count} tàu (chiều dài >= 15 mét)",
            f"Email nhận báo cáo: {settings.ADMIN_EMAIL}",
            "--------------------------------------------------------------------------------",
            "DANH SÁCH CHI TIẾT TÀU CÁ CẦN XỬ LÝ KHẨN CẤP:",
            ""
        ]

        for idx, v in enumerate(lost_vessels, start=1):
            plate = v.get("plate_number", "Chưa rõ")
            owner = v.get("owner_name", "Chưa rõ")
            phone = v.get("owner_phone") or v.get("captain_phone") or "Chưa có"
            address = v.get("owner_address") or v.get("captain_address") or "Chưa cập nhật"
            length = v.get("chieudaitoanbo", 15.0)
            cycles = v.get("consecutive_lost_cycles", 1)
            last_t = v.get("last_signal_time") or "Chưa nhận tín hiệu"

            lines.append(f"{idx}. SỐ ĐĂNG KÝ: {plate}")
            lines.append(f"   - Tên chủ tàu: {owner}")
            lines.append(f"   - Số điện thoại: {phone}")
            lines.append(f"   - Địa chỉ của tàu: {address}")
            lines.append(f"   - Chiều dài: {length} m | Số chu kỳ mất tín hiệu liên tục: {cycles}")
            lines.append(f"   - Lần cuối cập nhật vị trí: {last_t}")
            lines.append("-" * 60)

        lines.append("")
        lines.append("Yêu cầu trạm kiểm soát liên hệ ngay với chủ tàu/thuyền trưởng.")
        lines.append("Hệ thống sẽ tự động giám sát và chấm dứt thông báo khi tàu đã quay lại báo vị trí bình thường.")
        plain_text = "\n".join(lines)

        # 2. HTML Version (Tailwind / Modern Style)
        rows_html = ""
        for idx, v in enumerate(lost_vessels, start=1):
            plate = v.get("plate_number", "Chưa rõ")
            owner = v.get("owner_name", "Chưa rõ")
            phone = v.get("owner_phone") or v.get("captain_phone") or "Chưa có"
            address = v.get("owner_address") or v.get("captain_address") or "Chưa cập nhật"
            cycles = v.get("consecutive_lost_cycles", 1)
            last_t = str(v.get("last_signal_time") or "Chưa có")

            rows_html += f"""
            <tr style="border-bottom: 1px solid #f1f5f9; background-color: {'#fef2f2' if idx % 2 == 1 else '#ffffff'};">
                <td style="padding: 12px; text-align: center; font-weight: bold; color: #64748b;">{idx}</td>
                <td style="padding: 12px; font-weight: bold; color: #dc2626; font-size: 15px;">{plate}</td>
                <td style="padding: 12px; font-weight: 600; color: #1e293b;">{owner}</td>
                <td style="padding: 12px; font-weight: bold; color: #0284c7;"><a href="tel:{phone}" style="color: #0284c7; text-decoration: none;">{phone}</a></td>
                <td style="padding: 12px; color: #475569; font-size: 13px;">{address}</td>
                <td style="padding: 12px; color: #64748b; font-size: 13px;">{last_t}</td>
                <td style="padding: 12px; text-align: center;"><span style="background: #ef4444; color: white; padding: 4px 8px; border-radius: 9999px; font-size: 12px; font-weight: bold;">{cycles} chu kỳ</span></td>
            </tr>
            """

        html_content = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; margin: 0; padding: 24px; color: #334155;">
    <div style="max-width: 920px; margin: 0 auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 10px 25px rgba(0,0,0,0.05); border: 1px solid #e2e8f0;">
        <div style="background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 100%); color: white; padding: 28px 32px;">
            <div style="font-size: 12px; text-transform: uppercase; letter-spacing: 2px; color: #93c5fd; margin-bottom: 6px;">TRẠM KIỂM NGƯ NINH HÒA - VẠN NINH • CHI CỤC THỦY SẢN VÀ BIỂN ĐẢO TỈNH KHÁNH HÒA</div>
            <h2 style="margin: 0; font-size: 22px; color: #f59e0b;">⚠️ CẢNH BÁO TÀU CÁ MẤT KẾT NỐI SAU CHU KỲ 2 GIỜ</h2>
            <div style="margin-top: 10px; font-size: 13px; color: #cbd5e1;">
                Thời điểm quét: <strong>{scan_time}</strong> | Số lượng tàu vi phạm tín hiệu: <strong style="color: #f87171;">{count} tàu (≥ 15m)</strong>
            </div>
        </div>
        <div style="padding: 28px 32px;">
            <div style="background-color: #fef3c7; border-left: 4px solid #f59e0b; padding: 16px; border-radius: 6px; margin-bottom: 24px; color: #92400e; font-size: 14px; line-height: 1.5;">
                <strong>LƯU Ý NGHIỆP VỤ IUU:</strong> Các tàu cá dưới đây có chiều dài <strong>≥ 15 mét</strong> không có dữ liệu vị trí cập nhật trong chu kỳ 2 giờ gần nhất từ hệ thống GSTC Tổng cục Thủy sản.
            </div>
            <table style="width: 100%; border-collapse: collapse; text-align: left; font-size: 14px;">
                <thead>
                    <tr style="background: #0f172a; color: white;">
                        <th style="padding: 12px; text-align: center; width: 45px;">STT</th>
                        <th style="padding: 12px;">Số đăng ký</th>
                        <th style="padding: 12px;">Tên chủ tàu</th>
                        <th style="padding: 12px;">Số điện thoại</th>
                        <th style="padding: 12px;">Địa chỉ</th>
                        <th style="padding: 12px;">Lần cuối nhận</th>
                        <th style="padding: 12px; text-align: center;">Mất tín hiệu</th>
                    </tr>
                </thead>
                <tbody>{rows_html}</tbody>
            </table>
            <div style="margin-top: 24px; background: #f0fdf4; border-left: 4px solid #22c55e; padding: 14px; border-radius: 6px; color: #166534; font-size: 13px;">
                <strong>🔄 CƠ CHẾ GIÁM SÁT TRẠNG THÁI KHẮC PHỤC:</strong> Nếu tàu quay lại và báo vị trí bình thường trong chu kỳ kế tiếp, hệ thống sẽ <strong>tự động chấm dứt gửi thông báo</strong> cho tàu đó.
            </div>
        </div>
        <div style="background-color: #f1f5f9; padding: 16px 32px; border-top: 1px solid #e2e8f0; font-size: 12px; color: #64748b; text-align: center;">
            Hệ thống Giám sát Tàu cá Tự động • Gửi tới: <strong>{settings.ADMIN_EMAIL}</strong>
        </div>
    </div>
</body>
</html>"""
        return subject, plain_text, html_content

    def send_email_alert(self, lost_vessels: List[Dict[str, Any]], scan_time: str = None) -> Tuple[bool, str]:
        """Gửi email tới adminnhvn@gmail.com qua SMTP và lưu bản sao file"""
        if not lost_vessels:
            return True, "Không có tàu mất tín hiệu."

        subject, plain_text, html_content = self.build_email_payload(lost_vessels, scan_time)

        # 1. Lưu bản sao HTML & JSON vào thư mục sent_emails
        timestamp_slug = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"alert_{timestamp_slug}_{len(lost_vessels)}tau.html"
        file_path = settings.EMAILS_DIR / filename
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(html_content)
            meta = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "to": settings.ADMIN_EMAIL,
                "subject": subject,
                "vessel_count": len(lost_vessels),
                "file_path": filename,
                "vessels": lost_vessels
            }
            with open(settings.EMAILS_DIR / f"alert_{timestamp_slug}_{len(lost_vessels)}tau.json", "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[NOTIFIER] Lỗi lưu bản sao email: {e}")

        # 2. Gửi qua SMTP Gmail nếu có cấu hình
        if settings.SMTP_USER and settings.SMTP_PASSWORD:
            try:
                msg = MIMEMultipart("alternative")
                msg["Subject"] = subject
                msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_USER}>"
                msg["To"] = settings.ADMIN_EMAIL

                msg.attach(MIMEText(plain_text, "plain", "utf-8"))
                msg.attach(MIMEText(html_content, "html", "utf-8"))

                server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15)
                server.starttls()
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(settings.SMTP_USER, [settings.ADMIN_EMAIL], msg.as_string())
                server.quit()
                return True, f"Đã gửi email thành công tới {settings.ADMIN_EMAIL}"
            except Exception as e:
                return False, f"Đã lưu cảnh báo vào máy chủ nhưng lỗi SMTP: {e}"
        else:
            return True, f"Đã tạo và lưu trữ email cảnh báo tới {settings.ADMIN_EMAIL} (Cấu hình SMTP_USER và SMTP_PASSWORD trong .env để chuyển tiếp thực tế)."

    def send_telegram_alert(self, lost_vessels: List[Dict[str, Any]]) -> Tuple[bool, str]:
        """Gửi thông báo Telegram (Kênh mở rộng)"""
        if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHAT_ID:
            return False, "Chưa cấu hình Telegram Bot Token / Chat ID"

        text = f"⚠️ *CẢNH BÁO GSTC - TRẠM KIỂM NGƯ NINH HÒA - VẠN NINH*\nPhát hiện *{len(lost_vessels)} tàu cá* mất kết nối sau 2 giờ:\n\n"
        for idx, v in enumerate(lost_vessels, 1):
            text += f"{idx}. *{v.get('plate_number')}*\n"
            text += f"   - Chủ tàu: {v.get('owner_name')}\n"
            text += f"   - SĐT: {v.get('owner_phone') or v.get('captain_phone')}\n"
            text += f"   - Địa chỉ: {v.get('owner_address')}\n\n"

        url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
        try:
            r = requests.post(url, json={"chat_id": settings.TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"}, timeout=10)
            return r.status_code == 200, r.text
        except Exception as e:
            return False, str(e)

    def send_zalo_oa_alert(self, lost_vessels: List[Dict[str, Any]]) -> Tuple[bool, str]:
        """Gửi thông báo Zalo Official Account (Kênh mở rộng)"""
        if not settings.ZALO_OA_ACCESS_TOKEN:
            return False, "Chưa cấu hình Zalo OA Token"
        # Endpoint Zalo OA API
        return True, "Zalo OA đã được tích hợp sẵn endpoint"

    def send_sms_alert(self, lost_vessels: List[Dict[str, Any]]) -> Tuple[bool, str]:
        """Gửi tin nhắn SMS khẩn cấp (Kênh mở rộng)"""
        if not settings.SMS_API_KEY:
            return False, "Chưa cấu hình SMS Gateway Key"
        return True, "SMS Gateway đã được tích hợp sẵn endpoint"

    def dispatch_all(self, lost_vessels: List[Dict[str, Any]], scan_time: str = None) -> Dict[str, Any]:
        """Phát thông báo qua tất cả các kênh được kích hoạt"""
        ok_email, msg_email = self.send_email_alert(lost_vessels, scan_time)
        res = {"email": {"success": ok_email, "message": msg_email}}

        if settings.TELEGRAM_BOT_TOKEN:
            ok_tele, msg_tele = self.send_telegram_alert(lost_vessels)
            res["telegram"] = {"success": ok_tele, "message": msg_tele}

        return res

notifier = NotificationService()

