import pytest
from sqlalchemy import select

from app import cli
from app.models import Product

DRIVE = "https://drive.google.com/drive/folders/xyz"


def run(*args):
    cli.main(list(args))


def test_product_lifecycle(db, capsys):
    run("add-product", "--slug", "goi-a", "--name", "Gói A", "--price", "2000000", "--drive-url", DRIVE)
    run("set-price", "--slug", "goi-a", "--price", "1500000")
    run("set-drive-url", "--slug", "goi-a", "--url", "https://docs.google.com/document/d/1")
    run("deactivate", "--slug", "goi-a")
    p = db.scalar(select(Product))
    assert (p.price, p.drive_url, p.is_active) == (1_500_000, "https://docs.google.com/document/d/1", False)
    run("list-products")
    assert "goi-a" in capsys.readouterr().out


@pytest.mark.parametrize(
    "args",
    [
        ["add-product", "--slug", "Có Dấu", "--name", "x", "--price", "2000000", "--drive-url", DRIVE],
        ["add-product", "--slug", "goi-b", "--name", "x", "--price", "0", "--drive-url", DRIVE],
        ["add-product", "--slug", "goi-b", "--name", "x", "--price", "2000000", "--drive-url", "https://evil.example/x"],
        ["set-price", "--slug", "khong-co", "--price", "2000000"],
    ],
)
def test_rejects_bad_input(args):
    with pytest.raises(SystemExit):
        run(*args)


def test_duplicate_slug(db):
    run("add-product", "--slug", "goi-a", "--name", "Gói A", "--price", "2000000", "--drive-url", DRIVE)
    with pytest.raises(SystemExit):
        run("add-product", "--slug", "goi-a", "--name", "Gói A", "--price", "2000000", "--drive-url", DRIVE)


def test_reconciliation_commands(client, db, monkeypatch, capsys):
    from tests.conftest import make_product, order

    sent = []
    monkeypatch.setattr(cli, "send_drive_email", lambda o: sent.append(o.code) or True)
    make_product()
    code = order(client).json()["code"]
    with pytest.raises(SystemExit):
        run("resend-email", "--code", code)  # not paid yet -> no link
    run("mark-paid", "--code", code.lower())
    run("resend-email", "--code", code)
    assert sent == [code, code]
    db.expire_all()
    row = db.scalar(select(cli.Order))
    assert row.status == "paid" and row.email_sent_at is not None
    run("list-review")
    assert "Giao dịch cần kiểm tra: 0" in capsys.readouterr().out
