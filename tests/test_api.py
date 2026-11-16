from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest

from app import mailer
from app.config import Settings
from app.departments import Department
from app.errors import MailDeliveryError, ModelError
from app.main import create_app

BODY = {"email": "jan.nowak@example.com", "message": "Nie działa mi komputer"}


class FakeGraph:
    """Stands in for the compiled LangGraph."""

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.error: Exception | None = None

    async def ainvoke(self, request: dict) -> dict:
        if self.error:
            raise self.error
        self.calls.append(request)
        return {
            "sent_to": Department.HELP_DESK,
            "decided_by": "decision_model",
            "confidence": 0.95,
        }


@pytest.fixture
def graph():
    return FakeGraph()


@pytest.fixture
async def client(graph):
    app = create_app()  # lifespan is not run: dependencies are injected below
    app.state.graph = graph
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        yield http


async def test_routes_message_and_reports_recipient(client, graph):
    response = await client.post("/api/v1/messages", json=BODY)

    assert response.status_code == 200
    assert response.json() == {
        "recipient": "help-desk@example.com",
        "decided_by": "decision_model",
        "confidence": 0.95,
    }
    assert graph.calls == [BODY]
    assert response.headers["X-Request-ID"]


@pytest.mark.parametrize(
    "body",
    [
        {"email": "not-an-email", "message": "hi"},
        {"email": "jan@example.com", "message": "  "},
        {"email": "jan@żółw.pl", "message": "hi"},
        {"email": "żółw@example.com", "message": "hi"},
        {},
    ],
)
async def test_invalid_input_is_a_problem_response(client, graph, body):
    response = await client.post("/api/v1/messages", json=body)

    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"
    assert {"title", "status", "detail", "request_id"} <= response.json().keys()
    assert graph.calls == []


async def test_mail_failure_is_reported(client, graph):
    graph.error = MailDeliveryError("smtp down")
    failed = await client.post("/api/v1/messages", json=BODY)

    assert failed.status_code == 502
    assert failed.json()["detail"] == MailDeliveryError.detail


async def test_model_failure_hides_internal_details(client, graph, caplog):
    graph.error = ModelError("connect to http://ollama:11434 refused")
    response = await client.post("/api/v1/messages", json=BODY)

    assert response.status_code == 503
    assert "ollama" not in response.text
    assert "ollama:11434" in caplog.text


async def test_errors_are_logged_with_the_request_id(client, graph, caplog):
    for graph.error in (MailDeliveryError("smtp down"), RuntimeError("boom")):
        response = await client.post("/api/v1/messages", json=BODY)
        assert response.json()["request_id"] in caplog.records[-1].getMessage()


@pytest.mark.parametrize(
    ("method", "path", "status"), [("GET", "/nope", 404), ("GET", "/api/v1/messages", 405)]
)
async def test_unknown_path_and_method_are_problem_responses(client, method, path, status):
    response = await client.request(method, path)

    assert response.status_code == status
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["request_id"] == response.headers["X-Request-ID"]
    if status == 405:
        assert response.headers["Allow"] == "POST"


async def test_health_accepts_untagged_model_names(client, monkeypatch):
    class FakeOllama:
        async def list(self):
            names = ("qwen3:latest", "d3:2b")
            return SimpleNamespace(models=[SimpleNamespace(model=name) for name in names])

    client._transport.app.state.settings = Settings(_env_file=None, agent_model="qwen3")
    client._transport.app.state.ollama = FakeOllama()
    monkeypatch.setattr(mailer, "connect", lambda settings: MagicMock())

    response = await client.get("/api/v1/health")

    assert response.json()["components"]["ollama"] == "ok", response.text


async def test_unexpected_error_hides_details(client, graph):
    graph.error = RuntimeError("secret internals")
    response = await client.post("/api/v1/messages", json=BODY)

    assert response.status_code == 500
    assert "secret" not in response.text
    assert response.json()["request_id"]


async def test_swagger_is_served_under_api_v1_docs(client):
    assert (await client.get("/api/v1/docs")).status_code == 200
    schema = (await client.get("/api/v1/openapi.json")).json()
    assert "/api/v1/messages" in schema["paths"]
