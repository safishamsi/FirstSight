BACKEND_DIR := backend
VIEWER_DIR := viewer

.PHONY: help backend-setup backend-dev backend-stop backend-restart backend-test backend-example backend-smoke-stream backend-clean viewer-install viewer-dev viewer-build

help:
	@echo "Targets:"
	@echo "  make backend-setup   Create the backend venv, install deps, and seed .env"
	@echo "  make backend-dev     Run the FastAPI backend locally"
	@echo "  make backend-stop    Stop the local FastAPI backend"
	@echo "  make backend-restart Stop then run the FastAPI backend locally"
	@echo "  make backend-test    Run backend tests"
	@echo "  make backend-example Run the Vision Agents starter example"
	@echo "  make backend-smoke-stream Run the mock client against a local backend"
	@echo "  make backend-clean   Remove backend virtualenv and caches"
	@echo "  make viewer-install  Install the React debug viewer dependencies"
	@echo "  make viewer-dev      Run the React debug viewer locally"
	@echo "  make viewer-build    Build the React debug viewer"

backend-setup:
	@$(MAKE) -C $(BACKEND_DIR) setup

backend-dev:
	@$(MAKE) -C $(BACKEND_DIR) dev

backend-stop:
	@$(MAKE) -C $(BACKEND_DIR) stop

backend-restart:
	@$(MAKE) -C $(BACKEND_DIR) restart

backend-test:
	@$(MAKE) -C $(BACKEND_DIR) test

backend-example:
	@$(MAKE) -C $(BACKEND_DIR) example

backend-smoke-stream:
	@$(MAKE) -C $(BACKEND_DIR) smoke-stream

backend-clean:
	@$(MAKE) -C $(BACKEND_DIR) clean

viewer-install:
	cd $(VIEWER_DIR) && npm install

viewer-dev:
	cd $(VIEWER_DIR) && npm run dev

viewer-build:
	cd $(VIEWER_DIR) && npm run build
