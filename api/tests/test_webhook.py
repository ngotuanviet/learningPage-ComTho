from datetime import timedelta

import pytest
from sqlalchemy import func, select, update

from app import email as email_mod
from app.models import Order, PaymentTransaction, WebhookEvent, utcnow
from tests.conftest import DRIVE, make_product, order, status

URL = "/api/v1/webhooks/sepay"
AUTH = {"Authorization": "Apikey test-sepay-key"}


@pytest.fixture
def sent(monkeypatch):
    """Capture emails instead of calling Resend."""
    calls = []

    def fake_send(o):
        calls.append(o.code)
        return True

    monkeypatch.setattr("app.routers.webhooks.send_drive_email", fake_send)
    return calls


@pytest.fixture
def new_order(client):
    make_product()
    return order(client).json()


def tx(code, amount=2_000_000, tx_id=92704, **over):
    body = {
        "id": tx_id,
        "gateway": "MBBank",
        "transactionDate": "2026-11-05 15:40:00",
        "accountNumber": "0123456789",
        "subAccount": "",
        "code": code,
        "content": f"{code} chuyen tien",
        "transferType": "in",
        "description": "BankAPINotify",
        "transferAmount": amount,
        "accumulated": 10_000_000,
        "referenceCode": "FT26309000001",
    }
    body.update(over)
    return body


def hook(client, body, headers=AUTH):
    return client.post(URL, json=body, headers=headers)


def get_status(client, o):
    return status(client, o["code"], o["access_token"]).json()


def test_correct_payment_marks_paid_and_sends_email(client, new_order, sent, db):
    r = hook(client, tx(new_order["code"]))
    assert r.status_code == 201 and r.json() == {"success": True}
    s = get_status(client, new_order)
    assert s["status"] == "paid" and s["drive_url"] == DRIVE and s["email_sent"] is True
    assert sent == [new_order["code"]]
    t = db.scalar(select(PaymentTransaction))
    assert t.status == "matched" and t.amount == 2_000_000 and t.reference_code == "FT26309000001"
    assert t.transaction_date.utcoffset() == timedelta(0) and t.transaction_date.hour == 8  # 15:40 VN = 08:40 UTC
    assert db.scalar(select(WebhookEvent.result)) == "matched"


@pytest.mark.parametrize(
    "headers", [{}, {"Authorization": "Apikey wrong"}, {"Authorization": "test-sepay-key"}, {"Authorization": "Bearer test-sepay-key"}]
)
def test_rejects_bad_api_key(client, new_order, sent, headers):
    assert hook(client, tx(new_order["code"]), headers=headers).status_code == 401
    assert get_status(client, new_order)["status"] == "pending" and sent == []


def test_not_configured(client, new_order, settings):
    settings.sepay_webhook_api_key = None
    assert hook(client, tx(new_order["code"])).status_code == 503


def test_duplicate_delivery_processed_once(client, new_order, sent, db):
    for _ in range(3):
        assert hook(client, tx(new_order["code"])).json() == {"success": True}
    assert db.scalar(select(func.count()).select_from(PaymentTransaction)) == 1
    assert db.scalar(select(func.count()).select_from(WebhookEvent)) == 3  # every delivery is logged
    assert sent == [new_order["code"]]


@pytest.mark.parametrize("amount", [1_999_000, 2_000_001, 200_000])
def test_wrong_amount_needs_review(client, new_order, sent, db, amount):
    assert hook(client, tx(new_order["code"], amount=amount)).status_code == 201
    s = get_status(client, new_order)
    assert s["status"] == "needs_review" and s["drive_url"] is None and sent == []
    assert db.scalar(select(PaymentTransaction.status)) == "needs_review"


def test_unknown_code_recorded_for_review(client, new_order, sent, db):
    hook(client, tx("CTZZZZZZZZ"))
    t = db.scalar(select(PaymentTransaction))
    assert t.status == "needs_review" and t.order_id is None and sent == []
    assert get_status(client, new_order)["status"] == "pending"


def test_code_found_in_note_when_code_field_empty(client, new_order, sent):
    body = tx(None, content=f"MBVCB.123.{new_order['code'].lower()}.KHACH A CHUYEN KHOAN")
    hook(client, body)
    assert get_status(client, new_order)["status"] == "paid"


