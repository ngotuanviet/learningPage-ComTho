import re
from datetime import timedelta
from urllib.parse import parse_qs, urlsplit

from sqlalchemy import select, update

from app.models import Order, Product, utcnow
from tests.conftest import DRIVE, make_product, order, status


def test_product_info_hides_drive_link(client):
    make_product()
    r = client.get("/api/v1/products/goi-cong-thuc")
    assert r.status_code == 200
    assert r.json()["price"] == 2_000_000
    assert "drive" not in r.text


def test_inactive_or_unknown_product_404(client):
    make_product(active=False)
    assert client.get("/api/v1/products/goi-cong-thuc").status_code == 404
    assert client.get("/api/v1/products/khong-co").status_code == 404
    assert order(client).status_code == 404


def test_create_order(client):
    make_product()
    r = order(client, email="Khach@Example.com")
    assert r.status_code == 201
    o = r.json()
    assert re.fullmatch(r"CT[A-Z2-9]{8}", o["code"])
    assert o["status"] == "pending" and o["amount"] == 2_000_000
    assert o["drive_url"] is None and DRIVE not in r.text
    assert len(o["access_token"]) >= 40
    pay = o["payment"]
    assert pay["content"] == o["code"] and pay["amount"] == 2_000_000
    assert pay["account_number"] == "0123456789" and pay["account_name"] == "NGUYEN VAN A"
    qr = urlsplit(pay["qr_url"])
    assert qr.netloc == "vietqr.app"
    assert parse_qs(qr.query) == {
        "acc": ["0123456789"], "bank": ["MBBank"], "amount": ["2000000"], "des": [o["code"]], "template": ["compact"]
    }


def test_codes_are_unique(client, settings):
    settings.max_orders_per_ip_per_hour = 100
    settings.max_pending_orders_per_email = 100
    make_product()
    codes = {order(client).json()["code"] for _ in range(20)}
    assert len(codes) == 20


def test_client_cannot_set_price_or_status(client):
    make_product()
    for extra in ({"price": 1000}, {"amount": 1000}, {"status": "paid"}, {"drive_url": "x"}):
        assert order(client, **extra).status_code == 422


def test_input_validation(client):
    make_product()
    assert order(client, email="not-an-email").status_code == 422
    # Name is optional since checkout asks only for a phone number.
    r = client.post("/api/v1/orders", json={"product_slug": "goi-cong-thuc", "customer_name": "", "customer_email": "a@example.com"})
    assert r.status_code == 201
    r = client.post("/api/v1/orders", json={"product_slug": "goi-cong-thuc", "customer_name": "x" * 101, "customer_phone": "0912345678"})
    assert r.status_code == 422


def test_token_and_email_storage(client, db):
    make_product()
    o = order(client, email="Khach@Example.com").json()
    row = db.scalar(select(Order))
    assert row.access_token_hash != o["access_token"] and len(row.access_token_hash) == 64
    assert row.customer_email == "khach@example.com"


def test_price_change_does_not_affect_existing_order(client, db):
    make_product()
    o = order(client).json()
    db.execute(update(Product).values(price=1_000_000))
    db.commit()
    assert status(client, o["code"], o["access_token"]).json()["amount"] == 2_000_000


def test_status_requires_the_right_token(client):
    make_product()
    a = order(client, email="a@example.com").json()
    b = order(client, email="b@example.com").json()
    assert status(client, a["code"], a["access_token"]).status_code == 200
    for code, token in (
        (a["code"], None),
        (a["code"], "wrong-token"),
        (a["code"], b["access_token"]),  # someone else's token
        ("CTAAAAAAAA", a["access_token"]),  # unknown code
        ("ct-lower.x", a["access_token"]),  # malformed
    ):
        r = status(client, code, token)
        assert r.status_code == 404 and r.json()["detail"] == "Không tìm thấy đơn hàng."


def test_pending_has_payment_info_but_no_link(client):
    make_product()
    o = order(client).json()
    s = status(client, o["code"], o["access_token"]).json()
    assert s["status"] == "pending" and s["payment"]["content"] == o["code"] and s["drive_url"] is None


def test_paid_order_reveals_drive_link(client, db):
    make_product()
    o = order(client).json()
    db.execute(update(Order).values(status="paid", paid_at=utcnow()))
    db.commit()
    s = status(client, o["code"], o["access_token"]).json()
    assert s["status"] == "paid" and s["drive_url"] == DRIVE and s["payment"] is None


def test_needs_review_does_not_reveal_link(client, db):
    make_product()
    o = order(client).json()
    db.execute(update(Order).values(status="needs_review"))
    db.commit()
    assert status(client, o["code"], o["access_token"]).json()["drive_url"] is None


def test_order_expires(client, db):
    make_product()
    o = order(client).json()
    db.execute(update(Order).values(expires_at=utcnow() - timedelta(seconds=1)))
    db.commit()
    s = status(client, o["code"], o["access_token"]).json()
    assert s["status"] == "expired" and s["payment"] is None and s["drive_url"] is None


def test_limit_pending_orders_per_email(client, db):
    make_product()
    for _ in range(3):
        assert order(client).status_code == 201
    assert order(client).status_code == 429
    assert order(client, email="KHACH@example.com").status_code == 429  # same email, other case
    assert order(client, email="other@example.com").status_code == 201
    # expired orders no longer count
    db.execute(update(Order).values(expires_at=utcnow() - timedelta(seconds=1)))
    db.commit()
    assert order(client).status_code == 201


def test_limit_orders_per_ip(client, settings):
    settings.max_orders_per_ip_per_hour = 2
    make_product()
    assert order(client, email="a@example.com").status_code == 201
    assert order(client, email="b@example.com").status_code == 201
    assert order(client, email="c@example.com").status_code == 429


def test_cors_only_for_public_site(client):
    pre = {"Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"}
    ok = client.options("/api/v1/orders", headers={"Origin": "https://comtho.test", **pre})
    assert ok.headers.get("access-control-allow-origin") == "https://comtho.test"
    assert "access-control-allow-credentials" not in ok.headers
    bad = client.options("/api/v1/orders", headers={"Origin": "https://evil.example", **pre})
    assert "access-control-allow-origin" not in bad.headers


def test_no_store_and_security_headers(client):
    r = client.get("/api/v1/health")
    assert r.headers["cache-control"] == "no-store"
    assert r.headers["x-content-type-options"] == "nosniff"
