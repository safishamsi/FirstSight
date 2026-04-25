PYTHON_VERSION ?= 3.13
VENV ?= .venv
PYTHON := $(VENV)/bin/python
UVICORN := $(VENV)/bin/uvicorn

.PHONY: help setup ensure-env dev test example smoke-stream clean

help:
	@echo "Targets:"
	@echo "  make setup    Create the virtualenv, install deps, and seed .env"
	@echo "  make dev      Run the FastAPI app with reload"
	@echo "  make test     Run pytest"
	@echo "  make example  Run the Vision Agents starter example"
	@echo "  make smoke-stream  Run the mock streaming client against a local backend"
	@echo "  make clean    Remove virtualenv and Python caches"

setup:
	uv venv --python $(PYTHON_VERSION) $(VENV)
	uv pip install --python $(PYTHON) -e ".[dev]"
	@test -f .env || cp .env.example .env

dev: ensure-env
	@HOST=`$(PYTHON) -c 'from app.config import get_settings; print(get_settings().app_host)'`; \
	PORT=`$(PYTHON) -c 'from app.config import get_settings; print(get_settings().app_port)'`; \
	$(UVICORN) app.main:app --reload --host "$$HOST" --port "$$PORT"

test: ensure-env
	$(PYTHON) -m pytest tests

example: ensure-env
	$(PYTHON) -m app.examples.basic_video_agent

smoke-stream: ensure-env
	$(PYTHON) -m app.examples.mock_stream_client

ensure-env:
	@test -x $(PYTHON) || (echo "Missing $(VENV). Run 'make setup' first." && exit 1)

clean:
	rm -rf $(VENV) .pytest_cache app/__pycache__ app/examples/__pycache__ app/processors/__pycache__ tests/__pycache__
