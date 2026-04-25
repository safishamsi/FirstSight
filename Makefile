BACKEND_DIR := backend

.PHONY: help backend-setup backend-dev backend-test backend-example backend-clean

help:
	@echo "Targets:"
	@echo "  make backend-setup   Create the backend venv, install deps, and seed .env"
	@echo "  make backend-dev     Run the FastAPI backend locally"
	@echo "  make backend-test    Run backend tests"
	@echo "  make backend-example Run the Vision Agents starter example"
	@echo "  make backend-clean   Remove backend virtualenv and caches"

backend-setup:
	@$(MAKE) -C $(BACKEND_DIR) setup

backend-dev:
	@$(MAKE) -C $(BACKEND_DIR) dev

backend-test:
	@$(MAKE) -C $(BACKEND_DIR) test

backend-example:
	@$(MAKE) -C $(BACKEND_DIR) example

backend-clean:
	@$(MAKE) -C $(BACKEND_DIR) clean

