import asyncio

from fastapi import APIRouter, Request, Response

from app import mailer
from app.errors import MailDeliveryError, ModelError
from app.schemas import HealthResponse, MessageRequest, Problem, RoutingResponse

router = APIRouter(prefix="/api/v1")

_ERRORS = {
    422: "Invalid input.",
    MailDeliveryError.status: MailDeliveryError.detail,
    ModelError.status: ModelError.detail,
}


@router.post(
    "/messages",
    summary="Route a message to a department",
    response_model=RoutingResponse,
    responses={
        code: {"model": Problem, "description": text, "content": {"application/problem+json": {}}}
        for code, text in _ERRORS.items()
    },
)
async def route_message(body: MessageRequest, request: Request) -> RoutingResponse:
    """The agent picks the department and forwards the message by e-mail."""
    state = await request.app.state.graph.ainvoke({"email": body.email, "message": body.message})
    return RoutingResponse(
        recipient=state["sent_to"],
        decided_by=state["decided_by"],
        confidence=state.get("confidence"),
    )


@router.get(
    "/health",
    summary="Dependency health",
    response_model=HealthResponse,
    responses={503: {"model": HealthResponse, "description": "A dependency is failing."}},
)
async def health(request: Request, response: Response) -> HealthResponse:
    state = request.app.state
    settings = state.settings

    async def models() -> None:
        available = {model.model for model in (await state.ollama.list()).models}
        # Ollama lists an untagged name as name:latest.
        name = settings.model
        if (name if ":" in name.rpartition("/")[2] else f"{name}:latest") not in available:
            raise RuntimeError(f"model not pulled: {name}")

    def smtp() -> None:
        with mailer.connect(settings) as connection:
            connection.noop()

    async def check(probe) -> str:
        try:
            await probe
        except Exception as exc:  # health must report, never raise
            return f"error: {exc}"
        return "ok"

    ollama_status, smtp_status = await asyncio.gather(
        check(models()), check(asyncio.to_thread(smtp))
    )
    components = {"ollama": ollama_status, "smtp": smtp_status}
    healthy = all(status == "ok" for status in components.values())
    if not healthy:
        response.status_code = 503
    return HealthResponse(status="ok" if healthy else "degraded", components=components)
