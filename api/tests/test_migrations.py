"""The Alembic migration must build exactly the schema described by the models."""

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext

from app.db import get_engine
from app.models import Base


def test_migration_matches_models():
    engine = get_engine()
    Base.metadata.drop_all(engine)
    with engine.begin() as conn:
        conn.exec_driver_sql("DROP TABLE IF EXISTS alembic_version")
    command.upgrade(Config("alembic.ini"), "head")
    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn, opts={"compare_type": True})
        diff = compare_metadata(ctx, Base.metadata)
    assert diff == []
    command.downgrade(Config("alembic.ini"), "base")


def test_migration_backfills_order_items():
    engine = get_engine()
    Base.metadata.drop_all(engine)
    with engine.begin() as conn:
        conn.exec_driver_sql("DROP TABLE IF EXISTS alembic_version")
    cfg = Config("alembic.ini")
    command.upgrade(cfg, "0001")
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "INSERT INTO products (id, name, slug, description, price, drive_url, is_active, created_at, updated_at) "
            "VALUES (1, 'P', 'p', '', 10000, 'https://drive.google.com/x', 1, '2026-01-01', '2026-01-01')"
        )
        conn.exec_driver_sql(
            "INSERT INTO orders (id, code, product_id, product_name, amount, customer_name, customer_email, "
            "access_token_hash, status, expires_at, created_at, updated_at) VALUES "
            "(1, 'CTAAAAAAAA', 1, 'P', 10000, 'K', 'k@x.vn', 'h', 'paid', '2026-01-01', '2026-01-01', '2026-01-01')"
        )
    command.upgrade(cfg, "head")
    with engine.connect() as conn:
        rows = conn.exec_driver_sql("SELECT order_id, product_id, product_name, price FROM order_items").all()
    assert rows == [(1, 1, "P", 10000)]
    command.downgrade(cfg, "base")
