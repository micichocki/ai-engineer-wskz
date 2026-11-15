import asyncio

import pytest
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage

from app import mailer
from app.config import Settings
from app.decision import Decision
from app.departments import Department
from app.errors import MailDeliveryError, ModelError
from app.graph import build_graph

SETTINGS = Settings(_env_file=None)
REQUEST = {"email": "jan.nowak@example.com", "message": "Nie działa mi komputer"}


class FakeChatModel(FakeMessagesListChatModel):
    def bind_tools(self, tools, **kwargs):
        return self


class FakeDecisionModel:
    def __init__(self, result: Decision | Exception) -> None:
        self._result = result

    async def classify(self, message: str) -> Decision:
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


def tool_call(to: str, call_id: str = "call-1") -> dict:
    return {"name": "send_email", "args": {"to": to}, "id": call_id}


@pytest.fixture
def outbox(monkeypatch):
    sent = []
    monkeypatch.setattr(mailer, "send_email", lambda settings, **mail: sent.append(mail))
    return sent


class FailingChatModel(FakeChatModel):
    async def ainvoke(self, *args, **kwargs):
        raise RuntimeError("ollama is down")


async def run(response: AIMessage | FakeChatModel, decision: Decision | Exception) -> dict:
    chat = response if isinstance(response, FakeChatModel) else FakeChatModel(responses=[response])
    return await build_graph(SETTINGS, chat, FakeDecisionModel(decision)).ainvoke(REQUEST)


async def test_agent_tool_call_sends_original_message_with_reply_to(outbox):
    state = await run(
        AIMessage(content="", tool_calls=[tool_call("help-desk@example.com")]),
        Decision(Department.HELP_DESK, 0.95),
    )

    assert outbox == [
        {
            "to": Department.HELP_DESK,
            "reply_to": "jan.nowak@example.com",
            "body": "Nie działa mi komputer",
        }
    ]
    assert state["sent_to"] is Department.HELP_DESK
    assert state["decided_by"] == "decision_model"
    assert state["confidence"] == 0.95


async def test_only_one_email_is_sent_for_several_tool_calls(outbox):
    await run(
        AIMessage(
            content="",
            tool_calls=[tool_call("it@example.com", "a"), tool_call("kadry@example.com", "b")],
        ),
        Decision(Department.IT, 0.9),
    )

    assert [mail["to"] for mail in outbox] == [Department.IT]


@pytest.mark.parametrize(
    ("to", "confidence"),
    [("it@example.com", 0.4), ("kadry@example.com", 0.95)],
    ids=["low-confidence", "overrides-suggestion"],
)
async def test_decision_is_attributed_to_the_agent(outbox, to, confidence):
    state = await run(
        AIMessage(content="", tool_calls=[tool_call(to)]), Decision(Department.IT, confidence)
    )

    assert state["decided_by"] == "agent"


@pytest.mark.parametrize(
    ("response", "decision"),
    [
        (FailingChatModel(responses=[]), Decision(Department.IT, 0.9)),
        (AIMessage(content="This is for the help desk."), Decision(Department.IT, 0.9)),
        (
            AIMessage(content="", tool_calls=[tool_call("ceo@example.com")]),
            Decision(Department.IT, 0.9),
        ),
        (
            AIMessage(content="", tool_calls=[tool_call("kadry@example.com")]),
            ModelError("d3 is not loaded"),
        ),
        (
            AIMessage(
                content="",
                tool_calls=[{"name": "send_mail", "args": {"to": "it@example.com"}, "id": "x"}],
            ),
            Decision(Department.IT, 0.9),
        ),
    ],
    ids=[
        "agent-down",
        "no-tool-call",
        "address-outside-the-list",
        "decision-model-down",
        "wrong-tool-name",
    ],
)
async def test_model_failure_is_an_error_and_sends_nothing(outbox, response, decision):
    with pytest.raises(ModelError):
        await run(response, decision)

    assert outbox == []


async def test_mail_delivery_failure_is_not_swallowed(monkeypatch):
    def broken(settings, **mail):
        raise MailDeliveryError("smtp down")

    monkeypatch.setattr(mailer, "send_email", broken)

    with pytest.raises(MailDeliveryError, match="smtp down"):
        await run(
            AIMessage(content="", tool_calls=[tool_call("it@example.com")]),
            Decision(Department.IT, 0.9),
        )


async def test_agent_call_has_a_total_time_limit(outbox):
    class SlowChatModel(FakeChatModel):
        async def ainvoke(self, *args, **kwargs):
            await asyncio.sleep(5)

    settings = Settings(_env_file=None, model_timeout_seconds=0.01)
    graph = build_graph(
        settings, SlowChatModel(responses=[]), FakeDecisionModel(Decision(Department.IT, 0.9))
    )

    with pytest.raises(ModelError):
        await graph.ainvoke(REQUEST)
    assert outbox == []
