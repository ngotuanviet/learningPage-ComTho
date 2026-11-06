from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Text,
    TypeDecorator,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator):
    """Always store/return timezone-aware UTC datetimes (SQLite drops tzinfo)."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("naive datetime not allowed")
        return value.astimezone(timezone.utc)

    def process_result_value(self, value, dialect):
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


NAMING = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING)


ORDER_STATUSES = ("pending", "paid", "expired", "cancelled", "needs_review")


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (CheckConstraint("price > 0", name="price_positive"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(200), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    price: Mapped[int] = mapped_column(BigInteger)  # VND, integer: what the buyer pays
    # Original price shown struck through next to `price` (display only, never charged).
    list_price: Mapped[int | None] = mapped_column(BigInteger)
    # Public Google Drive link. Only revealed to buyers of a paid order.
    drive_url: Mapped[str] = mapped_column(String(1000))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
        CheckConstraint(
            "status IN ('pending', 'paid', 'expired', 'cancelled', 'needs_review')", name="status"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), index=True)
    # Snapshot at order time, so later price/name changes do not affect this order.
    product_name: Mapped[str] = mapped_column(String(200))
    amount: Mapped[int] = mapped_column(BigInteger)
    # Checkout asks only for a phone number; name/email are optional (older orders have them).
    customer_name: Mapped[str | None] = mapped_column(String(100))
    customer_email: Mapped[str | None] = mapped_column(String(320), index=True)
    customer_phone: Mapped[str | None] = mapped_column(String(15), index=True)  # 0xxxxxxxxx
    # sha256 of the access token given to the buyer once; raw token is never stored.
    access_token_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime())
    paid_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    email_sent_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    ip_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)

    # First item of the order (kept for older code paths); the full list is `items`.
    product: Mapped[Product] = relationship(lazy="joined")
    items: Mapped[list["OrderItem"]] = relationship(
        lazy="selectin", order_by="OrderItem.id", cascade="all, delete-orphan"
    )


class OrderItem(Base):
    """One document in an order. Name and price are snapshots taken when the order was made."""

    __tablename__ = "order_items"
    __table_args__ = (
        CheckConstraint("price > 0", name="price_positive"),
        UniqueConstraint("order_id", "product_id", name="uq_order_items_order_product"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), index=True)
    product_name: Mapped[str] = mapped_column(String(200))
    price: Mapped[int] = mapped_column(BigInteger)

    product: Mapped[Product] = relationship(lazy="joined")


class PaymentTransaction(Base):
    """One row per bank transaction reported by SePay (filled in Phase 2)."""

    __tablename__ = "payment_transactions"
    __table_args__ = (
        UniqueConstraint("provider", "provider_transaction_id", name="uq_payment_transactions_provider_tx"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(20), default="sepay")
    provider_transaction_id: Mapped[str] = mapped_column(String(100))
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id", ondelete="SET NULL"), index=True)
    amount: Mapped[int] = mapped_column(BigInteger)
    content: Mapped[str] = mapped_column(Text, default="")
    reference_code: Mapped[str | None] = mapped_column(String(100))
    transaction_date: Mapped[datetime | None] = mapped_column(UTCDateTime())
    # matched | needs_review
    status: Mapped[str] = mapped_column(String(20))
    note: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class WebhookEvent(Base):
    """Raw webhook payloads, stored before processing (Phase 2)."""

    __tablename__ = "webhook_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(20))
    provider_event_id: Mapped[str | None] = mapped_column(String(100), index=True)
    payload: Mapped[str] = mapped_column(Text)
    result: Mapped[str | None] = mapped_column(String(50))
    received_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    processed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
