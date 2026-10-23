import os

# Must be set before the app is imported, so tests never touch the real database.
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["LOG_FILE"] = "test.log"
os.environ["OPENROUTER_API_KEY"] = ""  # tests must never use a real key

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app


@pytest.fixture()
def engine():
    """A fresh, empty in-memory database for each test."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def db(engine):
    """A database session for tests that work with the database directly."""
    session = sessionmaker(bind=engine, autoflush=False)()
    yield session
    session.close()


@pytest.fixture()
def client(engine):
    """A test client whose app uses the test database."""
    TestingSession = sessionmaker(bind=engine, autoflush=False)

    def override_get_db():
        session = TestingSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def make_client(client):
    def _make(name="Acme Corp", **overrides):
        response = client.post("/clients", json={"name": name, "industry": "Retail", **overrides})
        assert response.status_code == 201
        return response.json()

    return _make


@pytest.fixture()
def make_bid(client):
    def _make(client_id, **overrides):
        body = {
            "client_id": client_id,
            "title": "Website redesign",
            "value": 100000,
            "estimated_cost": 80000,
            "deadline": "2026-12-01",
            **overrides,
        }
        response = client.post("/bids", json=body)
        assert response.status_code == 201
        return response.json()

    return _make