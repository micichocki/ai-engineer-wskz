import logging
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.schemas import Problem

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Base for failures we report to the client with a specific HTTP status."""

    status = HTTPStatus.INTERNAL_SERVER_ERROR
    detail = "Unexpected server error."


class MailDeliveryError(AppError):
    status = HTTPStatus.BAD_GATEWAY
    detail = "The mail server did not accept the e-mail."


class ModelError(AppError):
    status = HTTPStatus.SERVICE_UNAVAILABLE
    detail = "A model is unavailable or gave no usable answer; nothing was sent."


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


def problem_response(request: Request, status: HTTPStatus, detail: str) -> JSONResponse:
    request_id = _request_id(request)
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
        logger.error("%s: %s request_id=%s", type(exc).__name__, exc, _request_id(request))
        return problem_response(request, exc.status, exc.detail)

    @app.exception_handler(HTTPException)  # 404/405 raised by the router
    async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
        response = problem_response(request, HTTPStatus(exc.status_code), str(exc.detail))
        response.headers.update(exc.headers or {})  # e.g. Allow on 405
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        detail = "; ".join(
            f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
            for error in exc.errors()
        )
        return problem_response(request, HTTPStatus.UNPROCESSABLE_ENTITY, detail)

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error request_id=%s", _request_id(request), exc_info=exc)
        return problem_response(
            request,
            HTTPStatus.INTERNAL_SERVER_ERROR,
            "Unexpected server error. Quote the request_id when reporting it.",
        )
