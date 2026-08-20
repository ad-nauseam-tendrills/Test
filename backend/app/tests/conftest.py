import os
import sys
from pathlib import Path

DEFAULT_TEST_DATABASE_URL = (
    "postgresql+psycopg2://postgres:postgres@localhost:5432/instaopt_test"
)

# This suite DROPS EVERY TABLE, so it must never inherit an ambient
# DATABASE_URL. A developer with DATABASE_URL exported for local work --
# or, far worse, pointed at a shared or production database -- would
# otherwise lose it by running pytest. The test database is therefore
# forced here, overriding the environment rather than deferring to it.
# Point tests at a different database with TEST_DATABASE_URL.
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", DEFAULT_TEST_DATABASE_URL)
os.environ["UPLOAD_DIR"] = "/tmp/instaopt_test_uploads"
os.environ["VARIANT_DIR"] = "/tmp/instaopt_test_variants"

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine.url import make_url
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.all_models import Base
from app.db.session import get_db
from app.main import app


def _assert_safe_to_wipe(database_url: str) -> None:
    """
    Refuse to drop tables in a database that isn't clearly a test database.

    Belt-and-braces alongside the forced DATABASE_URL above: if someone
    sets TEST_DATABASE_URL to a real database, this stops the suite before
    it destroys anything.
    """
    name = (make_url(database_url).database or "").lower()
    if "test" not in name:
        raise RuntimeError(
            f"Refusing to run the test suite against database {name!r}: this suite "
            "drops every table, and the database name does not contain 'test'. "
            "Set TEST_DATABASE_URL to a dedicated test database."
        )


engine = create_engine(settings.DATABASE_URL, future=True)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    _assert_safe_to_wipe(settings.DATABASE_URL)
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(settings.VARIANT_DIR, exist_ok=True)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db_session():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        # Clean all tables between tests to keep them independent.
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(table.delete())
        session.commit()
        session.close()


@pytest.fixture()
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
