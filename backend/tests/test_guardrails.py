def test_guardrail_blocks_manual_message(client):
    resp = client.post(
        "/api/v1/channels/mock/webhook",
        json={"external_id": "u-guard-1", "content": "你好"},
    )
    assert resp.status_code == 200
    conversation_id = resp.json()["conversation_id"]

    blocked = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "可以代开发票吗", "direction": "out", "source": "manual"},
    )
    assert blocked.status_code == 200

    hits = client.get("/api/v1/admin/guardrails/hits").json()
    assert any("代开发票" in item["note"] for item in hits)


def test_guardrail_safe_context_allowlist():
    from app.db import SessionLocal
    from app.guardrails.service import GuardrailService
    from app.models import GuardrailRule

    with SessionLocal() as db:
        db.add(
            GuardrailRule(
                tenant_id="tenant-default",
                rule_type="content_safety",
                name="品牌违禁词-语境测试",
                pattern_json={"keywords": ["最", "第一"]},
                action="block",
                enabled=True,
            )
        )
        db.commit()

    with SessionLocal() as db:
        service = GuardrailService(db)
        assert service.check("tenant-default", "最近有到店福利，欢迎来看看").passed
        assert service.check("tenant-default", "客服会第一时间回复您").passed
        assert not service.check("tenant-default", "这是最好的服务").passed
        assert not service.check("tenant-default", "我们是行业第一").passed
        assert not service.check("tenant-default", "最近活动很多，而且效果最好").passed
