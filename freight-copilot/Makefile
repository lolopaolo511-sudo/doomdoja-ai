# Freight Copilot — local-first developer task runner.
# `make demo` is the one-command start: venv + deps + seed + run → http://127.0.0.1:8000

PY ?= python3
VENV := backend/.venv
BIN := $(VENV)/bin
HOST ?= 127.0.0.1
PORT ?= 8000

.PHONY: help demo venv install seed run test lint clean

help:
	@echo "Targets: demo (one-command start), venv, install, seed, run, test, lint, clean"

$(VENV):
	$(PY) -m venv $(VENV)

venv: $(VENV)

install: venv
	$(BIN)/pip install --quiet --upgrade pip
	$(BIN)/pip install --quiet -r backend/requirements.txt

seed: install
	cd backend && ../$(BIN)/python -m app.seed

run: install
	cd backend && ../$(BIN)/uvicorn app.main:app --host $(HOST) --port $(PORT)

# One command: install, seed demo data, then serve.
demo: install seed
	@echo "Freight Copilot running at http://$(HOST):$(PORT)  (Ctrl-C to stop)"
	cd backend && ../$(BIN)/uvicorn app.main:app --host $(HOST) --port $(PORT)

test: install
	cd backend && ../$(BIN)/python -m pytest -q

lint: install
	cd backend && ../$(BIN)/ruff check app tests

clean:
	rm -rf $(VENV) backend/freight_copilot.db backend/app/__pycache__ \
	  backend/**/__pycache__ backend/.pytest_cache
