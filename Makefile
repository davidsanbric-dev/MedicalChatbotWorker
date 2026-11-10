.PHONY: help install test check-db run docker-build docker-run

# Load variables from .env (POSTGRES_*, DATABASE_URL, ...)
ifneq (,$(wildcard .env))
include .env
export
endif

help:
	@echo "Available targets:"
	@echo "  install      Install Python dependencies with uv"
	@echo "  test         Run the unit tests (offline, no database needed)"
	@echo "  check-db     Verify the shared Postgres (medical_conditions_api stack)"
	@echo "               is reachable on localhost"
	@echo "  run          Run the worker locally against the shared Postgres"
	@echo "               on localhost (e.g. make run ARGS='--condition acne')"
	@echo "  docker-build Build the worker Docker image"
	@echo "  docker-run   Run the worker in Docker against the host's Postgres"
	@echo "               (e.g. make docker-run ARGS='--condition acne')"

install:
	uv sync

test:
	uv run pytest

# Verify the shared Postgres from the medical_conditions_api stack is
# up and reachable on localhost:$(POSTGRES_PORT).
check-db:
	@uv run python -c "import psycopg2; psycopg2.connect(host='localhost', port=$(POSTGRES_PORT), user='$(POSTGRES_USER)', password='$(POSTGRES_PASSWORD)', dbname='$(POSTGRES_DB)').close()" 2>/dev/null \
		&& echo "Postgres reachable on localhost:$(POSTGRES_PORT)" \
		|| (echo "Postgres is not reachable on localhost:$(POSTGRES_PORT)."; \
		    echo "Start it from medical_conditions_api: make db-up"; exit 1)

# Run locally (outside Docker), against the Postgres exposed on
# localhost:$(POSTGRES_PORT) by the medical_conditions_api stack.
run: check-db
	DATABASE_URL=postgresql://$(POSTGRES_USER):$(POSTGRES_PASSWORD)@localhost:$(POSTGRES_PORT)/$(POSTGRES_DB) \
		uv run python main.py $(ARGS)

docker-build:
	docker compose build

docker-run:
	docker compose run --rm worker uv run python main.py $(ARGS)
