"""Manage products and view orders from the terminal (there is no admin website).

    python -m app.cli add-product --slug goi-cong-thuc --name "Gói công thức" --price 2000000 --drive-url https://drive.google.com/...
    python -m app.cli set-price --slug goi-cong-thuc --price 1500000
    python -m app.cli set-drive-url --slug goi-cong-thuc --url https://drive.google.com/...
    python -m app.cli deactivate --slug goi-cong-thuc      (stop selling)
    python -m app.cli activate --slug goi-cong-thuc
    python -m app.cli list-products
    python -m app.cli list-orders [--status paid] [--limit 20]
    python -m app.cli list-review                          (giao dịch/đơn cần đối soát)
    python -m app.cli mark-paid --code CTXXXXXXXX          (đã kiểm tra tiền về tài khoản -> gửi link)
    python -m app.cli resend-email --code CTXXXXXXXX

Set DATABASE_URL to the production database to manage the live shop.
"""

import argparse
import re
import sys

from sqlalchemy import select

from app.db import get_sessionmaker
from app.email import send_drive_email
from app.models import ORDER_STATUSES, Order, PaymentTransaction, Product, utcnow

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
DRIVE_HOSTS = ("https://drive.google.com/", "https://docs.google.com/")


def _slug(value: str) -> str:
    if not SLUG_RE.match(value):
        raise argparse.ArgumentTypeError("slug: chữ thường không dấu, số, dấu gạch ngang (vd goi-cong-thuc)")
    return value


def _price(value: str) -> int:
    price = int(value)
    if not 1_000 <= price <= 1_000_000_000:
        raise argparse.ArgumentTypeError("giá phải từ 1.000 đến 1.000.000.000 VND")
    return price


def _drive_url(value: str) -> str:
    if not value.startswith(DRIVE_HOSTS):
        raise argparse.ArgumentTypeError("link phải là Google Drive/Docs (https://drive.google.com/...)")
    return value


def _vnd(n: int) -> str:
    return f"{n:,}".replace(",", ".") + " đ"


def _get(db, slug: str) -> Product:
    product = db.scalar(select(Product).where(Product.slug == slug))
    if product is None:
        sys.exit(f"Không có sản phẩm '{slug}'.")
    return product


def main(argv: list[str] | None = None) -> None:
    # Windows consoles default to cp1252, which cannot print Vietnamese.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    add = sub.add_parser("add-product")
    add.add_argument("--slug", type=_slug, required=True)
    add.add_argument("--name", required=True)
    add.add_argument("--price", type=_price, required=True)
    add.add_argument("--drive-url", type=_drive_url, required=True)
    add.add_argument("--description", default="")
    add.add_argument("--inactive", action="store_true", help="tạo nhưng chưa bán")

    sp = sub.add_parser("set-price")
    sp.add_argument("--slug", type=_slug, required=True)
    sp.add_argument("--price", type=_price, required=True)

    su = sub.add_parser("set-drive-url")
    su.add_argument("--slug", type=_slug, required=True)
    su.add_argument("--url", type=_drive_url, required=True)

    for name in ("activate", "deactivate"):
        sub.add_parser(name).add_argument("--slug", type=_slug, required=True)

    sub.add_parser("list-products")
    lo = sub.add_parser("list-orders")
    lo.add_argument("--status", choices=ORDER_STATUSES)
    lo.add_argument("--limit", type=int, default=20)
    sub.add_parser("list-review")
    for name in ("mark-paid", "resend-email"):
        sub.add_parser(name).add_argument("--code", required=True)

    args = parser.parse_args(argv)

    with get_sessionmaker()() as db:
        if args.command == "add-product":
            if db.scalar(select(Product.id).where(Product.slug == args.slug)):
                sys.exit(f"Slug '{args.slug}' đã tồn tại.")
            db.add(
                Product(
                    slug=args.slug,
                    name=args.name,
                    price=args.price,
                    drive_url=args.drive_url,
                    description=args.description,
                    is_active=not args.inactive,
                )
            )
            db.commit()
            print(f"Đã thêm '{args.slug}' giá {_vnd(args.price)}.")
        elif args.command == "set-price":
            product = _get(db, args.slug)
            old = product.price
            product.price = args.price
            db.commit()
            print(f"Đã đổi giá '{args.slug}': {_vnd(old)} -> {_vnd(args.price)} (đơn cũ giữ giá cũ).")
        elif args.command == "set-drive-url":
            _get(db, args.slug).drive_url = args.url
            db.commit()
            print("Đã đổi link Drive (áp dụng cho cả đơn đã thanh toán trước đó).")
        elif args.command in ("activate", "deactivate"):
            _get(db, args.slug).is_active = args.command == "activate"
            db.commit()
            print("Đã bật bán." if args.command == "activate" else "Đã ngừng bán.")
        elif args.command == "list-products":
            for p in db.scalars(select(Product).order_by(Product.id)):
                state = "đang bán" if p.is_active else "ngừng bán"
                print(f"{p.slug:30} {_vnd(p.price):>15}  {state:10} {p.name}")
        elif args.command == "list-orders":
            query = select(Order).order_by(Order.id.desc()).limit(args.limit)
            if args.status:
                query = query.where(Order.status == args.status)
            for o in db.scalars(query):
                when = o.created_at.astimezone().strftime("%d/%m %H:%M")
                print(f"{o.code:14} {o.status:12} {_vnd(o.amount):>15}  {when}  {o.customer_email}  {o.product_name}")

        elif args.command == "list-review":
            txs = db.scalars(
                select(PaymentTransaction).where(PaymentTransaction.status == "needs_review").order_by(PaymentTransaction.id)
            ).all()
            print(f"Giao dịch cần kiểm tra: {len(txs)}")
            for t in txs:
                code = db.get(Order, t.order_id).code if t.order_id else "-"
                print(f"  SePay#{t.provider_transaction_id:10} {_vnd(t.amount):>15}  đơn {code:12} {t.note or ''}  | {t.content[:60]}")
            orders = db.scalars(select(Order).where(Order.status == "needs_review")).all()
            print(f"Đơn cần kiểm tra: {len(orders)}")
            for o in orders:
                print(f"  {o.code:14} {_vnd(o.amount):>15}  {o.customer_email}")
        elif args.command in ("mark-paid", "resend-email"):
            order = db.scalar(select(Order).where(Order.code == args.code.upper()))
            if order is None:
                sys.exit("Không tìm thấy đơn.")
            if args.command == "mark-paid":
                if order.status == "paid":
                    sys.exit("Đơn đã ở trạng thái paid.")
                order.status, order.paid_at = "paid", utcnow()
                db.commit()
                print(f"Đã đánh dấu {order.code} là paid.")
            elif order.status != "paid":
                sys.exit(f"Đơn đang '{order.status}', chưa thanh toán nên không gửi link.")
            if send_drive_email(order):
                order.email_sent_at = utcnow()
                db.commit()
                print(f"Đã gửi email link Drive tới {order.customer_email}.")
            else:
                print("Chưa gửi được email (kiểm tra RESEND_API_KEY / log).")


if __name__ == "__main__":
    main()
