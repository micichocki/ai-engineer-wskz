from typing import Annotated, Literal

from pydantic import BaseModel, EmailStr, Field, StringConstraints, field_validator

from app.departments import Department


class MessageRequest(BaseModel):
    email: EmailStr = Field(description="Sender address; used as Reply-To of the forwarded e-mail.")
    message: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)
    ] = Field(description="Free-text message to route.")

    @field_validator("email")
    @classmethod
    def _ascii_only(cls, value: str) -> str:
        # shortcut: the mailer sends plain ASCII headers, so SMTPUTF8/IDN addresses are
        # rejected; switch to an SMTPUTF8 session if such senders must be supported.
        if not value.isascii():
            raise ValueError("non-ASCII e-mail addresses are not supported")
        return value

    model_config = {
        "json_schema_extra": {
            "examples": [{"email": "jan.nowak@example.com", "message": "Nie działa mi komputer"}]
        }
    }


class RoutingResponse(BaseModel):
    recipient: Department = Field(description="Department mailbox the e-mail was sent to.")
    decided_by: Literal["decision_model", "agent"] = Field(
        description=(
            "'decision_model' when the agent followed a confident suggestion, "
            "'agent' when it chose the department itself."
        )
    )
    suggested_department: Department = Field(description="Decision model's suggestion.")
    confidence: float = Field(description="Decision model's confidence in its suggestion.")


class Problem(BaseModel):
    """Error body (RFC 9457 problem details)."""

    type: str = "about:blank"
    title: str
    status: int
    detail: str
    request_id: str


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    components: dict[str, str] = Field(description="'ok' or the error, per dependency.")
