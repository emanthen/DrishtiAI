.PHONY: dev test lint typecheck build migrate

dev:
	uv run python manage.py runserver 0.0.0.0:8001

migrate:
	uv run python manage.py migrate

makemigrations:
	uv run python manage.py makemigrations

test:
	uv run pytest tests/ -v

lint:
	uv run ruff check drishtiai_admin/

typecheck:
	uv run mypy drishtiai_admin/

build:
	docker build -f Dockerfile -t drishtiai-admin:latest ../..
