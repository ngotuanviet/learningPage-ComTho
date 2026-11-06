import re

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Order, Product
from app.orders import OrderError, create_order, expire_if_due, qr_url, to_status
from app.schemas import OrderCreatedOut, OrderCreateIn, OrderStatusOut, ProductOut
from app.security import keyed_hash, same_hash

router = APIRouter(tags=["public"])

_CODE_RE = re.compile(r"^[A-Z0-9]{4,32}$")
_NOT_FOUND = "Không tìm thấy đơn hàng."


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.get("/products", response_model=list[ProductOut])
def list_products(db: Session = Depends(get_db)):
    """Active products, for the "buy together" checkboxes. Never includes Drive links."""
    return db.scalars(select(Product).where(Product.is_active.is_(True)).order_by(Product.id)).all()


@router.get("/products/{slug}", response_model=ProductOut)
def get_product(slug: str, db: Session = Depends(get_db)):
    product = db.scalar(select(Product).where(Product.slug == slug, Product.is_active.is_(True)))
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sản phẩm không tồn tại hoặc đã ngừng bán.")
    return product


@router.post("/orders", response_model=OrderCreatedOut, status_code=status.HTTP_201_CREATED)
def post_order(body: OrderCreateIn, request: Request, db: Session = Depends(get_db)):
    try:
        order, token = create_order(
            db, body.slugs, body.customer_name, body.customer_email, body.customer_phone,
            keyed_hash("ip:" + client_ip(request)),
        )
    except OrderError as e:
        raise HTTPException(e.status_code, e.message) from None
    return OrderCreatedOut(**to_status(order).model_dump(), access_token=token)


def _authorized_order(code: str, authorization: str | None, db: Session) -> Order:
    # Unknown code and wrong token give the same 404, so codes cannot be probed.
    token = (authorization or "").removeprefix("Bearer ").strip()
    if not token or not _CODE_RE.match(code):
        raise HTTPException(status.HTTP_404_NOT_FOUND, _NOT_FOUND)
    order = db.scalar(select(Order).where(Order.code == code))
    if order is None or not same_hash(token, order.access_token_hash):
        raise HTTPException(status.HTTP_404_NOT_FOUND, _NOT_FOUND)
    expire_if_due(db, order)
    return order


@router.get("/orders/{code}/status", response_model=OrderStatusOut)
def order_status(code: str, authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    return to_status(_authorized_order(code, authorization, db))


@router.get("/orders/{code}/qr", response_class=Response)
def order_qr(code: str, authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    """QR image as a downloadable PNG, so phone buyers can save it and scan it in their bank app.

    The browser cannot download it from vietqr.app directly (no CORS), so the API fetches it.
    """
    order = _authorized_order(code, authorization, db)
    if order.status != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, "Đơn không còn chờ thanh toán.")
    try:
        r = httpx.get(qr_url(order.amount, order.code), timeout=8)
        r.raise_for_status()
    except httpx.HTTPError:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Chưa tải được ảnh QR, vui lòng thử lại.") from None
    if not r.content.startswith(b"\x89PNG"):
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Chưa tải được ảnh QR, vui lòng thử lại.")
    return Response(
        content=r.content,
        media_type="image/png",
        headers={
            "Cache-Control": "private, no-store",
            "Content-Disposition": f'attachment; filename="QR-{order.code}.png"',
        },
    )
