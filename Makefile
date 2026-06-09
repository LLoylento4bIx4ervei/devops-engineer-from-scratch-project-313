.PHONY: run test lint format
run:
	uv run uvicorn main:app --host 0.0.0.0 --port 8080

test:
	uv run pytest -v

lint:
	uv run ruff check .

lint-fix:
	uv run ruff check --fix .

format:
	uv run ruff format .
