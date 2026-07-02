.PHONY: dev test lint build

dev:
	uv run celery -A drishtiai_worker.celery_app worker --loglevel=debug --concurrency=2

test:
	uv run pytest tests/ -v

lint:
	uv run ruff check src/

build:
	docker build -f Dockerfile -t drishtiai-worker:latest ../..
