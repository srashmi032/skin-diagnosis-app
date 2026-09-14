from __future__ import annotations

import io
import os
import tempfile

import pytest

# Configure the app for an isolated test environment BEFORE importing it.
_TMP = tempfile.mkdtemp(prefix="skindx-test-")
os.environ["SKINDX_DATABASE_URL"] = f"sqlite:///{_TMP}/test.db"
os.environ["SKINDX_STORAGE_LOCAL_DIR"] = f"{_TMP}/uploads"
os.environ["SKINDX_JWT_SECRET"] = "test-secret"
os.environ["SKINDX_ENVIRONMENT"] = "test"

from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.services.seed import seed_conditions  # noqa: E402
from app.database import SessionLocal  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _schema():
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_conditions(db)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def png_bytes() -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (640, 640), (180, 140, 130)).save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def auth_client(client):
    email = "patient@example.com"
    client.post(
        "/v1/auth/register", json={"email": email, "password": "supersecret1"}
    )
    token = client.post(
        "/v1/auth/login", json={"email": email, "password": "supersecret1"}
    ).json()["access_token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    for ctype in ("image_storage", "ai_processing"):
        client.post("/v1/consents", json={"consent_type": ctype, "granted": True})
    return client
