from dataclasses import dataclass
from typing import Protocol

import httpx
import ollama
from pydantic import ValidationError

from app.departments import DESCRIPTIONS, Department
from app.errors import ModelError

_QUESTION = "department"
_INSTRUCTIONS = (
    "An employee sent this message to the company. Which department mailbox should handle it?"
)


@dataclass(frozen=True)
class Decision:
    department: Department
    confidence: float


class DecisionModel(Protocol):
    async def classify(self, message: str) -> Decision: ...


class OllamaDecisionModel:
    """System-one decision model (e.g. d3) served by Ollama at /v1/systemone."""

    def __init__(self, client: ollama.AsyncClient, model: str) -> None:
        self._client = client
        self._model = model

    async def classify(self, message: str) -> Decision:
        try:
            response = await self._client.systemone(
                model=self._model,
                state=message,
                questions={
                    _QUESTION: {
                        "type": "choice",
                        "instructions": _INSTRUCTIONS,
                        "criteria": {d.value: text for d, text in DESCRIPTIONS.items()},
                    }
                },
            )
            answer = response.answers[_QUESTION]
            return Decision(Department(answer.choice), float(answer.confidence))
        except (
            ollama.ResponseError,
            httpx.HTTPError,
            ConnectionError,
            ValidationError,
            KeyError,
            AttributeError,
            TypeError,
            ValueError,
        ) as exc:
            raise ModelError(f"Decision model {self._model!r} failed: {exc}") from exc
