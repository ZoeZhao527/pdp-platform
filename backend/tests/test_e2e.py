"""1.0 全链路 E2E：发指令 -> 生成资产包 -> 审批 -> 整月排期 -> 自动下发 -> 验收回填 KPI。"""

import time
from datetime import datetime


def test_full_loop_e2e(client):
    industries = client.get("/api/v1/platform/industries").json()
    catering = next(item for item in industries if item["code"] == "catering")

    created = client.post(
        "/api/v1/platform/instructions",
        json={
            "title": "餐饮会员日储值促活",
            "content": "目标：储值额 20 万；人群：会员；活动：会员日+储值回馈",
            "industry_id": catering["id"],
            "params": {
                "goal_value": "20万",
                "kpi_metrics": "到店率,储值额,复购率",
                "activity_type": "会员日,储值回馈",
                "content_channels": "朋友圈,社群",
            },
        },
    ).json()

    generated = client.post(f"/api/v1/platform/instructions/{created['id']}/generate").json()
    assert generated["status"] == "已产出"
    assert generated["asset"]["activity_plan"]["theme"] == "餐饮会员日储值促活"
    assert "activity_details" in generated["asset"]
    assert "card_structure" in generated["asset"]

    client.put(
        "/api/v1/platform/send-policy",
        json={"auto_enabled": True, "window_start": "00:00", "window_end": "23:59"},
    )
    approved = client.post(f"/api/v1/platform/instructions/{created['id']}/approve").json()
    assert approved["status"] == "已批准"
    assert approved["tasks"] == 5
    assert approved["todo_count"] > 0

    deadline = time.time() + 12
    detail = None
    while time.time() < deadline:
        execution = client.get("/api/v1/platform/execution").json()
        detail = next(
            (item for item in execution["instructions"] if item["id"] == created["id"]),
            None,
        )
        if detail is None:
            time.sleep(0.3)
            continue
        channel_tasks = [
            task for task in detail["tasks"] if not task.get("todo") and task["channel"] != "企微"
        ]
        if channel_tasks and all(
            task["status"] in {"已完成", "已拦截", "已失败"} for task in channel_tasks
        ):
            break
        time.sleep(0.3)
    assert detail is not None
    channel_tasks = [
        task for task in detail["tasks"] if not task.get("todo") and task["channel"] != "企微"
    ]
    assert len(channel_tasks) == 5
    assert all(task["status"] in {"已完成", "已拦截", "已失败"} for task in channel_tasks)

    execution = client.get("/api/v1/platform/execution").json()
    board = next(item for item in execution["instructions"] if item["id"] == created["id"])
    due_todo = next(task for task in board["tasks"] if task.get("todo") and task["status"] == "待安排")
    today = datetime.now().strftime("%Y-%m-%d")
    client.put(
        f"/api/v1/platform/execution/todos/{due_todo['id']}",
        json={"due_at": today, "due_time": "00:01", "status": "待安排"},
    )
    scheduler = client.post("/api/v1/platform/execution/scheduler/run").json()
    assert scheduler["dispatched"] >= 1

    accepted = client.post(
        f"/api/v1/platform/instructions/{created['id']}/accept",
        json={"kpi_results": {"储值额": 200000, "到店率": 0.15}},
    ).json()
    assert accepted["status"] == "已验收"
    assert accepted["report_id"]

    report = client.get(f"/api/v1/platform/reports/{accepted['report_id']}").json()
    assert "KPI 对比" in report["content"]
    assert "储值额" in report["content"]
    assert "达成率" in report["content"]

    final = client.get("/api/v1/platform/execution").json()
    assert any(item["id"] == created["id"] for item in final["instructions"])
    assert any(item["kind"] == "验收报告" for item in final["reports"])
