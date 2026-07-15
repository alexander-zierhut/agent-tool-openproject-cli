.PHONY: help install up wait token seed env test test-unit down clean

BASE_URL ?= http://localhost:8090
ENV_FILE ?= .env

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install: ## Create venv and install the CLI (editable, with test deps)
	python3 -m venv .venv
	. .venv/bin/activate && pip install -q -e '.[test]'

up: ## Start the local OpenProject via docker compose
	docker compose up -d

wait: ## Wait until OpenProject answers on the API
	@echo "waiting for OpenProject at $(BASE_URL) ..."
	@until curl -sf -u apikey:x $(BASE_URL)/api/v3/configuration -o /dev/null 2>/dev/null || \
	       curl -sf $(BASE_URL)/health_checks/default -o /dev/null 2>/dev/null; do sleep 5; done
	@echo "OpenProject is up."

token: ## Mint the admin API token (prints APITOKEN=...)
	@./scripts/get_admin_token.sh

seed: ## Seed test data (modules, custom fields, 2nd user)
	@./scripts/seed_test_data.sh

env: wait ## Write a .env with base URL + freshly minted admin & 2nd-user tokens
	@TOKEN=$$(./scripts/get_admin_token.sh | grep '^APITOKEN=' | cut -d= -f2); \
	  JANE=$$(./scripts/get_admin_token.sh jane.doe 2>/dev/null | grep '^APITOKEN=' | cut -d= -f2 || true); \
	  printf 'export OPCLI_BASE_URL=%s\nexport OPCLI_TOKEN=%s\n' "$(BASE_URL)" "$$TOKEN" > $(ENV_FILE); \
	  [ -n "$$JANE" ] && printf 'export OPCLI_SECOND_TOKEN=%s\n' "$$JANE" >> $(ENV_FILE); \
	  echo "wrote $(ENV_FILE)"

test: ## Run the full suite (needs .env / OPCLI_* set)
	. .venv/bin/activate && [ -f $(ENV_FILE) ] && . $(ENV_FILE); \
	  OPCLI_BASE_URL=$${OPCLI_BASE_URL:-$(BASE_URL)} python -m pytest

test-unit: ## Run only the pure-unit tests (no live instance)
	. .venv/bin/activate && python -m pytest tests/test_unit.py

down: ## Stop the local OpenProject (keep volumes)
	docker compose down

clean: ## Stop and delete volumes (full reset)
	docker compose down -v
