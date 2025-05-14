# SurfSense Project Makefile
# A comprehensive build and development system for SurfSense components

###################################=> Common Settings <=#############################################
# Define the default goal
.DEFAULT_GOAL := help

# ========================== Capture Environment ===============================
SHELL := /bin/bash
ROOT_DIR := $(shell pwd)

# ==============================================================================
# Output directories
OUTPUT_DIR := $(ROOT_DIR)/_output
$(shell mkdir -p $(OUTPUT_DIR))

BIN_DIR := $(OUTPUT_DIR)/bin
$(shell mkdir -p $(BIN_DIR))

# ==============================================================================
# Git and version information
VERSION ?= $(shell git describe --tags --always --match="v*" --dirty | sed 's/-/./g' 2>/dev/null || echo "v0.0.6-dev")

# Check if the tree is dirty
GIT_TREE_STATE := "dirty"
ifeq (, $(shell git status --porcelain 2>/dev/null))
	GIT_TREE_STATE = "clean"
endif
GIT_COMMIT := $(shell git rev-parse HEAD 2>/dev/null || echo "unknown")

# ==============================================================================
# Docker images 
BACKEND_IMG ?= surfsense/backend:$(VERSION)
WEB_IMG ?= surfsense/web:$(VERSION)
EXTENSION_IMG ?= surfsense/extension:$(VERSION)

# ==============================================================================
# Python settings
PYTHON := python3
PIP := pip3
VENV_DIR := $(BACKEND_DIR)/.venv

# ==============================================================================
# Component directories
BACKEND_DIR := $(ROOT_DIR)/surfsense_backend
WEB_DIR := $(ROOT_DIR)/surfsense_web
EXTENSION_DIR := $(ROOT_DIR)/surfsense_browser_extension

# ==============================================================================
# Build modes
MODE ?= dev

# ==============================================================================
# Build targets
## all: Build all components
.PHONY: all
all: backend-build web-build extension-build

## dev: Start development environment
.PHONY: dev
dev:
	@echo "===========> Starting development environment"
	@docker compose up -d

###################################=> Backend Commands <=#############################################
## backend-venv: Create Python virtual environment for backend
.PHONY: backend-venv
backend-venv:
	@echo "===========> Creating backend virtual environment"
	@$(PYTHON) -m venv $(VENV_DIR)
	@echo "===========> Installing uv in virtual environment"
	@. $(VENV_DIR)/bin/activate && $(PIP) install --upgrade pip uv
	@echo "===========> Virtual environment created at $(VENV_DIR)"
	@echo "===========> Activate with: source $(VENV_DIR)/bin/activate"

## backend: Run backend in development mode
.PHONY: backend
backend: backend-venv backend-install
	@echo "===========> Running backend in development mode"
	@cd $(BACKEND_DIR) && source .venv/bin/activate && python main.py

## backend-install: Install backend dependencies
.PHONY: backend-install
backend-install: backend-venv
	@echo "===========> Installing backend dependencies"
	@cd $(BACKEND_DIR) && source .venv/bin/activate && uv pip sync

## backend-build: Build backend
.PHONY: backend-build
backend-build: backend-install
	@echo "===========> Building backend"
	@cd $(BACKEND_DIR) && source .venv/bin/activate && python -m build

## backend-test: Run backend tests
.PHONY: backend-test
backend-test: backend-install
	@echo "===========> Running backend tests"
	@cd $(BACKEND_DIR) && source .venv/bin/activate && pytest

## backend-lint: Run backend linters
.PHONY: backend-lint
backend-lint: backend-install
	@echo "===========> Running backend linters"
	@cd $(BACKEND_DIR) && source .venv/bin/activate && ruff check .

## backend-format: Format backend code
.PHONY: backend-format
backend-format: backend-install
	@echo "===========> Formatting backend code"
	@cd $(BACKEND_DIR) && source .venv/bin/activate && ruff format .

## backend-run: Run backend locally
.PHONY: backend-run
backend-run: backend-install
	@echo "===========> Running backend"
	@echo "===========> Starting backend server with auto-reload"
	@cd $(BACKEND_DIR) && source .venv/bin/activate && uvicorn main:app --host 0.0.0.0 --port 8000 --reload

## backend-migration: Create a new database migration
.PHONY: backend-migration
backend-migration:
	@echo "===========> Creating new database migration"
	@read -p "Migration name: " name; \
	cd $(BACKEND_DIR) && source .venv/bin/activate && alembic revision --autogenerate -m "$$name"

## backend-migrate: Run database migrations
.PHONY: backend-migrate
backend-migrate:
	@echo "===========> Running database migrations"
	@cd $(BACKEND_DIR) && source .venv/bin/activate && alembic upgrade head

