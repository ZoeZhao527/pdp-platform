def test_ops_webhook_routes_to_agent(client):
    resp = client.post(
        "/api/v1/channels/mock/webhook",
        json={"external_id": "u-ops-1", "content": "我想了解敏感肌护理方案"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["route"] == "ops"
    assert data["reply"]

    conversations = client.get("/api/v1/conversations").json()
    assert any(item["id"] == data["conversation_id"] for item in conversations)


def test_cs_webhook_routes_to_external_platform(client):
    resp = client.post(
        "/api/v1/channels/mock/webhook",
        json={"external_id": "u-cs-1", "content": "我要转人工客服"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["route"] == "cs"
    assert data["reply"]

    session = client.post(
        "/api/v1/cs-bridge/sessions",
        json={"conversation_id": data["conversation_id"], "platform": "echo"},
    )
    assert session.status_code == 200
    assert session.json()["ok"] is True

