.PHONY: dev test lint build clean install help migrate seed seed-dev generate-test-video benchmark generate-plate-crops benchmark-nepali collect-corrections train-nepali-ocr

COMPOSE := docker compose -f deploy/compose/docker-compose.yml

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install all dependencies (Python + Node)
	uv sync --all-packages
	pnpm install

dev: ## Start full stack in development mode
	$(COMPOSE) up --build

dev-infra: ## Start only infrastructure services (postgres, redis, minio)
	$(COMPOSE) up postgres redis minio

dev-api: ## Start API service only (requires dev-infra)
	$(COMPOSE) up api

dev-web: ## Start web app only
	$(COMPOSE) up web

stop: ## Stop all services
	$(COMPOSE) down

clean: ## Stop and remove volumes (destructive)
	$(COMPOSE) down -v --remove-orphans

lint: ## Run all linters
	uv run ruff check .
	uv run mypy apps packages
	pnpm --recursive lint

format: ## Auto-format all code
	uv run ruff format .
	pnpm format

typecheck: ## Run all type checkers
	uv run mypy apps packages
	pnpm --recursive typecheck

test: ## Run all tests
	uv run pytest
	pnpm --recursive test

test-python: ## Run Python tests only
	uv run pytest

test-js: ## Run JavaScript/TypeScript tests only
	pnpm --recursive test

build: ## Build all Docker images
	$(COMPOSE) build

logs: ## Tail logs for all services
	$(COMPOSE) logs -f

health: ## Check health of all running services
	@curl -sf http://localhost:8000/health && echo " api: OK" || echo " api: FAIL"
	@curl -sf http://localhost:8001/health/ && echo " admin: OK" || echo " admin: FAIL"

licenses: ## Generate LICENSES.md (requires pip-licenses and license-checker)
	uv run pip-licenses --format=markdown --output-file=LICENSES.md
	@echo "Python licenses written to LICENSES.md"

keygen: ## Generate RS256 JWT keypair — run once at install, add output to .env
	uv run python apps/api/scripts/generate_jwt_keys.py

security-scan: ## Run local security checks (Bandit SAST + pip-audit + pnpm audit)
	uv run bandit -r apps/api/src apps/pipeline/src apps/worker/src -q
	uv run pip-audit --desc
	pnpm --recursive audit --prod

backup: ## Create a full backup bundle
	$(COMPOSE) exec postgres pg_dump -U drishtiai drishtiai > deploy/backups/postgres_$$(date +%Y%m%d_%H%M%S).sql
	@echo "Backup complete."

migrate: ## Run Alembic migrations against the local Postgres (requires dev-infra running)
	cd packages/shared-python && uv run alembic upgrade head

seed: ## Seed superadmin user (set SUPERADMIN_EMAIL and SUPERADMIN_PASSWORD env vars)
	uv run python apps/api/scripts/seed_superadmin.py

seed-dev: ## Seed dev environment: org + site + superadmin + mediamtx test camera
	uv run python apps/api/scripts/seed_dev_data.py

generate-test-video: ## Generate synthetic Phase 1 test video and ground truth JSON
	uv run python ml/benchmarks/synthetic/generate_test_video.py \
		--output ml/benchmarks/phase1.mp4 \
		--gt ml/benchmarks/phase1_gt.json
	mkdir -p deploy/compose/test-media
	cp ml/benchmarks/phase1.mp4 deploy/compose/test-media/test.mp4
	@echo "Test video ready at deploy/compose/test-media/test.mp4"

benchmark: ## Evaluate Phase 1 recall against running stack (run after 'make dev')
	uv run python ml/benchmarks/eval_phase1.py \
		--gt ml/benchmarks/phase1_gt.json \
		--db postgresql://drishtiai:drishtiai@localhost:5432/drishtiai

benchmark-11: ## Evaluate Phase 11 OCR quality (recall, precision, CER) against running stack
	uv run python ml/benchmarks/eval_phase11.py \
		--gt ml/benchmarks/phase1_gt.json \
		--db postgresql://drishtiai:drishtiai@localhost:5432/drishtiai

generate-plate-crops: ## Generate 500 synthetic Nepali plate crops + ground-truth JSON
	uv run python ml/benchmarks/synthetic/generate_plate_crops.py \
		--out-dir ml/benchmarks/nepali_plates_test/ \
		--gt      ml/benchmarks/nepali_gt.json \
		--count   500

benchmark-nepali: ## Evaluate Nepali OCR accuracy on synthetic plate crops
	uv run python ml/benchmarks/eval_nepali_ocr.py \
		--image-dir ml/benchmarks/nepali_plates_test/ \
		--gt        ml/benchmarks/nepali_gt.json

collect-corrections: ## Download guard-reviewed OCR corrections from the review queue
	uv run python ml/plate-ocr/collect_corrections.py \
		--api-url $${DRISHTIAI_API_URL:-http://localhost:8000} \
		--out-dir ml/plate-ocr/corrections/

train-nepali-ocr: ## Fine-tune PaddleOCR on Nepali plates (requires GPU + ≥500 corrections)
	uv run python ml/plate-ocr/prepare_dataset.py \
		--corrections  ml/plate-ocr/corrections/ \
		--synthetic    ml/benchmarks/nepali_plates_test/ \
		--synthetic-gt ml/benchmarks/nepali_gt.json
	uv run python ml/plate-ocr/fine_tune.py \
		--config ml/plate-ocr/configs/nepali_embossed.yml
