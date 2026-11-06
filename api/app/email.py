"""Send the Google Drive link to the buyer (Resend API)."""

import html
import logging

import httpx

from app.config import get_settings
from app.models import Order
from app.orders import order_items

log = logging.getLogger("comtho.email")
RESEND_URL = "https://api.resend.com/emails"


def _vnd(n: int) -> str:
    return f"{n:,}".replace(",", ".") + " đ"


def build_drive_email(order: Order) -> dict:
    s = get_settings()
    name = html.escape(order.customer_name or "bạn")
    subject = f"Tài liệu của bạn – đơn {order.code}"
    docs = order_items(order)
    rows = "".join(
        f"""
  <div style="border:1px solid #e6dfd4;border-radius:10px;padding:14px 16px;margin:12px 0">
    <div style="font-weight:bold;margin-bottom:10px">{html.escape(pname)}</div>
    <a href="{html.escape(p.drive_url, quote=True)}" style="background:#9a3b1b;color:#fff;padding:10px 18px;border-radius:8px;text-decoration:none;font-weight:bold;display:inline-block">Mở tài liệu (Google Drive)</a>
    <div style="color:#666;font-size:12px;margin-top:8px;word-break:break-all">{html.escape(p.drive_url)}</div>
  </div>"""
        for p, pname, _ in docs
    )
    body_html = f"""<div style="font-family:Arial,sans-serif;font-size:15px;line-height:1.6;color:#222;max-width:560px">
  <p>Chào {name},</p>
  <p>Cơm Đốt Thố Hội An đã nhận được thanh toán <b>{_vnd(order.amount)}</b> cho đơn <b>{order.code}</b>.</p>
  {rows}
  <p style="color:#666;font-size:13px">Vui lòng giữ email này để mở lại tài liệu khi cần. Cần hỗ trợ, hãy trả lời email này.</p>
</div>"""
    links = "\n".join(f"- {pname}: {p.drive_url}" for p, pname, _ in docs)
    text = (
        f"Chào {order.customer_name or 'bạn'},\n\n"
        f"Đã nhận thanh toán cho đơn {order.code} ({_vnd(order.amount)}).\n"
        f"Tài liệu của bạn:\n{links}\n\n"
        "Vui lòng giữ email này để mở lại tài liệu khi cần.\n"
    )
    payload = {"from": s.email_from, "to": [order.customer_email], "subject": subject, "html": body_html, "text": text}
    if s.email_reply_to:
        payload["reply_to"] = s.email_reply_to
    return payload


def send_drive_email(order: Order) -> bool:
    """Returns True when the email was accepted by Resend. Never raises."""
    s = get_settings()
    if not order.customer_email:
        return False  # phone-only checkout: the link is shown on the checkout page
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
