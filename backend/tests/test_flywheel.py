def test_flywheel_trigger_creates_cycle(client):
    resp = client.post(
        "/api/v1/flywheel/trigger",
        json={"signal_text": "客户皮肤敏感泛红，想了解护理方案", "source_type": "message"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["cycle_id"]
    assert "敏感修护" in (data["tags"] or {}).get("tags", [])
    assert data["reply"]

    dashboard = client.get("/api/v1/flywheel/dashboard").json()
    assert dashboard["total_cycles"] >= 1


def test_topic_relevance_scoring():
    from app.flywheel.relevance import score_relevance

    assert score_relevance("敏感肌护肤新品上市", "beauty") >= 1.0
    assert score_relevance("会员积分新品上市", "retail") >= 1.0
    assert score_relevance("会员日优惠活动", "retail") < 1.0
    assert score_relevance("DOTA2 电竞比赛", "beauty") < 0.3
    assert score_relevance("某明星演唱会官宣", "catering") < 0.3


def test_managed_strategy_task_in_execution_center(client):
    client.put(
        "/api/v1/platform/send-policy",
        json={"auto_enabled": True, "window_start": "00:00", "window_end": "23:59"},
    )
    client.post(
        "/api/v1/strategies",
        json={
            "title": "托管测试策略",
            "activity_type": "会员日",
            "channels": "朋友圈",
            "cadence": "每日1条",
            "kpi_metrics": "GMV,复购率",
        },
    )
    strategies = client.get("/api/v1/strategies").json()
    strategy_id = next(item["id"] for item in strategies if item["name"] == "托管测试策略")
    client.post(f"/api/v1/strategies/{strategy_id}/toggle-managed").json()
    client.post("/api/v1/flywheel/run-auto?limit=0&collect_topics=false").json()

    execution = client.get("/api/v1/platform/execution").json()
    assert any(
        task["title"].startswith("托管测试策略") and task.get("todo")
        for task in execution["managed_tasks"]
    )
    assert any(
        task["title"].startswith("托管测试策略") and task["status"] in {"已完成", "已拦截", "已失败"}
        for task in execution["managed_tasks"]
    )
