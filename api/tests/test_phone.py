"""Checkout with only a phone number."""

import pytest
from sqlalchemy import select

from app import email as email_mod
from app.models import Order
from tests.conftest import make_product


def buy(client, phone, **extra):
    return client.post("/api/v1/orders", json={"product_slug": "goi-cong-thuc", "customer_phone": phone, **extra})


@pytest.mark.parametrize(
    "raw,stored",
    [("0912345678", "0912345678"), ("0912 345 678", "0912345678"), ("091.234.5678", "0912345678"),
     ("+84 912 345 678", "0912345678"), ("84912345678", "0912345678"), ("0389-123-456", "0389123456")],
)
def test_phone_only_order_normalises_number(client, db, raw, stored):
    make_product()
    r = buy(client, raw)
    assert r.status_code == 201, r.text
    row = db.scalar(select(Order))
    assert row.customer_phone == stored and row.customer_email is None and row.customer_name is None


@pytest.mark.parametrize("bad", ["", "123", "0123456789", "09123456789", "abcdefghij", "0912 345 67x"])
def test_invalid_phone_rejected(client, bad):
    make_product()
    assert buy(client, bad).status_code == 422


def test_phone_or_email_required(client):
    make_product()
    assert client.post("/api/v1/orders", json={"product_slug": "goi-cong-thuc"}).status_code == 422
    assert client.post("/api/v1/orders", json={"product_slug": "goi-cong-thuc", "customer_name": "K"}).status_code == 422


def test_old_pages_with_name_and_email_still_work(client):
    make_product()
    r = client.post(
        "/api/v1/orders",
        json={"product_slug": "goi-cong-thuc", "customer_name": "K", "customer_email": "k@example.com"},
    )
    assert r.status_code == 201


def test_pending_limit_per_phone(client):
    make_product()
    for _ in range(3):
        assert buy(client, "0912345678").status_code == 201
    assert buy(client, "+84912345678").status_code == 429  # same number, other format
    assert buy(client, "0987654321").status_code == 201


def test_no_email_attempt_for_phone_only_orders(client, db, settings, monkeypatch):
    make_product()
    buy(client, "0912345678")
    settings.resend_api_key = "re_test"
    monkeypatch.setattr(email_mod.httpx, "post", lambda *a, **k: pytest.fail("should not call Resend"))
    assert email_mod.send_drive_email(db.scalar(select(Order))) is False