## backend-downgrade: Downgrade database to previous migration
.PHONY: backend-downgrade
backend-downgrade:
	@echo "===========> Downgrading database to previous migration"
	@cd $(BACKEND_DIR) && source .venv/bin/activate && alembic downgrade -1

###################################=> Web Commands <=#############################################
## web: Run web app in development mode
.PHONY: web
web:
	@echo "===========> Running web app in development mode"
	@cd $(WEB_DIR) && npm run dev

## web-install: Install web dependencies
.PHONY: web-install
web-install:
	@echo "===========> Installing web dependencies"
	@cd $(WEB_DIR) && npm install

## web-build: Build web app
.PHONY: web-build
web-build: web-install
	@echo "===========> Building web app"
	@cd $(WEB_DIR) && npm run build

## web-lint: Run web linters
.PHONY: web-lint
web-lint: web-install
	@echo "===========> Running web linters"
	@cd $(WEB_DIR) && npm run lint

## web-start: Start web production server
.PHONY: web-start
web-start: web-build
	@echo "===========> Starting web production server"
	@cd $(WEB_DIR) && npm run start

###################################=> Extension Commands <=#############################################
## extension: Run browser extension in development mode
.PHONY: extension
extension:
	@echo "===========> Running browser extension in development mode"
	@cd $(EXTENSION_DIR) && npm run dev

## extension-install: Install extension dependencies
.PHONY: extension-install
extension-install:
	@echo "===========> Installing extension dependencies"
	@cd $(EXTENSION_DIR) && npm install

## extension-build: Build browser extension
.PHONY: extension-build
extension-build: extension-install
	@echo "===========> Building browser extension"
	@cd $(EXTENSION_DIR) && npm run build

## extension-package: Package browser extension for distribution
.PHONY: extension-package
extension-package: extension-build
	@echo "===========> Packaging browser extension for distribution"
	@cd $(EXTENSION_DIR) && npm run package

###################################=> Docker Commands <=#############################################
## docker-build: Build all Docker images
.PHONY: docker-build
docker-build: docker-build-backend docker-build-web

## docker-build-backend: Build backend Docker image
.PHONY: docker-build-backend
docker-build-backend:
	@echo "===========> Building backend Docker image: $(BACKEND_IMG)"
	@docker build -t $(BACKEND_IMG) -f $(BACKEND_DIR)/Dockerfile $(BACKEND_DIR)

## docker-build-web: Build web Docker image
.PHONY: docker-build-web
docker-build-web:
	@echo "===========> Building web Docker image: $(WEB_IMG)"
	@docker build -t $(WEB_IMG) -f $(WEB_DIR)/Dockerfile $(WEB_DIR)

## docker-push: Push all Docker images
.PHONY: docker-push
docker-push: docker-build
	@echo "===========> Pushing Docker images"
	@docker push $(BACKEND_IMG)
	@docker push $(WEB_IMG)

###################################=> Composite Commands <=#############################################
## test-all: Run tests for all components
.PHONY: test-all
test-all: backend-test web-lint extension-build
	@echo "===========> All tests completed"

## update: Update all dependencies
.PHONY: update
update:
	@echo "===========> Updating backend dependencies"
	@cd $(BACKEND_DIR) && source .venv/bin/activate && uv pip compile -o requirements.txt pyproject.toml
	@echo "===========> Updating web dependencies"
	@cd $(WEB_DIR) && npm update
	@echo "===========> Updating extension dependencies"
	@cd $(EXTENSION_DIR) && npm update

## start-prod: Start all components in production mode
.PHONY: start-prod
start-prod: MODE=prod
start-prod: docker-build
	@echo "===========> Starting production environment"
	@MODE=prod docker compose up -d

## deploy: Full deployment workflow
.PHONY: deploy
deploy: test-all docker-build docker-push
	@echo "===========> Deploying SurfSense"
	@echo "Build complete. Docker images ready for deployment:"
	@echo "  Backend: $(BACKEND_IMG)"
	@echo "  Web: $(WEB_IMG)"
	@echo "  Extension: $(EXTENSION_IMG)"
	@echo "Use 'make start-prod' to start the production environment locally"

###################################=> Utility Commands <=#############################################
## clean: Clean build artifacts
.PHONY: clean
clean:
	@echo "===========> Cleaning build artifacts"
	@rm -rf $(OUTPUT_DIR)
	@cd $(WEB_DIR) && npm run clean || true
	@find $(BACKEND_DIR) -name "*.pyc" -delete
	@find $(BACKEND_DIR) -name "__pycache__" -delete
	@find $(BACKEND_DIR) -name ".pytest_cache" -delete
	@find $(BACKEND_DIR) -name ".coverage" -delete

