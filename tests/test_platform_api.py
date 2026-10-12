from __future__ import annotations

from datetime import timedelta
from urllib.parse import parse_qs, urlparse

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import select

from platform_api.config import Settings
from platform_api.main import create_app
from platform_api.models import AuditEvent, UserSession, utc_now
from platform_api.wecom import WeComClient


def make_app():
    return create_app(
        Settings(
            database_url="sqlite://",
            enable_fake_wecom=True,
            session_idle_days=10,
            auth_transaction_ttl_seconds=300,
        )
    )


def login(client: TestClient, *, userid: str = "tester", is_admin: bool = False):
    created = client.post(
        "/api/v1/auth/wecom/transactions",
        json={"device_id": "test-device-001"},
    )
    assert created.status_code == 201, created.text
    transaction = created.json()
    assert transaction["mode"] == "fake"
    assert transaction["poll_secret"] not in transaction["qr_url"]

    approved = client.post(
        f"/api/v1/dev/auth/wecom/transactions/{transaction['transaction_id']}/approve",
        json={
            "wecom_userid": userid,
            "display_name": "测试用户",
            "department_code": "engineering",
            "is_admin": is_admin,
        },
    )
    assert approved.status_code == 200, approved.text

    polled = client.post(
        "/api/v1/auth/wecom/transactions/poll",
        json={
            "transaction_id": transaction["transaction_id"],
            "poll_secret": transaction["poll_secret"],
        },
    )
    assert polled.status_code == 200, polled.text
    assert polled.json()["status"] == "approved"
    assert polled.json()["exchange_code"]

    exchanged = client.post(
        "/api/v1/auth/token",
        json={
            "transaction_id": transaction["transaction_id"],
            "exchange_code": polled.json()["exchange_code"],
        },
    )
    assert exchanged.status_code == 200, exchanged.text
    return exchanged.json()


def test_health_and_unauthorized_access() -> None:
    app = make_app()
    with TestClient(app) as client:
        assert client.get("/health/live").json() == {"status": "ok"}
        assert client.get("/health/ready").json() == {"status": "ready"}
        assert client.get("/api/v1/me").status_code == 401


def test_real_wecom_qr_callback_and_token_exchange() -> None:
    settings = Settings(
        database_url="sqlite://",
        enable_fake_wecom=False,
        wecom_corp_id="ww-test-corp",
        wecom_agent_id="1000002",
        wecom_secret="server-side-secret",
        wecom_callback_url="https://platform.example.test/api/v1/auth/wecom/callback",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/cgi-bin/gettoken":
            assert request.url.params["corpsecret"] == "server-side-secret"
            return httpx.Response(
                200,
                json={"errcode": 0, "access_token": "wecom-token", "expires_in": 7200},
            )
        if request.url.path == "/cgi-bin/user/getuserinfo":
            assert request.url.params["code"] == "callback-code"
            return httpx.Response(200, json={"errcode": 0, "UserId": "zhangsan"})
        if request.url.path == "/cgi-bin/user/get":
            return httpx.Response(
                200,
                json={
                    "errcode": 0,
                    "userid": "zhangsan",
                    "name": "张三",
                    "department": [42],
                },
            )
        return httpx.Response(404, json={"errcode": 404, "errmsg": "not found"})

    provider = WeComClient(settings, transport=httpx.MockTransport(handler))
    app = create_app(settings, wecom_client=provider)
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/auth/wecom/transactions",
            json={"device_id": "desktop-real-wecom"},
        )
        assert created.status_code == 201, created.text
        transaction = created.json()
        assert transaction["mode"] == "wecom"
        login_query = parse_qs(urlparse(transaction["qr_url"]).query)
        assert login_query["appid"] == ["ww-test-corp"]
        assert login_query["agentid"] == ["1000002"]
        state = login_query["state"][0]
        assert transaction["poll_secret"] not in state

        invalid = client.get(
            "/api/v1/auth/wecom/callback",
            params={"code": "callback-code", "state": f"{state}-tampered"},
        )
        assert invalid.status_code == 400

        callback = client.get(
            "/api/v1/auth/wecom/callback",
            params={"code": "callback-code", "state": state},
        )
        assert callback.status_code == 200, callback.text
        assert "登录成功" in callback.text

        polled = client.post(
            "/api/v1/auth/wecom/transactions/poll",
            json={
                "transaction_id": transaction["transaction_id"],
                "poll_secret": transaction["poll_secret"],
            },
        )
        assert polled.status_code == 200
        assert polled.json()["user"]["display_name"] == "张三"

        token = client.post(
            "/api/v1/auth/token",
            json={
                "transaction_id": transaction["transaction_id"],
                "exchange_code": polled.json()["exchange_code"],
            },
        )
        assert token.status_code == 200
        headers = {"Authorization": f"Bearer {token.json()['access_token']}"}
        assert client.get("/api/v1/me", headers=headers).json()["wecom_userid"] == "zhangsan"


