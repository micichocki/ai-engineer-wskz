# AI message router

Proof of concept: an HTTP API takes a free-text message from an employee, an AI agent decides
which department should handle it and forwards it there by e-mail through a tool call.
Everything runs locally in containers; the models are served by Ollama.

## Run it

Requirements: Docker with Compose v2, about 6 GB of free RAM and 6 GB of disk.

```bash
git clone <repository-url> && cd <repository>
docker compose up -d
```

The first start downloads the model weights (about 4.6 GB), so it takes a few minutes. The
command returns once the models are downloaded and loaded and the API reports healthy, so the
stack accepts requests as soon as you get the prompt back.

| What | Address |
|---|---|
| API | http://localhost:8000/api/v1/messages |
| Swagger / OpenAPI | http://localhost:8000/api/v1/docs |
| Captured e-mails (MailHog) | http://localhost:8025 |
| Health of dependencies | http://localhost:8000/api/v1/health |

Optional settings (models, ports, confidence threshold) are listed in [.env.example](.env.example).
With an NVIDIA GPU and the NVIDIA Container Toolkit:
`docker compose -f docker-compose.yml -f compose.gpu.yaml up -d`.

## Try it

```bash
curl -X POST http://localhost:8000/api/v1/messages \
  -H "Content-Type: application/json" \
  -d '{"email": "jan.nowak@example.com", "message": "Nie działa mi komputer"}'
```

```json
{
  "recipient": "help-desk@example.com",
  "decided_by": "decision_model",
  "suggested_department": "help-desk@example.com",
  "confidence": 0.83
}
```

Open http://localhost:8025: the e-mail is addressed to `help-desk@example.com`, its `Reply-To`
is `jan.nowak@example.com` and its body is the original message. A request takes about 3 seconds
on a laptop CPU.

## How it works

```
client ─► api (FastAPI) ─► LangGraph
                             classify : decision model d3      ─► department + confidence
                             agent    : LLM qwen3 (Ollama)     ─► tool call send_email(to)
                             tools    : send_email             ─► SMTP ─► MailHog
```

| Container | Image | Role |
|---|---|---|
| `api` | built from `python:3.12-slim` | FastAPI app with the agent |
| `ollama` | `ollama/ollama` | serves both models on CPU (or GPU) |
| `ollama-init` | `ollama/ollama` | one-shot job: pulls and loads the models, then exits |
| `ready` | `ollama/ollama` | one-shot gate: makes `up -d` wait until the API is healthy |
| `mailhog` | `mailhog/mailhog` | catches the e-mails, web UI on port 8025 |

## Architecture decisions

**Two models, each doing what it is good at.** A *decision model* (`d3:2b`, a "system one" model)
reads the message and the department descriptions and returns a department with a confidence.
Decision models answer typed questions with probabilities and cannot generate text or tool calls,
so a small tool-calling LLM (`qwen3:1.7b`) acts as the agent: it receives the message and the
suggestion and calls the `send_email` tool. With a confident suggestion (0.8 or higher by default)
it is told to use it; otherwise it is told to decide itself.

**The LLM chooses only the recipient.** The tool takes one argument, restricted to the five
allowed addresses. The body (the original message, unchanged), the subject and the `Reply-To`
header are set by code from the request, so the model cannot alter the text or the sender.

**Model problems are errors, not guesses.** If a model cannot be reached, or the agent answers
without a valid `send_email` call, nothing is sent and the API returns `503`. `other@example.com`
is used only when the models choose it. Only one e-mail is sent per request. The response field
`decided_by` says whether the agent followed a confident suggestion (`decision_model`) or chose
the department itself (`agent`).

**Errors are reported in one format.** Failures return `application/problem+json` with `title`,
`status`, a fixed `detail` and a `request_id` that also appears in the logs (with the real cause)
and the `X-Request-ID` header.

| Status | Meaning |
|---|---|
| 422 | invalid input |
| 502 | the mail server did not accept the e-mail (nothing was sent; retry is safe) |
| 503 | a model is unavailable or gave no usable answer; nothing was sent (retry is safe) |
| 500 | unexpected error; details are only in the logs |

**Department meanings** are defined once, in [app/departments.py](app/departments.py), and used
by both models. `kadry` covers personnel administration (leave, payroll, contracts, certificates);
`human-resources` covers recruitment, training, development and workplace conflicts; `help-desk`
covers things that are broken; `it` covers access, systems and infrastructure requests.

**Readiness.** The API container starts only after the model job has finished and MailHog is
healthy, and the `ready` job holds `docker compose up -d` until the API health check passes. Models stay loaded in memory, so no request pays the model load time.

## Project layout

```
app/
  main.py          application factory, lifespan, request id
  routes.py        POST /api/v1/messages, GET /api/v1/health
  graph.py         LangGraph: classify -> agent -> tools
  decision.py      decision model client (Ollama /v1/systemone)
  mailer.py        builds and sends the e-mail
  departments.py   allowed addresses and their descriptions
  schemas.py       request / response models
  errors.py        domain errors and their HTTP mapping
  config.py        settings from environment variables
tests/             unit tests (no Docker needed) and an end-to-end test
```

## Tests

```bash
uv sync
uv run pytest            # unit tests, models and services are faked
uv run pytest -m e2e     # end-to-end, needs the running stack
uv run ruff check .
```

## Limits of this PoC

- No authentication, rate limiting or deduplication: sending the same request twice sends two e-mails.
- Routing quality was checked on 20 Polish messages (all routed correctly); it is not a benchmark.
- The MailHog image is built for amd64 only; on ARM machines Docker runs it under emulation.
