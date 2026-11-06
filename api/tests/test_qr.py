import httpx
import pytest

from app.models import Order
from tests.conftest import make_product

PNG = b"\x89PNG\r\n\x1a\n" + b"x" * 20


def new_order(client):
    make_product()
    r = client.post("/api/v1/orders", json={"product_slug": "goi-cong-thuc", "customer_phone": "0912345678"})
    assert r.status_code == 201
    return r.json()


@pytest.fixture
def fake_vietqr(monkeypatch):
    calls = []

    def fake_get(url, timeout):
        calls.append(url)
        return httpx.Response(200, content=PNG, request=httpx.Request("GET", url))

    monkeypatch.setattr("app.routers.public.httpx.get", fake_get)
    return calls


def test_qr_download_for_order_owner(client, fake_vietqr):
    o = new_order(client)
    r = client.get(f"/api/v1/orders/{o['code']}/qr", headers={"Authorization": f"Bearer {o['access_token']}"})
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert r.content == PNG
    assert f"QR-{o['code']}.png" in r.headers["content-disposition"]
    assert "no-store" in r.headers["cache-control"]
    # Same image the page shows: amount and order code filled in.
    assert fake_vietqr[0] == o["payment"]["qr_url"]


@pytest.mark.parametrize("auth", [None, "Bearer wrong-token"])
def test_qr_needs_the_order_token(client, fake_vietqr, auth):
    o = new_order(client)
    headers = {"Authorization": auth} if auth else {}
    r = client.get(f"/api/v1/orders/{o['code']}/qr", headers=headers)
    assert r.status_code == 404
    assert fake_vietqr == []


def test_qr_not_served_once_paid(client, db, fake_vietqr):
    o = new_order(client)
    order = db.query(Order).filter_by(code=o["code"]).one()
    order.status = "paid"
    db.commit()
    r = client.get(f"/api/v1/orders/{o['code']}/qr", headers={"Authorization": f"Bearer {o['access_token']}"})
    assert r.status_code == 409


def test_qr_upstream_error_is_502(client, monkeypatch):
    o = new_order(client)

    def broken(url, timeout):
        raise httpx.ConnectTimeout("timeout")

    monkeypatch.setattr("app.routers.public.httpx.get", broken)
    r = client.get(f"/api/v1/orders/{o['code']}/qr", headers={"Authorization": f"Bearer {o['access_token']}"})
    assert r.status_code == 502
