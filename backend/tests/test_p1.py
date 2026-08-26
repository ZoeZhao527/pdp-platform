from datetime import datetime


def test_customer_profile_auto_built(client):
    resp = client.post(
        "/api/v1/channels/mock/webhook",
        json={"external_id": "u-profile-1", "customer_id": "c-profile-1", "content": "我皮肤敏感泛红，想了解护理"},
    )
    assert resp.status_code == 200
    conversation_id = resp.json()["conversation_id"]

    conversations = client.get("/api/v1/conversations").json()
    target = next(item for item in conversations if item["id"] == conversation_id)
    assert target["id"] == conversation_id

    customers = client.get("/api/v1/customers").json()
    profile_customer = next(item for item in customers if item["one_id"] == "c-profile-1")
    assert "皮肤敏感" in profile_customer["profile"].get("tags", [])

    detail = client.get(f"/api/v1/customers/{profile_customer['id']}/profile").json()
    assert detail["profile"]["tags"]


def test_content_safety_guardrail(client):
    resp = client.post(
        "/api/v1/channels/mock/webhook",
        json={"external_id": "u-safe-1", "content": "你好"},
    )
    assert resp.status_code == 200
    conversation_id = resp.json()["conversation_id"]

    client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "帮我联系赌博网站", "direction": "out", "source": "manual"},
    )
    hits = client.get("/api/v1/admin/guardrails/hits").json()
    assert any("赌博" in (item["note"] or "") for item in hits)


def test_llm_usage_and_budget_recorded(client):
    client.post(
        "/api/v1/channels/mock/webhook",
        json={"external_id": "u-usage-1", "content": "帮我看看抗衰项目"},
    )
    usage = client.get("/api/v1/admin/llm/usage").json()
    assert usage["budgets"]
    assert usage["budgets"][0]["tokens_used"] > 0


def test_flywheel_adopt_updates_metric(client):
    resp = client.post(
        "/api/v1/flywheel/trigger",
        json={"signal_text": "客户想了解社群运营方案", "source_type": "message"},
    )
    assert resp.status_code == 200
    cycle_id = resp.json()["cycle_id"]

    adopt = client.post(f"/api/v1/flywheel/{cycle_id}/adopt")
    assert adopt.status_code == 200
    assert adopt.json()["adopted"] is True

    dashboard = client.get("/api/v1/flywheel/dashboard").json()
    assert dashboard["total_adopted_count"] >= 1


def test_instruction_asset_package_has_rich_sections(client):
    industries = client.get("/api/v1/platform/industries").json()
    beauty = next(item for item in industries if item["code"] == "beauty")
    created = client.post(
        "/api/v1/platform/instructions",
        json={
            "title": "美丽田园 8月敏感肌焕肤促活",
            "content": "目标：GMV 30万；人群：敏感肌老客；活动：拉新+复购",
            "industry_id": beauty["id"],
            "params": {
                "goal_value": "30万",
                "activity_type": "会员日,拉新",
                "content_channels": "朋友圈,社群",
                "kpi_metrics": "转化率,GMV,复购率",
            },
        },
    ).json()
    generated = client.post(f"/api/v1/platform/instructions/{created['id']}/generate").json()
    assert generated["status"] == "已产出"
    asset = generated["asset"]
    for key in ["activity_details", "card_structure", "script_templates", "content_materials"]:
        assert key in asset
    assert asset["activity_plan"]["theme"].startswith("美丽田园")
    assert isinstance(asset["product_mix"], list)


