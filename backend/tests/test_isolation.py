"""P4-1: Multi-tenant data isolation tests.

Verifies that non-admin users cannot access another tenant's data
by spoofing the X-Tenant-Id header.
"""
from fastapi.testclient import TestClient

from app.main import app


def _create_operator(client: TestClient, username: str = "iso_op") -> str:
    """Create an operator user in the default tenant, return its token."""
    client.post(
        "/api/v1/auth/users",
        json={"username": username, "password": "iso123456", "display_name": "隔离测试", "role": "operator"},
    )
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": "iso123456"})
    assert resp.status_code == 200
    return resp.json()["token"]


def _create_second_tenant(client: TestClient) -> str:
    """Create a second tenant via platform API, return its id."""
    resp = client.post(
        "/api/v1/dev/brands",
        json={"name": "隔离测试品牌B", "code": "iso-test-b", "industry_id": None},
    )
    if resp.status_code in (200, 201):
        return resp.json().get("id", "")
    # Fallback: list existing tenants and pick a non-default one
    tenants = client.get("/api/v1/platform/tenants").json()
    for t in tenants:
        if t.get("id") != "tenant-default":
            return t["id"]
    return "tenant-default"


def test_operator_cannot_access_other_tenant(client: TestClient):
    """Operator with X-Tenant-Id spoofed to a different tenant -> 403."""
    op_token = _create_operator(client)
    other_tenant = _create_second_tenant(client)

    # Access own tenant -> 200
    resp = client.get(
        "/api/v1/strategies",
        headers={"Authorization": f"Bearer {op_token}", "X-Tenant-Id": "tenant-default"},
    )
    assert resp.status_code == 200, f"own tenant should work: {resp.text}"

    # Access other tenant -> 403
    resp = client.get(
        "/api/v1/strategies",
        headers={"Authorization": f"Bearer {op_token}", "X-Tenant-Id": other_tenant},
    )
    assert resp.status_code == 403, f"cross-tenant should be blocked: {resp.text}"


def test_admin_can_switch_tenants(client: TestClient):
    """Admin role can access any tenant via X-Tenant-Id header."""
    other_tenant = _create_second_tenant(client)

    # Access default tenant -> 200
    resp = client.get("/api/v1/strategies", headers={"X-Tenant-Id": "tenant-default"})
    assert resp.status_code == 200

    # Access other tenant -> 200 (admin can switch)
    resp = client.get("/api/v1/strategies", headers={"X-Tenant-Id": other_tenant})
    assert resp.status_code == 200, f"admin should access any tenant: {resp.text}"
