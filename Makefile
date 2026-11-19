# Two variants of the router share one image; ROUTER_MODE selects the variant.
.PHONY: agent decision bench-agent bench-decision test down

agent:
	ROUTER_MODE=agent docker compose up -d --build

decision:
	ROUTER_MODE=decision docker compose up -d --build

bench-agent: agent
	uv run python batch.py agent

bench-decision: decision
	uv run python batch.py decision

test:
	uv run ruff check . && uv run pytest

down:
	docker compose down
