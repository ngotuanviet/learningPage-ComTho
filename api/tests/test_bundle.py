"""Buying several documents in one order (e.g. recipes + operations manual)."""

import pytest
from sqlalchemy import select

from app import email as email_mod
from app.models import Order, OrderItem
from tests.conftest import DRIVE, make_product, status

OPS_DRIVE = "https://drive.google.com/drive/folders/ops"
AUTH = {"Authorization": "Apikey test-sepay-key"}


@pytest.fixture
def two_products():
    make_product(slug="goi-cong-thuc", price=10_000_000)
    make_product(slug="quy-trinh-van-hanh", price=10_000_000, drive_url=OPS_DRIVE)


def bundle(client, slugs, email="khach@example.com", **extra):
    body = {"product_slugs": slugs, "customer_name": "Khách", "customer_email": email, **extra}
    return client.post("/api/v1/orders", json=body)


def test_product_list_has_no_drive_links(client, two_products):
    make_product(slug="ngung-ban", active=False)
    r = client.get("/api/v1/products")
    assert [p["slug"] for p in r.json()] == ["goi-cong-thuc", "quy-trinh-van-hanh"]
    assert "drive" not in r.text


def test_bundle_order_sums_prices_from_db(client, two_products, db):
    r = bundle(client, ["goi-cong-thuc", "quy-trinh-van-hanh"])
    assert r.status_code == 201
    o = r.json()
    assert o["amount"] == 20_000_000 and o["payment"]["amount"] == 20_000_000
    assert [(i["slug"], i["price"], i["drive_url"]) for i in o["items"]] == [
        ("goi-cong-thuc", 10_000_000, None),
        ("quy-trinh-van-hanh", 10_000_000, None),
    ]
    assert " + " in o["product_name"]
    assert len(db.scalars(select(OrderItem)).all()) == 2


def test_duplicate_slugs_count_once(client, two_products):
    assert bundle(client, ["goi-cong-thuc", "goi-cong-thuc"]).json()["amount"] == 10_000_000


@pytest.mark.parametrize(
    "body",
    [
        {"product_slugs": []},
        {"product_slugs": ["a", "b", "c", "d", "e", "f"]},
        {"product_slugs": ["goi-cong-thuc"], "product_slug": "goi-cong-thuc"},  # both fields
        {},  # neither
        {"product_slugs": ["goi-cong-thuc"], "price": 1},
    ],
)
def test_bad_bundle_requests(client, two_products, body):
    body = {"customer_name": "K", "customer_email": "k@example.com", **body}
    assert client.post("/api/v1/orders", json=body).status_code == 422


def test_unknown_or_inactive_item_rejects_whole_order(client, two_products):
    make_product(slug="ngung-ban", active=False)
    assert bundle(client, ["goi-cong-thuc", "khong-co"]).status_code == 404
    assert bundle(client, ["goi-cong-thuc", "ngung-ban"]).status_code == 404


def test_paid_bundle_reveals_every_link(client, two_products, monkeypatch):
    monkeypatch.setattr("app.routers.webhooks.send_drive_email", lambda o: True)
    o = bundle(client, ["goi-cong-thuc", "quy-trinh-van-hanh"]).json()
    tx = {"id": 1, "code": o["code"], "content": o["code"], "transferType": "in", "transferAmount": 20_000_000}
    assert client.post("/api/v1/webhooks/sepay", json=tx, headers=AUTH).status_code == 201
    s = status(client, o["code"], o["access_token"]).json()
    assert s["status"] == "paid"
    assert [i["drive_url"] for i in s["items"]] == [DRIVE, OPS_DRIVE]


def test_paying_only_one_item_needs_review(client, two_products, monkeypatch):
    monkeypatch.setattr("app.routers.webhooks.send_drive_email", lambda o: True)
    o = bundle(client, ["goi-cong-thuc", "quy-trinh-van-hanh"]).json()
    tx = {"id": 2, "code": o["code"], "content": o["code"], "transferType": "in", "transferAmount": 10_000_000}
    client.post("/api/v1/webhooks/sepay", json=tx, headers=AUTH)
    s = status(client, o["code"], o["access_token"]).json()
    assert s["status"] == "needs_review" and all(i["drive_url"] is None for i in s["items"])


def test_single_slug_field_still_works(client, two_products):
    r = client.post(
        "/api/v1/orders",
        json={"product_slug": "goi-cong-thuc", "customer_name": "K", "customer_email": "k@example.com"},
    )
    assert r.status_code == 201 and len(r.json()["items"]) == 1


def test_legacy_order_without_items(client, two_products, db):
    """Orders made before order_items existed still show their single document."""
    o = bundle(client, ["goi-cong-thuc"]).json()
    db.execute(OrderItem.__table__.delete())
    db.commit()
    s = status(client, o["code"], o["access_token"]).json()
    assert [i["slug"] for i in s["items"]] == ["goi-cong-thuc"]


def test_email_lists_every_document(client, two_products, db):
    bundle(client, ["goi-cong-thuc", "quy-trinh-van-hanh"])
    msg = email_mod.build_drive_email(db.scalar(select(Order)))
    assert DRIVE in msg["html"] and OPS_DRIVE in msg["html"]
    assert DRIVE in msg["text"] and OPS_DRIVE in msg["text"]
