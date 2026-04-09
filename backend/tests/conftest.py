import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.seed import seed_data  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def seeded_db():
    seed_data()
    yield


@pytest.fixture(scope="session")
def client(seeded_db):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def teacher_headers(client):
    response = client.post("/api/v1/auth/login", json={
        "account": "teacher@aitutor.local",
        "password": "Teacher123!",
        "role": "teacher",
    })
    token = response.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
def student_headers(client):
    response = client.post("/api/v1/auth/login", json={
        "account": "student@aitutor.local",
        "password": "Student123!",
        "role": "student",
    })
    token = response.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}
