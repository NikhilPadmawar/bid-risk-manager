import os

# Must be set before the app is imported, so tests never touch the real database.
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["LOG_FILE"] = "test.log"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app


@pytest.fixture()
def client():
    """A test client backed by a fresh, empty in-memory database."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    engine.dispose()


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