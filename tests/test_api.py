import httpx
import pytest

from app.departments import Department
from app.errors import MailDeliveryError
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
            "suggestion": Department.HELP_DESK,
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
        "suggested_department": "help-desk@example.com",
        "confidence": 0.95,
    }
    assert graph.calls == [BODY]
    assert response.headers["X-Request-ID"]


@pytest.mark.parametrize(
    "body",
    [{"email": "not-an-email", "message": "hi"}, {"email": "jan@example.com", "message": "  "}, {}],
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
    assert failed.json()["detail"] == "smtp down"


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
