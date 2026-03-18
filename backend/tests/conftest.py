from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{ROOT / 'test.db'}"
os.environ["JWT_SECRET"] = "test-secret"
os.environ["OPENAI_ENABLE_LIVE"] = "false"

from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import seed_demo_data  # noqa: E402


@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_demo_data(db)
        db.commit()
    yield


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def auth_headers(client):
    def _factory(email: str = "reviewer.w@example.com", password: str = "demo1234") -> dict[str, str]:
        response = client.post("/api/auth/login", json={"email": email, "password": password})
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    return _factory


@pytest.fixture
def patient_id(client, auth_headers):
    response = client.get("/api/patients", headers=auth_headers("patient.a@example.com"))
    return response.json()[0]["id"]


@pytest.fixture
def patient_b_id(client, auth_headers):
    response = client.get("/api/patients", headers=auth_headers("patient.b@example.com"))
    return response.json()[0]["id"]
