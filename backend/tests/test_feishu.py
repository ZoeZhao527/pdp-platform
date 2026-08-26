"""飞书接入接口测试。"""


def test_webhook_challenge(client):
    resp = client.post("/webhook/feishu", json={"challenge": "abc-123"})
    assert resp.status_code == 200
    assert resp.json()["challenge"] == "abc-123"


def test_feishu_messages_mock(client):
    resp = client.get("/api/v1/feishu/messages?limit=5")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert "sender" in data[0]
    assert "text" in data[0]


def test_handle_feedback_command(client):
    resp = client.post("/api/v1/feishu/handle", json={"text": "回传：今日卖卡12单"})
    assert resp.status_code == 200
    reply = resp.json()["reply"]
    assert "已记录回传" in reply
    assert "12" in reply


def test_handle_list_strategies(client):
    resp = client.post("/api/v1/feishu/handle", json={"text": "查看当前策略"})
    assert resp.status_code == 200
    reply = resp.json()["reply"]
    # 有策略时返回列表，无策略时返回提示
    assert isinstance(reply, str)
    assert len(reply) > 0


def test_handle_toggle_managed(client):
    resp = client.post("/api/v1/feishu/handle", json={"text": "开启策略托管"})
    assert resp.status_code == 200
    reply = resp.json()["reply"]
    assert "托管" in reply


def test_handle_unknown_command(client):
    resp = client.post("/api/v1/feishu/handle", json={"text": "今天天气如何"})
    assert resp.status_code == 200
    assert "未识别" in resp.json()["reply"]


def test_send_message_mock(client):
    resp = client.post("/api/v1/feishu/send", json={"text": "测试消息"})
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