def test_fake_wecom_chat_usage_and_audit_closed_loop() -> None:
    app = make_app()
    with TestClient(app) as client:
        token = login(client, is_admin=True)
        headers = {"Authorization": f"Bearer {token['access_token']}"}
        me = client.get("/api/v1/me", headers=headers)
        assert me.status_code == 200
        assert me.json()["wecom_userid"] == "tester"

        conversation = client.post(
            "/api/v1/conversations",
            headers=headers,
            json={"title": "首个闭环"},
        )
        assert conversation.status_code == 201, conversation.text

        response = client.post(
            f"/api/v1/conversations/{conversation.json()['id']}/messages",
            headers=headers,
            json={"content": "请总结今天的工作", "logical_model": "general-fast"},
        )
        assert response.status_code == 200, response.text
        result = response.json()
        assert "Fake 模型回复" in result["content"]
        assert result["usage"]["total_tokens"] > 0
        assert result["usage"]["source"] == "estimated"

        usage = client.get("/api/v1/usage/me/summary", headers=headers)
        assert usage.status_code == 200
        assert usage.json()["request_count"] == 1
        assert usage.json()["total_tokens"] == result["usage"]["total_tokens"]

        audit = client.get("/api/v1/admin/audit/events", headers=headers)
        assert audit.status_code == 200
        actions = {item["action"] for item in audit.json()}
        assert "auth.session.created" in actions
        assert "conversation.created" in actions
        assert "ai.response.completed" in actions

        with app.state.database.session_factory() as session:
            ai_event = session.scalar(
                select(AuditEvent).where(AuditEvent.action == "ai.response.completed")
            )
            assert ai_event is not None
            serialized = str(ai_event.metadata_json)
            assert "请总结今天的工作" not in serialized
            assert ai_event.metadata_json["input_content_hash"]


def test_server_prompt_assignment_reaches_client_and_chat() -> None:
    app = make_app()
    with TestClient(app) as client:
        token = login(client, userid="admin", is_admin=True)
        headers = {"Authorization": f"Bearer {token['access_token']}"}

        prompt = client.post(
            "/api/v1/admin/prompts",
            headers=headers,
            json={
                "name": "weekly-report",
                "purpose": "生成公司周报",
                "version": 1,
                "system_prompt": "输出必须包含本周完成、风险和下周计划。",
                "status": "published",
            },
        )
        assert prompt.status_code == 201, prompt.text
        assigned = client.post(
            f"/api/v1/admin/prompts/{prompt.json()['id']}/assignments",
            headers=headers,
            json={"subject_type": "all", "subject_id": "", "required": True},
        )
        assert assigned.status_code == 201, assigned.text

        client_prompts = client.get("/api/v1/client/prompts", headers=headers)
        assert client_prompts.status_code == 200
        assert client_prompts.json()[0]["name"] == "weekly-report"
        assert client_prompts.json()[0]["required"] is True

        conversation = client.post(
            "/api/v1/conversations",
            headers=headers,
            json={"title": "Prompt 下发"},
        ).json()
        response = client.post(
            f"/api/v1/conversations/{conversation['id']}/messages",
            headers=headers,
            json={"content": "生成周报"},
        )
        assert response.status_code == 200
        assert response.json()["applied_prompts"] == ["weekly-report@1"]


def test_streaming_response_emits_typed_sse_events() -> None:
    app = make_app()
    with TestClient(app) as client:
        token = login(client)
        headers = {"Authorization": f"Bearer {token['access_token']}"}
        conversation = client.post(
            "/api/v1/conversations",
            headers=headers,
            json={"title": "流式对话"},
        ).json()
        response = client.post(
            f"/api/v1/conversations/{conversation['id']}/responses",
            headers=headers,
            json={"content": "流式返回测试"},
        )
        assert response.status_code == 200
        assert "event: response.created" in response.text
        assert "event: response.output_text.delta" in response.text
        assert "event: response.completed" in response.text


def test_idle_session_requires_new_scan_after_ten_days() -> None:
    app = make_app()
    with TestClient(app) as client:
        token = login(client)
        headers = {"Authorization": f"Bearer {token['access_token']}"}
        with app.state.database.session_factory() as session:
            stored = session.scalar(select(UserSession))
            assert stored is not None
            stored.last_activity_at = utc_now() - timedelta(days=10, seconds=1)
            session.commit()

        expired = client.get("/api/v1/me", headers=headers)
        assert expired.status_code == 401
        assert expired.json()["code"] == "session_expired"

        with app.state.database.session_factory() as session:
            stored = session.scalar(select(UserSession))
            assert stored is not None
            assert stored.status == "expired"


def test_access_token_is_only_persisted_as_hash() -> None:
    app = make_app()
    with TestClient(app) as client:
        token = login(client)
        with app.state.database.session_factory() as session:
            stored = session.scalar(select(UserSession))
            assert stored is not None
            assert stored.token_hash != token["access_token"]
            assert len(stored.token_hash) == 64
