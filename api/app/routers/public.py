import re

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Order, Product
from app.orders import OrderError, create_order, expire_if_due, to_status
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
            db, body.product_slug, body.customer_name, body.customer_email, keyed_hash("ip:" + client_ip(request))
        )
    except OrderError as e:
        raise HTTPException(e.status_code, e.message) from None
    return OrderCreatedOut(**to_status(order).model_dump(), access_token=token)


@router.get("/orders/{code}/status", response_model=OrderStatusOut)
def order_status(code: str, authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    # Unknown code and wrong token give the same 404, so codes cannot be probed.
    token = (authorization or "").removeprefix("Bearer ").strip()
    if not token or not _CODE_RE.match(code):
        raise HTTPException(status.HTTP_404_NOT_FOUND, _NOT_FOUND)
    order = db.scalar(select(Order).where(Order.code == code))
    if order is None or not same_hash(token, order.access_token_hash):
        raise HTTPException(status.HTTP_404_NOT_FOUND, _NOT_FOUND)
    expire_if_due(db, order)
    return to_status(order)
