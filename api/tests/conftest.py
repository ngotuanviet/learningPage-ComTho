import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="comtho-test-"))
os.environ.update(
    ENV="test",
    DATABASE_URL=f"sqlite:///{(_TMP / 'test.db').as_posix()}",
    APP_SECRET="test-secret-" + "x" * 40,
    PUBLIC_ALLOWED_ORIGINS="https://comtho.test",
    BANK_CODE="MBBank",
    BANK_ACCOUNT="0123456789",
    BANK_ACCOUNT_NAME="NGUYEN VAN A",
    ORDER_CODE_PREFIX="CT",
    SEPAY_WEBHOOK_API_KEY="test-sepay-key",
    RESEND_API_KEY="",
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.db import get_engine, get_sessionmaker  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base, Product  # noqa: E402

DRIVE = "https://drive.google.com/drive/folders/abc123"


@pytest.fixture(autouse=True)
def _fresh_db():
    engine = get_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture
def db():
    with get_sessionmaker()() as session:
        yield session


@pytest.fixture
def settings():
    s = get_settings()
    snapshot = s.model_dump()
    yield s
    for key, value in snapshot.items():
        setattr(s, key, value)


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def make_product(slug="goi-cong-thuc", price=2_000_000, active=True, drive_url=DRIVE) -> Product:
    with get_sessionmaker()() as session:
        p = Product(slug=slug, name="Gói công thức Cơm Thố", price=price, drive_url=drive_url, is_active=active)
        session.add(p)
        session.commit()
        return p


def order(client, email="khach@example.com", slug="goi-cong-thuc", **extra):
    body = {"product_slug": slug, "customer_name": "Khách A", "customer_email": email, **extra}
    return client.post("/api/v1/orders", json=body)


def status(client, code, token):
    headers = {"Authorization": f"Bearer {token}"} if token is not None else {}
    return client.get(f"/api/v1/orders/{code}/status", headers=headers)