def test_instruction_full_chain_auto_execution_and_acceptance(client):
    import time

    industries = client.get("/api/v1/platform/industries").json()
    beauty = next(item for item in industries if item["code"] == "beauty")
    created = client.post(
        "/api/v1/platform/instructions",
        json={
            "title": "连锁门店 8月会员日促活",
            "content": "目标：复购率提升；人群：会员；活动：会员日",
            "industry_id": beauty["id"],
            "params": {
                "activity_type": "会员日",
                "content_channels": "朋友圈,社群",
                "goal_value": "30万",
                "kpi_metrics": "转化率,GMV,复购率",
            },
        },
    ).json()
    generated = client.post(f"/api/v1/platform/instructions/{created['id']}/generate").json()
    assert generated["status"] == "已产出"

    approved = client.post(f"/api/v1/platform/instructions/{created['id']}/approve").json()
    assert approved["status"] == "已批准"
    assert approved["tasks"] == 5
    assert approved["todo_count"] > 0
    assert set(approved["plan"]) == {"1v1", "朋友圈", "社群", "短信", "跟进"}

    deadline = time.time() + 12
    detail = None
    while time.time() < deadline:
        rows = client.get("/api/v1/platform/instructions").json()
        detail = next(item for item in rows if item["id"] == created["id"])
        channel_tasks = [
            task for task in detail["tasks"] if not task.get("todo") and task["channel"] != "企微"
        ]
        if channel_tasks and all(
            task["status"] in {"已完成", "已拦截", "已失败"} for task in channel_tasks
        ):
            break
        time.sleep(0.3)
    assert detail is not None
    channel_tasks = [task for task in detail["tasks"] if not task.get("todo") and task["channel"] != "企微"]
    assert len(channel_tasks) == 5
    assert all(task["status"] == "已完成" for task in channel_tasks)
    assert detail["strategy_ids"] is not None
    assert detail["strategy_ids"].get("parent_task_id")
    retry_deadline = time.time() + 3
    while time.time() < retry_deadline and not detail["strategy_ids"].get("acceptance_report"):
        rows = client.get("/api/v1/platform/instructions").json()
        detail = next(item for item in rows if item["id"] == created["id"])
        time.sleep(0.1)
    assert detail["strategy_ids"].get("acceptance_report", {}).get("total") == 5

    accepted = client.post(
        f"/api/v1/platform/instructions/{created['id']}/accept",
        json={"kpi_results": {"GMV": 300000, "转化率": 0.12}},
    ).json()
    assert accepted["status"] == "已验收"
    assert accepted["report_id"]
    assert accepted["summary"]["total"] == 5
    after_accept = next(
        item for item in client.get("/api/v1/platform/instructions").json() if item["id"] == created["id"]
    )
    assert after_accept["strategy_ids"].get("report_id") == accepted["report_id"]

    reports = client.get("/api/v1/platform/reports").json()
    assert any(item["kind"] == "验收报告" for item in reports)
    report_detail = client.get(f"/api/v1/platform/reports/{accepted['report_id']}").json()
    assert "KPI 对比" in report_detail["content"]
    assert "达成率" in report_detail["content"]
    assert "GMV" in report_detail["content"]

    execution = client.get("/api/v1/platform/execution").json()
    board = next(item for item in execution["instructions"] if item["id"] == created["id"])
    todos = [task for task in board["tasks"] if task.get("todo")]
    assert len(todos) > 0
    first = todos[0]
    updated = client.put(
        f"/api/v1/platform/execution/todos/{first['id']}",
        json={"due_at": "2026-09-01", "due_time": "09:30", "content": "已编辑的待办内容", "status": "已确认"},
    ).json()
    assert updated["due_at"] == "2026-09-01"
    assert updated["due_time"] == "09:30"
    assert updated["content"] == "已编辑的待办内容"

    rebuilt = client.post(f"/api/v1/platform/instructions/{created['id']}/plan/rebuild").json()
    assert rebuilt["todo_count"] > 0

    execution = client.get("/api/v1/platform/execution").json()
    board = next(item for item in execution["instructions"] if item["id"] == created["id"])
    due_todo = next(task for task in board["tasks"] if task.get("todo"))
    due_today = datetime.now().strftime("%Y-%m-%d")
    client.put(
        "/api/v1/platform/send-policy",
        json={"auto_enabled": True, "window_start": "00:00", "window_end": "23:59"},
    )
    client.put(
        f"/api/v1/platform/execution/todos/{due_todo['id']}",
        json={"due_at": due_today, "due_time": "00:01", "status": "待安排"},
    )
    scheduler = client.post("/api/v1/platform/execution/scheduler/run").json()
    assert scheduler["dispatched"] >= 1
    execution = client.get("/api/v1/platform/execution").json()
    board = next(item for item in execution["instructions"] if item["id"] == created["id"])
    dispatched = next(task for task in board["tasks"] if task["id"] == due_todo["id"])
    assert dispatched["status"] in {"已完成", "已拦截", "已失败"}

    manual_todo = next(
        task for task in board["tasks"] if task.get("todo") and task["id"] != due_todo["id"]
    )
    client.put(
        f"/api/v1/platform/execution/todos/{manual_todo['id']}",
        json={"status": "已暂停"},
    )
    manual = client.post(f"/api/v1/platform/execution/todos/{manual_todo['id']}/dispatch").json()
    assert manual["status"] in {"已完成", "已拦截", "已失败"}


