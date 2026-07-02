.PHONY: dev test lint typecheck build

dev:
	uv run uvicorn drishtiai_api.main:app --reload --host 0.0.0.0 --port 8000

test:
	uv run pytest tests/ -v

lint:
	uv run ruff check src/

typecheck:
	uv run mypy src/

build:
	docker build -f Dockerfile -t drishtiai-api:latest ../..
