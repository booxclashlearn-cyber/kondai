import os

os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings, get_settings
from app.db import Base, get_session
from app.main import app

engine = create_engine(
    "sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
)
TestingSession = sessionmaker(engine, expire_on_commit=False)


@pytest.fixture(autouse=True)
def database():
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def session():
    with TestingSession() as value:
        yield value


@pytest.fixture
def client(session: Session, tmp_path):
    def override():
        yield session

    app.dependency_overrides[get_session] = override
    app.dependency_overrides[get_settings] = lambda: Settings(
        app_env="test",
        database_url="sqlite+pysqlite:///:memory:",
        local_storage_path=str(tmp_path / "uploads"),
    )
    with TestClient(app) as value:
        yield value
    app.dependency_overrides.clear()


@pytest.fixture
def project_payload():
    return {
        "title": "The Red Key",
        "genre": "Mystery thriller",
        "intended_audience": "Adult mystery fans",
        "target_duration_seconds": 240,
        "description": "A controlled synthetic film.",
    }