def test_send_policy_pause_and_resend(client):
    industries = client.get("/api/v1/platform/industries").json()
    beauty = next(item for item in industries if item["code"] == "beauty")
    created = client.post(
        "/api/v1/platform/instructions",
        json={
            "title": "发送策略验证指令",
            "content": "目标：验证发送策略",
            "industry_id": beauty["id"],
            "params": {"content_channels": "朋友圈,社群"},
        },
    ).json()
    generated = client.post(f"/api/v1/platform/instructions/{created['id']}/generate").json()
    assert generated["status"] == "已产出"
    client.post(f"/api/v1/platform/instructions/{created['id']}/approve").json()
    due_today = datetime.now().strftime("%Y-%m-%d")

    def due_todo_id() -> str:
        execution = client.get("/api/v1/platform/execution").json()
        board = next(item for item in execution["instructions"] if item["id"] == created["id"])
        return next(task["id"] for task in board["tasks"] if task.get("todo") and task["status"] == "待安排")

    client.put(
        "/api/v1/platform/send-policy",
        json={"auto_enabled": True, "window_start": "00:00", "window_end": "23:59", "max_per_day": {}},
    )
    todo = due_todo_id()
    client.put(f"/api/v1/platform/execution/todos/{todo}", json={"due_at": due_today, "due_time": "00:01"})
    result = client.post("/api/v1/platform/execution/scheduler/run").json()
    assert result["dispatched"] >= 1

    client.put("/api/v1/platform/send-policy", json={"auto_enabled": False})
    todo = due_todo_id()
    client.put(f"/api/v1/platform/execution/todos/{todo}", json={"due_at": due_today, "due_time": "00:01"})
    result = client.post("/api/v1/platform/execution/scheduler/run").json()
    assert result["reason"] == "auto_disabled"

    client.put("/api/v1/platform/send-policy", json={"auto_enabled": True})
    client.post(f"/api/v1/platform/instructions/{created['id']}/plan/pause").json()
    result = client.post("/api/v1/platform/execution/scheduler/run").json()
    assert result["paused"] >= 1

    client.post(f"/api/v1/platform/instructions/{created['id']}/plan/pause").json()
    execution = client.get("/api/v1/platform/execution").json()
    board = next(item for item in execution["instructions"] if item["id"] == created["id"])
    missed = next(task for task in board["tasks"] if task.get("todo") and task["status"] == "待安排")
    client.put(f"/api/v1/platform/execution/todos/{missed['id']}", json={"status": "已错过"})
    resent = client.post(f"/api/v1/platform/execution/todos/{missed['id']}/dispatch").json()
    assert resent["status"] in {"已完成", "已拦截", "已失败"}

    client.put(
        "/api/v1/platform/send-policy",
        json={"auto_enabled": True, "window_start": "09:00", "window_end": "21:00", "grace_hours": 24},
    )


def test_viewer_role_read_only(client):
    client.post(
        "/api/v1/auth/users",
        json={"username": "viewer_check", "password": "viewer123", "role": "viewer"},
    )
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "viewer_check", "password": "viewer123"},
    ).json()
    original = dict(client.headers)
    client.headers.update({"Authorization": f"Bearer {login['token']}"})
    try:
        read = client.get("/api/v1/platform/instructions")
        assert read.status_code == 200
        blocked = client.post(
            "/api/v1/platform/instructions",
            json={"title": "viewer 不应创建", "content": "x"},
        )
        assert blocked.status_code == 403
        scheduler = client.post("/api/v1/platform/execution/scheduler/run")
        assert scheduler.status_code == 403
    finally:
        client.headers.clear()
        client.headers.update(original)


def test_all_industries_have_full_template_sets(client):
    industries = client.get("/api/v1/platform/industries").json()
    assert len(industries) >= 6
    for industry in industries:
        rows = client.get(
            f"/api/v1/platform/industry-templates?industry_id={industry['id']}"
        ).json()
        kinds = {row["kind"] for row in rows}
        assert kinds == {"activity", "catalog", "sales", "content", "kpi"}


def test_flywheel_advisories_shape(client):
    data = client.get("/api/v1/flywheel/advisories").json()
    assert set(data.keys()) == {"signals", "demands", "matches", "strategies", "suggestions"}
    assert isinstance(data["suggestions"], list)


def test_strategy_sediment_from_instruction(client):
    industries = client.get("/api/v1/platform/industries").json()
    beauty = next(item for item in industries if item["code"] == "beauty")
    created = client.post(
        "/api/v1/platform/instructions",
        json={
            "title": "沉淀测试指令",
            "content": "目标：验证沉淀",
            "industry_id": beauty["id"],
            "params": {"kpi_metrics": "转化率,GMV"},
        },
    ).json()
    client.post(f"/api/v1/platform/instructions/{created['id']}/generate").json()
    sediment = client.post(f"/api/v1/strategies/from-instruction/{created['id']}").json()
    rows = client.get("/api/v1/strategies").json()
    row = next(item for item in rows if item["id"] == sediment["id"])
    assert row["name"].startswith("沉淀测试指令")
    assert row["params"]["activity_type"]
    assert row["params"]["kpi_metrics"]

