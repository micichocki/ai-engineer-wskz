# Two variants of the router share one image; ROUTER_MODE selects the variant.
.PHONY: agent decision bench-agent bench-decision chart test down

agent: ## LLM agent picks the department and calls send_email (the task as specified)
	ROUTER_MODE=agent docker compose up -d --build

decision: ## decision model picks the department, code makes the same call (no LLM)
	ROUTER_MODE=decision docker compose up -d --build

bench-agent: agent
	uv run python batch.py agent

bench-decision: decision
	uv run python batch.py decision

chart: ## bench/results/*.json -> bench/results.png
	uv run --with matplotlib python bench/chart.py

test:
	uv run ruff check . && uv run pytest

down:
	docker compose down
