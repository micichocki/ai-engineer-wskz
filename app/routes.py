import asyncio
import smtplib

from fastapi import APIRouter, Request, Response

from app.schemas import HealthResponse, MessageRequest, Problem, RoutingResponse

router = APIRouter(prefix="/api/v1")

_ERRORS = {
    422: "Invalid input.",
    502: "The mail server did not accept the e-mail.",
    503: "A model is unavailable or gave no usable answer; nothing was sent.",
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
        suggested_department=state["suggestion"],
        confidence=state["confidence"],
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
        missing = {settings.agent_model, settings.decision_model} - available
        if missing:
            raise RuntimeError(f"models not pulled: {', '.join(sorted(missing))}")

    def smtp() -> None:
        with smtplib.SMTP(
            settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout_seconds
        ) as connection:
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
