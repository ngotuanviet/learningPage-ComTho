"""Order rules. Price and status always come from the database, never from the browser."""

from datetime import timedelta
from urllib.parse import urlencode

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Order, Product, utcnow
from app.schemas import OrderStatusOut, PaymentInfo
from app.security import new_order_code, new_token, sha256_hex


class OrderError(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        self.message = message


def qr_url(amount: int, content: str) -> str:
    s = get_settings()
    query = urlencode(
        {"acc": s.bank_account, "bank": s.bank_code, "amount": amount, "des": content, "template": "compact"}
    )
    # Image generator documented by SePay (docs.sepay.vn/tao-qr-code-vietqr-dong.html)
    return f"https://vietqr.app/img?{query}"


def payment_info(order: Order) -> PaymentInfo:
    s = get_settings()
    return PaymentInfo(
        bank_code=s.bank_code,
        account_number=s.bank_account,
        account_name=s.bank_account_name,
        amount=order.amount,
        content=order.code,
        qr_url=qr_url(order.amount, order.code),
    )


def expire_if_due(db: Session, order: Order) -> None:
    if order.status == "pending" and order.expires_at <= utcnow():
        order.status = "expired"
        db.commit()


def to_status(order: Order) -> OrderStatusOut:
    return OrderStatusOut(
        code=order.code,
        status=order.status,
        product_name=order.product_name,
        amount=order.amount,
        expires_at=order.expires_at,
        paid_at=order.paid_at,
        payment=payment_info(order) if order.status == "pending" else None,
        drive_url=order.product.drive_url if order.status == "paid" else None,
        email_sent=order.email_sent_at is not None,
    )


def create_order(db: Session, product_slug: str, name: str, email: str, ip_hash: str) -> tuple[Order, str]:
    s = get_settings()
    now = utcnow()
    email = email.lower()

    product = db.scalar(select(Product).where(Product.slug == product_slug, Product.is_active.is_(True)))
    if product is None:
        raise OrderError(404, "Sản phẩm không tồn tại hoặc đã ngừng bán.")

    pending = db.scalar(
        select(func.count()).where(
            Order.customer_email == email, Order.status == "pending", Order.expires_at > now
        )
    )
    if pending >= s.max_pending_orders_per_email:
        raise OrderError(429, "Email này đang có nhiều đơn chờ thanh toán. Vui lòng hoàn tất hoặc thử lại sau.")
    recent = db.scalar(
        select(func.count()).where(Order.ip_hash == ip_hash, Order.created_at > now - timedelta(hours=1))
    )
    if recent >= s.max_orders_per_ip_per_hour:
        raise OrderError(429, "Bạn đã tạo quá nhiều đơn. Vui lòng thử lại sau.")

    token = new_token()
    for _ in range(5):  # retry on the (very unlikely) code collision
        order = Order(
            code=new_order_code(),
            product_id=product.id,
            product_name=product.name,
            amount=product.price,
            customer_name=name,
            customer_email=email,
            access_token_hash=sha256_hex(token),
            status="pending",
            expires_at=now + timedelta(minutes=s.order_ttl_minutes),
            ip_hash=ip_hash,
            created_at=now,
        )
        db.add(order)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            continue
        db.refresh(order)
        return order, token
    raise OrderError(503, "Không tạo được đơn, vui lòng thử lại.")
