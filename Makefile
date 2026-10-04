# Satyapan — one-command workflows.
# Uses `uv` by default. Without uv, activate your venv and run e.g. `make check RUN=`
RUN ?= uv run
T ?=

.PHONY: help sync check lint fmt typecheck test task run demo-data schemas status console-test ext-test clean

help:
	@echo "make sync          install core + dev deps (uv)"
	@echo "make check         lint + format check + typecheck + all tests (run before every commit)"
	@echo "make test          all tests (task tests skip until their task is implemented)"
	@echo "make task T=T07    run ONLY task T07's acceptance tests, strict (no skipping)"
	@echo "make run           start the API on http://127.0.0.1:8000 (docs at /docs)"
	@echo "make demo-data     regenerate data/demo fixtures + schemas and validate them"
	@echo "make status        print the task board from docs/STATUS.md"

sync:
	uv sync

lint:
	$(RUN) ruff check .
	$(RUN) ruff format --check .

fmt:
	$(RUN) ruff format .
	$(RUN) ruff check --fix .

typecheck:
	$(RUN) mypy

test:
	$(RUN) pytest

task:
	@if [ -z "$(T)" ]; then echo "Usage: make task T=T07"; exit 2; fi
	$(RUN) pytest --task $(T) -v

check: lint typecheck test
	@echo "make check: ALL GREEN"

run:
	$(RUN) uvicorn satyapan.api.app:app --reload --host 127.0.0.1 --port 8000

demo-data:
	$(RUN) python scripts/make_demo_data.py
	$(RUN) python scripts/export_schemas.py
	$(RUN) python scripts/decision_relevance.py

schemas:
	$(RUN) python scripts/export_schemas.py

status:
	@sed -n '/^| ID/,/^$$/p' docs/STATUS.md

console-test:
	cd console && npm install && npm test

ext-test:
	cd extension && node --test tests/*.test.mjs

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache vault_data
