def test_knowledge_upload_and_search(client):
    content = "敏感肌护理：温和洁面，保湿优先，避免高浓度酸类成分。"
    resp = client.post(
        "/api/v1/knowledge/documents",
        files={"file": ("护理知识.txt", content.encode("utf-8"), "text/plain")},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ready"

    docs = client.get("/api/v1/knowledge/documents").json()
    assert any(item["name"] == "护理知识.txt" for item in docs)

    search = client.get("/api/v1/knowledge/search", params={"q": "敏感肌怎么护理"}).json()
    assert any("敏感肌" in item["content"] for item in search)

