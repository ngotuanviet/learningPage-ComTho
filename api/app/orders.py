"""Order rules. Price and status always come from the database, never from the browser."""

from datetime import timedelta
from urllib.parse import urlencode

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Order, OrderItem, Product, utcnow
from app.schemas import OrderItemOut, OrderStatusOut, PaymentInfo
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


MAX_ITEMS = 5


def order_items(order: Order) -> list[tuple[Product, str, int]]:
    """(product, name snapshot, price snapshot) for each document in the order."""
    if order.items:
        return [(i.product, i.product_name, i.price) for i in order.items]
    # Orders created before order_items existed hold a single product.
    return [(order.product, order.product_name, order.amount)]


def to_status(order: Order) -> OrderStatusOut:
    paid = order.status == "paid"
    items = [
        OrderItemOut(slug=p.slug, name=name, price=price, drive_url=p.drive_url if paid else None)
        for p, name, price in order_items(order)
    ]
    return OrderStatusOut(
        code=order.code,
        status=order.status,
        product_name=order.product_name,
        amount=order.amount,
        expires_at=order.expires_at,
        paid_at=order.paid_at,
        payment=payment_info(order) if order.status == "pending" else None,
        items=items,
        # Kept for older checkout pages: link of the first document.
        drive_url=items[0].drive_url if items else None,
        email_sent=order.email_sent_at is not None,
    )


def create_order(
    db: Session, slugs: list[str], name: str | None, email: str | None, phone: str | None, ip_hash: str
) -> tuple[Order, str]:
    s = get_settings()
    now = utcnow()
    email = email.lower() if email else None

    slugs = list(dict.fromkeys(slugs))  # unique, keep the order the buyer chose
    if not 1 <= len(slugs) <= MAX_ITEMS:
        raise OrderError(422, "Danh sách sản phẩm không hợp lệ.")
    found = {
        p.slug: p
        for p in db.scalars(select(Product).where(Product.slug.in_(slugs), Product.is_active.is_(True)))
    }
    if len(found) != len(slugs):
        raise OrderError(404, "Sản phẩm không tồn tại hoặc đã ngừng bán.")
    products = [found[slug] for slug in slugs]

    who = Order.customer_phone == phone if phone else Order.customer_email == email
    pending = db.scalar(
        select(func.count()).where(who, Order.status == "pending", Order.expires_at > now)
    )
    if pending >= s.max_pending_orders_per_email:
        raise OrderError(429, "Số điện thoại này đang có nhiều đơn chờ thanh toán. Vui lòng hoàn tất hoặc thử lại sau.")
    recent = db.scalar(
        select(func.count()).where(Order.ip_hash == ip_hash, Order.created_at > now - timedelta(hours=1))
    )
    if recent >= s.max_orders_per_ip_per_hour:
        raise OrderError(429, "Bạn đã tạo quá nhiều đơn. Vui lòng thử lại sau.")

    token = new_token()
    for _ in range(5):  # retry on the (very unlikely) code collision
        order = Order(
            code=new_order_code(),
            product_id=products[0].id,
            product_name=" + ".join(p.name for p in products)[:200],
            amount=sum(p.price for p in products),  # always from the database
            customer_name=(name or None),
            customer_email=email,
            customer_phone=phone,
            access_token_hash=sha256_hex(token),
            status="pending",
            expires_at=now + timedelta(minutes=s.order_ttl_minutes),
            ip_hash=ip_hash,
            created_at=now,
            items=[OrderItem(product_id=p.id, product_name=p.name, price=p.price) for p in products],
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