def test_code_glued_to_other_text(client, new_order, sent):
    # bank stuck letters in front of the code; the real code is still found
    hook(client, tx(None, content=f"ACT{new_order['code']}XYZ"))
    assert get_status(client, new_order)["status"] == "paid"


def test_outgoing_transfer_ignored(client, new_order, sent, db):
    hook(client, tx(new_order["code"], transferType="out"))
    assert get_status(client, new_order)["status"] == "pending"
    assert db.scalar(select(func.count()).select_from(PaymentTransaction)) == 0


def test_late_exact_payment_is_accepted(client, new_order, sent, db):
    db.execute(update(Order).values(expires_at=utcnow() - timedelta(minutes=5)))
    db.commit()
    assert get_status(client, new_order)["status"] == "expired"
    hook(client, tx(new_order["code"]))
    assert get_status(client, new_order)["status"] == "paid"
    assert db.scalar(select(WebhookEvent.result)) == "late_matched"


def test_second_payment_for_paid_order_needs_review(client, new_order, sent, db):
    hook(client, tx(new_order["code"], tx_id=1))
    hook(client, tx(new_order["code"], tx_id=2))
    rows = db.scalars(select(PaymentTransaction).order_by(PaymentTransaction.id)).all()
    assert [r.status for r in rows] == ["matched", "needs_review"]
    assert get_status(client, new_order)["status"] == "paid" and sent == [new_order["code"]]


def test_amount_as_string_and_bad_payloads(client, new_order, sent):
    assert hook(client, tx(new_order["code"], amount="2000000")).status_code == 201
    assert get_status(client, new_order)["status"] == "paid"
    assert hook(client, {"transferType": "in"}).status_code == 400
    assert client.post(URL, content=b"not json", headers=AUTH).status_code == 400
    assert hook(client, [1, 2]).status_code == 400


def test_email_failure_does_not_break_webhook(client, new_order, monkeypatch):
    monkeypatch.setattr("app.routers.webhooks.send_drive_email", lambda o: False)
    assert hook(client, tx(new_order["code"])).json() == {"success": True}
    s = get_status(client, new_order)
    assert s["status"] == "paid" and s["drive_url"] == DRIVE and s["email_sent"] is False


# ---- email ----

def test_email_content_is_escaped(client, db):
    make_product()
    client.post(
        "/api/v1/orders",
        json={"product_slug": "goi-cong-thuc", "customer_name": "<b>Khách</b>", "customer_email": "k@example.com"},
    )
    row = db.scalar(select(Order))
    msg = email_mod.build_drive_email(row)
    assert msg["to"] == ["k@example.com"] and row.code in msg["subject"]
    assert DRIVE in msg["html"] and DRIVE in msg["text"]
    assert "<b>Khách</b>" not in msg["html"] and "&lt;b&gt;" in msg["html"]


def test_send_drive_email_calls_resend(client, db, settings, monkeypatch):
    make_product()
    order(client)
    row = db.scalar(select(Order))
    settings.resend_api_key = "re_test"
    seen = {}

    class Resp:
        status_code = 200

    def fake_post(url, json, headers, timeout):
        seen.update(url=url, headers=headers, to=json["to"])
        return Resp()

    monkeypatch.setattr(email_mod.httpx, "post", fake_post)
    assert email_mod.send_drive_email(row) is True
    assert seen["url"] == "https://api.resend.com/emails"
    assert seen["headers"]["Authorization"] == "Bearer re_test"
    assert seen["headers"]["Idempotency-Key"] == f"order-paid-{row.code}"

    Resp.status_code = 422
    assert email_mod.send_drive_email(row) is False


def test_send_skipped_without_key(client, db, settings):
    make_product()
    order(client)
    settings.resend_api_key = None
    assert email_mod.send_drive_email(db.scalar(select(Order))) is False


def test_order_lock_is_valid_postgres_sql():
    """SQLite ignores FOR UPDATE, so check the Postgres SQL directly (regression: 500 in production)."""
    from sqlalchemy.dialects import postgresql

    from app.payments import lock_orders_query

    sql = str(lock_orders_query(["CTAAAAAAAA"]).compile(dialect=postgresql.dialect()))
    assert "LEFT OUTER JOIN products" in sql  # product is eager-loaded...
    assert sql.rstrip().endswith("FOR UPDATE OF orders")  # ...so only orders may be locked
