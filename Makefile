# /!\ /!\ /!\ /!\ /!\ /!\ /!\ DISCLAIMER /!\ /!\ /!\ /!\ /!\ /!\ /!\ /!\
#
# This Makefile is only meant to be used for DEVELOPMENT purpose as we are
# changing the user id that will run in the container.
#
# PLEASE DO NOT USE IT FOR YOUR CI/PRODUCTION/WHATEVER...
#
# /!\ /!\ /!\ /!\ /!\ /!\ /!\ /!\ /!\ /!\ /!\ /!\ /!\ /!\ /!\ /!\ /!\ /!\
#
# Note to developers:
#
# While editing this file, please respect the following statements:
#
# 1. Every variable should be defined in the ad hoc VARIABLES section with a
#    relevant subsection
# 2. Every new rule should be defined in the ad hoc RULES section with a
#    relevant subsection depending on the targeted service
# 3. Rules should be sorted alphabetically within their section
# 4. When a rule has multiple dependencies, you should:
#    - duplicate the rule name to add the help string (if required)
#    - write one dependency per line to increase readability and diffs
# 5. .PHONY rule statement should be written after the corresponding rule
# ==============================================================================
# VARIABLES

BOLD  := \033[1m
RESET := \033[0m
GREEN := \033[1;32m
SHELL := /bin/env bash

# -- Database

DB_HOST            = postgresql
DB_PORT            = 5432

# -- Docker
# Get the current user ID to use for docker run and docker exec commands
ifeq ($(OS),Windows_NT)
DOCKER_USER         := 0:0     # run containers as root on Windows
else
DOCKER_UID          := $(shell id -u)
DOCKER_GID          := $(shell id -g)
DOCKER_USER         := $(DOCKER_UID):$(DOCKER_GID)
endif
COMPOSE             = DOCKER_USER=$(DOCKER_USER) docker compose
COMPOSE_EXEC        = $(COMPOSE) exec
COMPOSE_EXEC_APP    = $(COMPOSE_EXEC) app-dev
COMPOSE_RUN         = $(COMPOSE) run --rm
COMPOSE_RUN_APP     = $(COMPOSE_RUN) app-dev
COMPOSE_RUN_APP_UV  = $(COMPOSE_RUN_APP) uv run

# -- Backend
MANAGE              = $(COMPOSE_RUN_APP_UV) python manage.py

# ==============================================================================
# RULES

default: help

data/static:
	@mkdir -p data/static

# -- Project
#
create-env-local-files: ## create env.local files in env.d/development
create-env-local-files: 
	@touch env.d/development/common.local
	@touch env.d/development/postgresql.local
	@touch env.d/development/kc_postgresql.local
.PHONY: create-env-local-files

pre-bootstrap: \
	data/static \
	create-env-local-files
.PHONY: pre-bootstrap

post-bootstrap: \
	migrate \
	demo \
	back-i18n-compile
.PHONY: post-bootstrap

pre-beautiful-bootstrap: ## Display a welcome message before bootstrap
ifeq ($(OS),Windows_NT)
	@echo ""
	@echo "================================================================================"
	@echo ""
	@echo "  Welcome to Menshen - Token exchange authz server from La Suite!
	@echo ""
	@echo "  This will set up your development environment with:"
	@echo "  - Docker containers for all services"
	@echo "  - Database migrations and static files"
	@echo "  - Environment configuration files"
	@echo ""
	@echo "  Services will be available at:"
	@echo "  - API:      http://localhost:8071"
	@echo "  - Admin:    http://localhost:8071/admin"
	@echo ""
	@echo "================================================================================"
	@echo ""
	@echo "Starting bootstrap process..."
else
	@echo -e "$(BOLD)"
	@echo "╔══════════════════════════════════════════════════════════════════════════════╗"
	@echo "║                                                                              ║"
	@echo "║  🚀 Welcome to Menshen - Token exchange authz server from La Suite! 🚀       ║"
	@echo "║                                                                              ║"
	@echo "║  This will set up your development environment with:                         ║"
	@echo "║  • Docker containers for all services                                        ║"
	@echo "║  • Database migrations and static files                                      ║"
	@echo "║  • Environment configuration files                                           ║"
	@echo "║                                                                              ║"
	@echo "║  Services will be available at:                                              ║"
	@echo "║  • API:      http://localhost:8071                                           ║"
	@echo "║  • Admin:    http://localhost:8071/admin                                     ║"
	@echo "║                                                                              ║"
	@echo "╚══════════════════════════════════════════════════════════════════════════════╝"
	@echo -e "$(RESET)"
	@echo -e "$(GREEN)Starting bootstrap process...$(RESET)"
endif
	@echo "" 
.PHONY: pre-beautiful-bootstrap

post-beautiful-bootstrap: ## Display a success message after bootstrap
	@echo ""
ifeq ($(OS),Windows_NT)
	@echo "Bootstrap completed successfully!"
	@echo ""
	@echo "Next steps:"
	@echo "  - Play with the API at http://localhost:8071"
	@echo "  - Run 'make help' to see all available commands"
else
	@echo -e "$(GREEN)🎉 Bootstrap completed successfully!$(RESET)"
	@echo ""
	@echo -e "$(BOLD)Next steps:$(RESET)"
	@echo "  • Play with the API at http://localhost:8071"
	@echo "  • Run 'make help' to see all available commands"
endif
	@echo ""
.PHONY: post-beautiful-bootstrap

bootstrap: ## Prepare the project for local development
bootstrap: \
	pre-beautiful-bootstrap \
	pre-bootstrap \
	build \
	post-bootstrap \
	run \
	post-beautiful-bootstrap
.PHONY: bootstrap

# -- Docker/compose
#
build: cache ?=
build: ## build the project containers
	@$(MAKE) build-backend cache=$(cache)
.PHONY: build

build-backend: cache ?=
build-backend: ## build the app-dev container
	@$(COMPOSE) build app-dev $(cache)
.PHONY: build-backend

down: ## stop and remove containers, networks, images, and volumes
	@$(COMPOSE) down
.PHONY: down

logs: ## display app-dev logs (follow mode)
	@$(COMPOSE) logs -f app-dev
.PHONY: logs

run-backend: ## Start only the backend application and all needed services
	@$(COMPOSE) up --force-recreate -d app-dev
.PHONY: run-backend

run: ## start the wsgi (production) and development server
run: 
	@$(MAKE) run-backend
.PHONY: run

status: ## an alias for "docker compose ps"
	@$(COMPOSE) ps
.PHONY: status

stop: ## stop the development server using Docker
	@$(COMPOSE) stop
.PHONY: stop

# -- Backend
demo: ## flush db then create a demo for load testing purpose
	@$(MAKE) resetdb
	# @$(MANAGE) create_demo
.PHONY: demo

# Nota bene: Black should come after isort just in case they don't agree...
lint: ## lint back-end python sources
lint: \
  lint-ruff-format \
  lint-ruff-check
.PHONY: lint

lint-ruff-format: ## format back-end python sources with ruff
	@echo 'lint:ruff-format started…'
	@$(COMPOSE_RUN_APP_UV) ruff format .
.PHONY: lint-ruff-format

lint-ruff-check: ## lint back-end python sources with ruff
	@echo 'lint:ruff-check started…'
	@$(COMPOSE_RUN_APP_UV) ruff check . --fix
.PHONY: lint-ruff-check

test: ## run project tests
	@$(MAKE) test-back-parallel
.PHONY: test

test-back: ## run back-end tests
	@args="$(filter-out $@,$(MAKECMDGOALS))" && \
	bin/pytest $${args:-${1}}
.PHONY: test-back

test-back-parallel: ## run all back-end tests in parallel
	@args="$(filter-out $@,$(MAKECMDGOALS))" && \
	bin/pytest -n auto $${args:-${1}}
.PHONY: test-back-parallel

makemigrations:  ## run django makemigrations for the menshen project.
	@echo -e "$(BOLD)Running makemigrations$(RESET)"
	@$(COMPOSE) up -d postgresql
	@$(MANAGE) makemigrations
.PHONY: makemigrations

migrate:  ## run django migrations for the menshen project.
	@echo -e "$(BOLD)Running migrations$(RESET)"
	@$(COMPOSE) up -d postgresql
	@$(MANAGE) migrate
.PHONY: migrate

superuser: ## Create an admin superuser with password "admin"
	@echo -e "$(BOLD)Creating a Django superuser$(RESET)"
	@DJANGO_SUPERUSER_PASSWORD=admin $(MANAGE) createsuperuser --email admin@example.com --username admin --no-input
.PHONY: superuser

back-i18n-compile: ## compile the gettext files
	@$(MANAGE) compilemessages
.PHONY: back-i18n-compile

back-i18n-generate: ## create the .pot files used for i18n
	@$(MANAGE) makemessages -a --keep-pot --all
.PHONY: back-i18n-generate

shell: ## connect to database shell
	@$(MANAGE) shell #_plus
.PHONY: dbshell

# -- Database
#
dbshell: ## connect to database shell
	docker compose exec app-dev python manage.py dbshell
.PHONY: dbshell

resetdb: FLUSH_ARGS ?=
resetdb: ## flush database and create a superuser "admin"
	@echo -e "$(BOLD)Flush database$(RESET)"
	@$(MANAGE) flush $(FLUSH_ARGS)
	@${MAKE} superuser
.PHONY: resetdb

# -- Misc
clean: ## restore repository state as it was freshly cloned
	git clean -idx
.PHONY: clean

help:
	@echo -e "$(BOLD)menshen Makefile"
	@echo "Please use 'make $(BOLD)target$(RESET)' where $(BOLD)target$(RESET) is one of:"
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(firstword $(MAKEFILE_LIST)) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "$(GREEN)%-30s$(RESET) %s\n", $$1, $$2}'
.PHONY: help
