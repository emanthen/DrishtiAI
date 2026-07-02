.PHONY: dev build lint typecheck test

dev:
	pnpm dev

build:
	pnpm build

lint:
	pnpm lint

typecheck:
	pnpm typecheck

test:
	pnpm test

build-docker:
	docker build -f Dockerfile -t drishtiai-web:latest ../..
