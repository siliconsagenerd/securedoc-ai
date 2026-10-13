# SecureDoc AI — developer commands
#
# Quick reference:  make help

.DEFAULT_GOAL := help
PY  := backend/.venv/bin/python
PIP := backend/.venv/bin/pip

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

backend-install: ## Create the venv and install backend deps + spaCy model
	python3.12 -m venv backend/.venv
	$(PIP) install -r backend/requirements.txt
	$(PY) -m spacy download en_core_web_lg

backend-dev: ## Run the API locally with reload
	cd backend && ./.venv/bin/uvicorn app.main:app --reload --port 8000

backend-test: ## Run the backend test suite
	cd backend && ./.venv/bin/python -m pytest -v

frontend-install: ## Install frontend dependencies
	cd frontend && npm install

frontend-dev: ## Run the dashboard locally
	cd frontend && npm run dev

frontend-build: ## Type-check and build the dashboard
	cd frontend && npm run build

java-test: ## Run the Java validator tests
	cd java-validator && mvn -q test

docker-build: ## Build all images
	docker compose build

up: ## Start the full stack
	docker compose up --build

down: ## Stop the stack
	docker compose down

logs: ## Tail stack logs
	docker compose logs -f

audit: ## Print the audit log from the running backend container
	docker compose exec backend sh -c 'test -f /app/data/audit.log && cat /app/data/audit.log || echo "no audit log yet — process a document first"'

smoke: ## Run the API smoke test (inside the running stack; falls back to a local backend)
	@if docker compose exec -T backend true 2>/dev/null; then \
		docker compose exec -T backend python /app/scripts/smoke.py; \
	else \
		BASE_URL=$${BASE_URL:-http://127.0.0.1:8000} $(PY) backend/scripts/smoke.py; \
	fi

eval-guard: ## Run the offline prompt-injection guard evaluation
	$(PY) backend/evals/run.py

test: backend-test frontend-build java-test ## Run every test suite

verify-all: ## Run all checks (adds bundle-secret + Docker runtime when available)
	./scripts/verify-all.sh

.PHONY: help backend-install backend-dev backend-test frontend-install \
	frontend-dev frontend-build java-test docker-build up down logs audit smoke eval-guard test verify-all
