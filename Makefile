.PHONY: setup live-setup demo verify llm-check seed-datahub api dashboard

setup:
	uv sync --dev --extra mcp
	npm --prefix web ci
	test -f .env || cp .env.example .env

live-setup:
	uv sync --dev
	npm --prefix web ci
	test -f .env || cp .env.example .env

demo:
	uv run rationaleops demo-all --approve-actions --approve-writeback

verify:
	uv run ruff format --check src tests
	uv run ruff check src tests
	uv run pytest -q
	uv build
	npm --prefix web run lint
	npm --prefix web test

llm-check:
	uv run rationaleops llm-check

seed-datahub:
	uv run rationaleops seed-datahub

api:
	uv run rationaleops-api

dashboard:
	npm --prefix web run dev
