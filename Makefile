# SecureDoc AI — developer commands
#
# Quick reference:  make help

.DEFAULT_GOAL := help
PY  := backend/.venv/bin/python
PIP := backend/.venv/bin/pip

# Bounded health wait (seconds) used by `make smoke`.
HEALTH_TIMEOUT := 60

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

smoke: ## Run the API smoke test (waits for backend + validator health first)
	@echo "Ensuring the stack is running..."
	@docker compose up -d >/dev/null 2>&1 || { echo "ERROR: could not start the Compose stack"; exit 1; }
	@echo "Waiting for backend health (up to $(HEALTH_TIMEOUT)s)..."
	@i=0; until docker compose exec -T backend python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')" >/dev/null 2>&1; do \
		i=$$((i+1)); [ $$i -ge $(HEALTH_TIMEOUT) ] && { echo "ERROR: backend not healthy after $(HEALTH_TIMEOUT)s"; exit 1; }; sleep 1; \
	done; echo "  backend healthy"
	@echo "Waiting for Java validator health (up to $(HEALTH_TIMEOUT)s)..."
	@i=0; until docker compose exec -T java-validator wget -q -O - http://127.0.0.1:8080/health >/dev/null 2>&1; do \
		i=$$((i+1)); [ $$i -ge $(HEALTH_TIMEOUT) ] && { echo "ERROR: java-validator not healthy after $(HEALTH_TIMEOUT)s"; exit 1; }; sleep 1; \
	done; echo "  java-validator healthy"
	@docker compose exec -T backend python /app/scripts/smoke.py

eval-guard: ## Run the offline prompt-injection guard evaluation
	$(PY) backend/evals/run.py

test: backend-test frontend-build java-test ## Run every test suite

verify-all: ## Run all checks (adds bundle-secret + Docker runtime when available)
	./scripts/verify-all.sh

.PHONY: help backend-install backend-dev backend-test frontend-install \
	frontend-dev frontend-build java-test docker-build up down logs audit smoke eval-guard test verify-all
