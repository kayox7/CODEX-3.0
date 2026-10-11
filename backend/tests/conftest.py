import os
import sys
import tempfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

# Ensure sdk package is importable
sdk_path = Path(__file__).resolve().parent.parent.parent / "sdk"
if str(sdk_path) not in sys.path:
    sys.path.insert(0, str(sdk_path))

from app.db import init_db, DB_FILE
import app.db as app_db
from app.seed import seed_database
from app.main import app

@pytest.fixture(autouse=True)
def setup_test_db(tmp_path):
    """Create a clean isolated SQLite database for each test."""
    test_db_file = tmp_path / "test_warden.db"
    test_db_path = str(test_db_file)
    
    # Redirect DB connection to temporary file
    old_sqlite_path = os.environ.get("SQLITE_PATH")
    os.environ["SQLITE_PATH"] = test_db_path
    app_db.DB_FILE = test_db_path

    # Initialize and seed fresh tables
    init_db()
    seed_database()

    yield test_db_path

    # Restore environment
    if old_sqlite_path is not None:
        os.environ["SQLITE_PATH"] = old_sqlite_path
        app_db.DB_FILE = old_sqlite_path
    else:
        os.environ.pop("SQLITE_PATH", None)
        app_db.DB_FILE = "warden.db"

@pytest.fixture
def client():
    """FastAPI TestClient fixture."""
    with TestClient(app) as test_client:
        yield test_client

@pytest.fixture
def admin_headers(client):
    """Auth headers for admin user."""
    res = client.post("/auth/login", json={"username": "admin", "password": "demo123"})
    assert res.status_code == 200, f"Admin login failed: {res.text}"
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def auditor_headers(client):
    """Auth headers for auditor user."""
    res = client.post("/auth/login", json={"username": "auditor", "password": "demo123"})
    assert res.status_code == 200, f"Auditor login failed: {res.text}"
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def approver_headers(client):
    """Auth headers for approver user."""
    res = client.post("/auth/login", json={"username": "approver", "password": "demo123"})
    assert res.status_code == 200, f"Approver login failed: {res.text}"
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
