from types import SimpleNamespace

import ollama
import pytest

from app.decision import Decision, OllamaDecisionModel
from app.departments import Department
from app.errors import ModelError


class FakeOllama:
    def __init__(self, answer=None, error: Exception | None = None) -> None:
        self.answer, self.error, self.requests = answer, error, []

    async def systemone(self, **request):
        self.requests.append(request)
        if self.error:
            raise self.error
        return SimpleNamespace(answers={"department": self.answer})


async def test_classify_asks_one_choice_question_over_all_departments():
    client = FakeOllama(SimpleNamespace(choice="kadry@example.com", confidence=0.91))

    decision = await OllamaDecisionModel(client, "d3:2b").classify("Urlop na jutro")

    assert decision == Decision(Department.KADRY, 0.91)
    (request,) = client.requests
    assert request["model"] == "d3:2b"
    assert request["state"] == "Urlop na jutro"
    question = request["questions"]["department"]
    assert question["type"] == "choice"
    assert set(question["criteria"]) == {d.value for d in Department}


@pytest.mark.parametrize(
    "client",
    [
        FakeOllama(error=ollama.ResponseError("model not found")),
        FakeOllama(error=ConnectionError("refused")),
        FakeOllama(SimpleNamespace(choice="ceo@example.com", confidence=0.9)),
        FakeOllama(SimpleNamespace(choice="it@example.com", confidence=None)),
    ],
    ids=["ollama-error", "connection-error", "unknown-department", "missing-confidence"],
)
async def test_classify_wraps_every_failure(client):
    with pytest.raises(ModelError):
        await OllamaDecisionModel(client, "d3:2b").classify("hello")
