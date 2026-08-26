import os

import pytest
from fastapi.testclient import TestClient

if os.path.exists("./test_pdp.db"):
    os.remove("./test_pdp.db")

os.environ["PDP_DATABASE_URL"] = "sqlite:///./test_pdp.db"
os.environ["PDP_LLM_LOCAL_ENABLED"] = "false"
os.environ["PDP_EMBEDDING_PROVIDER"] = "local"
os.environ["PDP_FEISHU_MOCK"] = "true"
os.environ["PDP_FEISHU_ENABLED"] = "false"

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        login = test_client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        assert login.status_code == 200, login.text
        token = login.json()["token"]
        test_client.headers.update({"Authorization": f"Bearer {token}"})
        yield test_client
    if os.path.exists("./test_pdp.db"):
        os.remove("./test_pdp.db")
