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


UNUSED = ModelError("the other mode's model must not be called")


async def run(response: AIMessage | FakeChatModel, decision: Decision | Exception = UNUSED) -> dict:
    """Agent mode unless a decision is given; the unused model fails if it is called."""
    mode = "agent" if decision is UNUSED else "decision"
    settings = Settings(_env_file=None, router_mode=mode)
    chat = response if isinstance(response, FakeChatModel) else FakeChatModel(responses=[response])
    return await build_graph(settings, chat, FakeDecisionModel(decision)).ainvoke(REQUEST)


async def test_agent_tool_call_sends_original_message_with_reply_to(outbox):
    state = await run(AIMessage(content="", tool_calls=[tool_call("help-desk@example.com")]))

    assert outbox == [
        {
            "to": Department.HELP_DESK,
            "reply_to": "jan.nowak@example.com",
            "body": "Nie działa mi komputer",
        }
    ]
    assert state["sent_to"] is Department.HELP_DESK
    assert state["decided_by"] == "agent"
    assert "confidence" not in state


async def test_decision_mode_sends_through_the_same_tool_without_the_llm(outbox):
    state = await run(FailingChatModel(responses=[]), Decision(Department.KADRY, 0.95))

    assert outbox == [
        {"to": Department.KADRY, "reply_to": "jan.nowak@example.com", "body": REQUEST["message"]}
    ]
    assert state["sent_to"] is Department.KADRY
    assert state["decided_by"] == "decision_model"
    assert state["confidence"] == 0.95


async def test_only_one_email_is_sent_for_several_tool_calls(outbox):
    await run(
        AIMessage(
            content="",
            tool_calls=[tool_call("it@example.com", "a"), tool_call("kadry@example.com", "b")],
        )
    )

    assert [mail["to"] for mail in outbox] == [Department.IT]


@pytest.mark.parametrize(
    ("response", "decision"),
    [
        (FailingChatModel(responses=[]), UNUSED),
        (AIMessage(content="This is for the help desk."), UNUSED),
        (AIMessage(content="", tool_calls=[tool_call("ceo@example.com")]), UNUSED),
        (
            AIMessage(content="", tool_calls=[tool_call("kadry@example.com")]),
            ModelError("d3 is not loaded"),
        ),
        (
            AIMessage(
                content="",
                tool_calls=[{"name": "send_mail", "args": {"to": "it@example.com"}, "id": "x"}],
            ),
            UNUSED,
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
        await run(AIMessage(content="", tool_calls=[tool_call("it@example.com")]))


async def test_agent_call_has_a_total_time_limit(outbox):
    class SlowChatModel(FakeChatModel):
        async def ainvoke(self, *args, **kwargs):
            await asyncio.sleep(5)

    settings = Settings(_env_file=None, model_timeout_seconds=0.01)
    graph = build_graph(settings, SlowChatModel(responses=[]), FakeDecisionModel(UNUSED))

    with pytest.raises(ModelError):
        await graph.ainvoke(REQUEST)
    assert outbox == []


async def test_decision_call_has_a_total_time_limit(outbox):
    class SlowDecisionModel(FakeDecisionModel):
        async def classify(self, message: str) -> Decision:
            await asyncio.sleep(5)

    settings = Settings(_env_file=None, router_mode="decision", model_timeout_seconds=0.01)
    graph = build_graph(settings, FakeChatModel(responses=[]), SlowDecisionModel(UNUSED))

    with pytest.raises(ModelError, match="timed out"):
        await graph.ainvoke(REQUEST)
    assert outbox == []