## format: Format code in all components
.PHONY: format
format: backend-format
	@echo "===========> Formatting web code"
	@cd $(WEB_DIR) && npm run lint -- --fix || true
	@echo "===========> Formatting extension code"
	@cd $(EXTENSION_DIR) && npx prettier --write . || true

## lint: Run linters on all components
.PHONY: lint
lint: backend-lint web-lint

## setup-env: Set up environment files from examples
.PHONY: setup-env
setup-env:
	@echo "===========> Setting up environment files"
	@if [ ! -f ".env" ]; then cp .env.example .env || true; fi
	@if [ ! -f "$(BACKEND_DIR)/.env" ]; then cp $(BACKEND_DIR)/.env.example $(BACKEND_DIR)/.env || true; fi
	@if [ ! -f "$(WEB_DIR)/.env" ]; then cp $(WEB_DIR)/.env.example $(WEB_DIR)/.env || true; fi
	@if [ ! -f "$(EXTENSION_DIR)/.env" ]; then cp $(EXTENSION_DIR)/.env.example $(EXTENSION_DIR)/.env || true; fi

## db-shell: Connect to database with psql
.PHONY: db-shell
db-shell:
	@echo "===========> Connecting to database"
	@docker compose exec db psql -U postgres -d surfsense

## help: Show this help
.PHONY: help
help: Makefile
	@printf "\n\033[1mSurfSense Project Makefile\033[0m\n"
	@printf "\n\033[1mUsage: make <TARGETS> ...\033[0m\n\n\033[1mTargets:\033[0m\n\n"
	@sed -n 's/^##//p' $< | awk -F':' '{printf "\033[36m%-28s\033[0m %s\n", $$1, $$2}' | sed -e 's/^/ /'

## init: Initialize project (create virtual env, install dependencies, setup env files)
.PHONY: init
init: backend-venv setup-env backend-install web-install extension-install
	@echo "===========> Project initialized"

# ==============================================================================
# Database settings
DB_NAME ?= surfsense
DB_USER ?= postgres
DB_HOST ?= localhost
DB_PORT ?= 5432
BACKUP_DIR := $(OUTPUT_DIR)/backups
$(shell mkdir -p $(BACKUP_DIR))

###################################=> Database Commands <=#############################################
## db-backup: Backup the database
.PHONY: db-backup
db-backup:
	@echo "===========> Backing up database"
	@TIMESTAMP=$$(date +%Y%m%d_%H%M%S); \
	BACKUP_FILE=$(BACKUP_DIR)/$(DB_NAME)_$$TIMESTAMP.sql; \
	echo "Backing up to $$BACKUP_FILE"; \
	docker compose exec -T db pg_dump -U $(DB_USER) $(DB_NAME) > $$BACKUP_FILE; \
	echo "Backup completed to $$BACKUP_FILE"

## db-restore: Restore database from backup
.PHONY: db-restore
db-restore:
	@echo "===========> Restoring database"
	@if [ -z "$(BACKUP_FILE)" ]; then \
		echo "Error: BACKUP_FILE is required"; \
		echo "Usage: make db-restore BACKUP_FILE=<path-to-backup-file>"; \
		exit 1; \
	fi; \
	echo "Restoring from $(BACKUP_FILE)"; \
	docker compose exec -T db psql -U $(DB_USER) -d $(DB_NAME) < $(BACKUP_FILE); \
	echo "Restore completed"

## db-list-backups: List available backups
.PHONY: db-list-backups
db-list-backups:
	@echo "===========> Available database backups:"
	@ls -lh $(BACKUP_DIR)

###################################=> Monitoring Commands <=#############################################
## logs: Show logs for all services
.PHONY: logs
logs:
	@echo "===========> Showing logs for all services"
	@docker compose logs -f

## logs-backend: Show logs for backend service
.PHONY: logs-backend
logs-backend:
	@echo "===========> Showing logs for backend service"
	@docker compose logs -f backend

## logs-web: Show logs for web service
.PHONY: logs-web
logs-web:
	@echo "===========> Showing logs for web service"
	@docker compose logs -f web

## status: Show status of all services
.PHONY: status
status:
	@echo "===========> Showing status of all services"
	@docker compose ps

## health: Check health of all services
.PHONY: health
health:
	@echo "===========> Checking health of all services"
	@echo "Database:"
	@docker compose exec db pg_isready -U $(DB_USER) -d $(DB_NAME) || echo "Database is not ready"
	@echo "\nBackend API:"
	@curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health || echo "Backend API is not responding"
	@echo "\nWeb Application:"
	@curl -s -o /dev/null -w "%{http_code}" http://localhost:3000 || echo "Web application is not responding" 