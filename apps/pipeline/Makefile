.PHONY: dev test lint build

dev:
	uv run python -m drishtiai_pipeline.main

test:
	uv run pytest tests/ -v

lint:
	uv run ruff check src/

build:
	docker build -f Dockerfile -t drishtiai-pipeline:latest ../..
