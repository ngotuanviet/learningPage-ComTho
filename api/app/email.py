"""Send the Google Drive link to the buyer (Resend API)."""

import html
import logging

import httpx

from app.config import get_settings
from app.models import Order

log = logging.getLogger("comtho.email")
RESEND_URL = "https://api.resend.com/emails"


def _vnd(n: int) -> str:
    return f"{n:,}".replace(",", ".") + " đ"


def build_drive_email(order: Order) -> dict:
    s = get_settings()
    name = html.escape(order.customer_name)
    product = html.escape(order.product_name)
    link = html.escape(order.product.drive_url, quote=True)
    subject = f"Tài liệu của bạn – đơn {order.code}"
    body_html = f"""\
<div style="font-family:Arial,sans-serif;font-size:15px;line-height:1.6;color:#222;max-width:560px">
  <p>Chào {name},</p>
  <p>Cơm Đốt Thố Hội An đã nhận được thanh toán cho đơn <b>{order.code}</b>.</p>
  <table style="border-collapse:collapse;margin:12px 0">
    <tr><td style="padding:4px 12px 4px 0;color:#666">Sản phẩm</td><td><b>{product}</b></td></tr>
    <tr><td style="padding:4px 12px 4px 0;color:#666">Số tiền</td><td>{_vnd(order.amount)}</td></tr>
  </table>
  <p style="margin:20px 0">
    <a href="{link}" style="background:#9a3b1b;color:#fff;padding:12px 20px;border-radius:8px;text-decoration:none;font-weight:bold">Mở tài liệu (Google Drive)</a>
  </p>
  <p style="color:#666;font-size:13px">Nếu nút không bấm được, mở link này: <br><a href="{link}">{link}</a></p>
  <p style="color:#666;font-size:13px">Vui lòng giữ email này để mở lại tài liệu khi cần. Cần hỗ trợ, hãy trả lời email này.</p>
</div>"""
    text = (
        f"Chào {order.customer_name},\n\n"
        f"Đã nhận thanh toán cho đơn {order.code} ({order.product_name}, {_vnd(order.amount)}).\n"
        f"Mở tài liệu: {order.product.drive_url}\n\n"
        "Vui lòng giữ email này để mở lại tài liệu khi cần.\n"
    )
    payload = {"from": s.email_from, "to": [order.customer_email], "subject": subject, "html": body_html, "text": text}
    if s.email_reply_to:
        payload["reply_to"] = s.email_reply_to
    return payload


def send_drive_email(order: Order) -> bool:
    """Returns True when the email was accepted by Resend. Never raises."""
    s = get_settings()
    if not s.resend_api_key:
        log.warning("RESEND_API_KEY not set, skipped email for order %s", order.code)
        return False
    try:
        r = httpx.post(
            RESEND_URL,
            json=build_drive_email(order),
            headers={
                "Authorization": f"Bearer {s.resend_api_key}",
                # Retries (webhook resend, CLI resend) will not send the same email twice within 24h.
                "Idempotency-Key": f"order-paid-{order.code}",
            },
            timeout=10,
        )
    except httpx.HTTPError as e:
        log.error("email for order %s failed: %s", order.code, type(e).__name__)
        return False
    if r.status_code >= 300:
        log.error("email for order %s rejected: HTTP %s", order.code, r.status_code)
        return False
    return True
