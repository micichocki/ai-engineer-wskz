import logging
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import ollama
from fastapi import FastAPI, Request
from langchain_ollama import ChatOllama

from app.config import get_settings
from app.decision import OllamaDecisionModel
from app.errors import register_error_handlers
from app.graph import build_graph
from app.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    ollama_client = ollama.AsyncClient(
        host=settings.ollama_base_url, timeout=settings.model_timeout_seconds
    )
    chat_model = ChatOllama(
        model=settings.agent_model,
        base_url=settings.ollama_base_url,
        temperature=0,
        reasoning=False,  # one enum argument needs no thinking; keeps CPU latency low
        client_kwargs={"timeout": settings.model_timeout_seconds},
    )

    app.state.settings = settings
    app.state.ollama = ollama_client
    app.state.graph = build_graph(
        settings, chat_model, OllamaDecisionModel(ollama_client, settings.decision_model)
    )
    try:
        yield
    finally:
        await ollama_client.close()


def create_app() -> FastAPI:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    app = FastAPI(
        title="AI message router",
        description=(
            "Routes a free-text message to the right department: a decision model "
            "classifies it and an LLM agent sends the e-mail through a tool call."
        ),
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/api/v1/docs",
        openapi_url="/api/v1/openapi.json",
        redoc_url=None,
    )

    @app.middleware("http")
    async def request_id(request: Request, call_next):
        request.state.request_id = str(uuid.uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    register_error_handlers(app)
    app.include_router(router)
    return app


app = create_app()
