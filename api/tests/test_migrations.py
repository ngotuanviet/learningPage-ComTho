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
