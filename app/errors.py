import logging
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.schemas import Problem

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Base for failures we report to the client with a specific HTTP status."""

    status = HTTPStatus.INTERNAL_SERVER_ERROR


class MailDeliveryError(AppError):
    status = HTTPStatus.BAD_GATEWAY


class ModelError(AppError):
    status = HTTPStatus.SERVICE_UNAVAILABLE


def problem_response(request: Request, status: HTTPStatus, detail: str) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    body = Problem(title=status.phrase, status=status, detail=detail, request_id=request_id)
    return JSONResponse(
        body.model_dump(),
        status_code=status,
        media_type="application/problem+json",
        headers={"X-Request-ID": request_id},
    )


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error(request: Request, exc: AppError) -> JSONResponse:
        logger.error("%s: %s", type(exc).__name__, exc)
        return problem_response(request, exc.status, str(exc))

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        detail = "; ".join(
            f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
            for error in exc.errors()
        )
        return problem_response(request, HTTPStatus.UNPROCESSABLE_ENTITY, detail)

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error", exc_info=exc)
        return problem_response(
            request,
            HTTPStatus.INTERNAL_SERVER_ERROR,
            "Unexpected server error. Quote the request_id when reporting it.",
        )
