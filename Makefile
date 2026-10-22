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

# -- Docker
# Get the current user ID to use for docker run and docker exec commands
ifeq ($(OS),Windows_NT)
DOCKER_USER         := 0:0     # run containers as root on Windows
else
DOCKER_UID          := $(shell id -u)
DOCKER_GID          := $(shell id -g)
DOCKER_USER         := $(DOCKER_UID):$(DOCKER_GID)
endif
APP_NAME           ?= menshen-backend
COMPOSE             = DOCKER_UID=$(DOCKER_UID) DOCKER_GID=$(DOCKER_GID) DOCKER_USER=$(DOCKER_USER) docker compose
COMPOSE_EXEC        = $(COMPOSE) exec
COMPOSE_EXEC_APP    = $(COMPOSE_EXEC) $(APP_NAME)
COMPOSE_RUN         = $(COMPOSE) run --rm --remove-orphans
COMPOSE_RUN_APP     = $(COMPOSE_RUN) $(APP_NAME)
COMPOSE_RUN_APP_UV  = $(COMPOSE_RUN_APP) uv run

# -- Backend
MANAGE              = $(COMPOSE_RUN_APP_UV) python manage.py

# -- Client
CLIENT_UV           = cd src/client && uv
CLIENT_UV_RUN       = $(CLIENT_UV) run

# -- Playground
COMPOSE_EXEC_SOURCE_UV = $(COMPOSE_EXEC) menshen-playground-source uv run
COMPOSE_EXEC_TARGET_UV = $(COMPOSE_EXEC) menshen-playground-target uv run

# -- Interop
INTEROP_URL         = https://github.com/suitenumerique/interop/archive/refs/heads/main.tar.gz

# ==============================================================================
# RULES

default: help

data/static:
	@mkdir -p data/static

interop:
	mkdir -p interop
	curl -sL $(INTEROP_URL) | tar -xzf - --strip-components=1 -C interop
	cd interop && make bootstrap

env.d/development/common.local:
	@bin/local-env

env.d/development/kc_postgresql.local:
	@touch env.d/development/kc_postgresql.local

env.d/development/postgresql.local:
	@touch env.d/development/postgresql.local

env.d/development/proconnect.local:
	@cp env.d/development/proconnect env.d/development/proconnect.local
	@echo -e "$(BOLD)Created env.d/development/proconnect.local environment.$(RESET)"
	@echo -e "$(GREEN)It should be edited with appropriate credentials!$(RESET)"

LOCAL_ENV = \
  env.d/development/common.local \
	env.d/development/kc_postgresql.local \
	env.d/development/postgresql.local \
	env.d/development/proconnect.local

# -- Project
#
create-env-local-files: $(LOCAL_ENV)
create-env-local-files: ## create env.local files in env.d/development
.PHONY: create-env-local-files

pre-bootstrap: \
  data/static \
  interop \
  create-env-local-files
.PHONY: pre-bootstrap

post-bootstrap: \
  migrate \
  demo \
  back-i18n-compile
.PHONY: post-bootstrap

post-bootstrap-pc:
	APP_NAME=menshen-backend-pc $(MAKE) migrate
	APP_NAME=menshen-backend-pc $(MAKE) demo
.PHONY: post-bootstrap-pc

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
	@echo "  - API:      http://menshen.lasuite.localhost:49000/auth/token/"
	@echo "  - Admin:    http://menshen.lasuite.localhost:49000/admin"
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
	@echo "║  • API:      http://menshen.lasuite.localhost:49000/auth/token/              ║"
	@echo "║  • Admin:    http://menshen.lasuite.localhost:49000/admin                    ║"
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
	@echo "  - Play with the API at http://menshen.lasuite.localhost:49000/auth/token/docs"
	@echo "  - Run 'make help' to see all available commands"
else
	@echo -e "$(GREEN)🎉 Bootstrap completed successfully!$(RESET)"
	@echo ""
	@echo -e "$(BOLD)Next steps:$(RESET)"
	@echo "  • Play with the API at http://menshen.lasuite.localhost:49000/auth/token/docs"
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
	@$(COMPOSE) build $(cache)
.PHONY: build

build-backend: cache ?=
build-backend: ## build the menshen container
	@$(COMPOSE) build $(APP_NAME) $(cache)
.PHONY: build-backend

build-playground: \
  build-playground-source \
  build-playground-target
build-playground:  ## build playground services container
.PHONY: build-playground

build-playground-source: cache ?=
build-playground-source: ## build the playground-source container
	@$(COMPOSE) build menshen-playground-source $(cache)
.PHONY: build-playground-source

build-playground-target: cache ?=
build-playground-target: ## build the playground-target container
	@$(COMPOSE) build menshen-playground-target $(cache)
.PHONY: build-playground-target

down: ## stop and remove containers, networks, images, and volumes
	@$(COMPOSE) down
.PHONY: down

logs: ## display menshen logs (follow mode)
	@$(COMPOSE) logs -f $(APP_NAME)
.PHONY: logs

run-backend: ## Start only the backend application and all needed services
	@$(COMPOSE) up --no-recreate -d $(APP_NAME)
.PHONY: run-backend

run-playground: ## start the playground 
	$(COMPOSE) up --no-recreate -d menshen-playground-source menshen-playground-target
.PHONY: run-playground

run-playground-pc: ## start the playground (with ProConnect integration)
	$(COMPOSE) up --force-recreate -d menshen-playground-source-pc menshen-playground-target-pc
.PHONY: run-playground-pc

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

watch: ## watch changes in playground source code (development mode)
	@$(COMPOSE) watch menshen-playground-source menshen-playground-target
.PHONY: watch 

watch-pc: ## watch changes in playground source code (development mode with Proconnect integration)
	@$(COMPOSE) watch menshen-playground-source-pc menshen-playground-target-pc
.PHONY: watch-pc

interop-update: ## update interop services
	$(MAKE) -B interop
.PHONY: interop-update

# -- Quality checks
#
lint: ## run project linters
lint: \
  lint-back \
  lint-client \
  lint-playground
.PHONY: lint

lint-back: ## lint back-end python sources
lint-back: \
  lint-back-ruff-format \
  lint-back-ruff-check \
  lint-back-ty-check
.PHONY: lint-back

lint-back-ruff-format: ## format back-end python sources with ruff
	@echo 'lint-back:ruff-format started…'
	@$(COMPOSE_RUN_APP_UV) ruff format .
.PHONY: lint-back-ruff-format

lint-back-ruff-check: ## lint back-end python sources with ruff
	@echo 'lint-back:ruff-check started…'
	@$(COMPOSE_RUN_APP_UV) ruff check . --fix
.PHONY: lint-back-ruff-check

lint-back-ty-check: ## lint back-end python sources with ty
	@echo 'lint-back:ty-check started…'
	@$(COMPOSE_RUN_APP_UV) ty check
.PHONY: lint-back-ty-check

lint-client: ## lint client python sources
lint-client: \
  lint-client-ruff-format \
  lint-client-ruff-check \
  lint-client-ty-check
.PHONY: lint-client

lint-client-ruff-format: ## format client python sources with ruff
	@echo 'lint-client:ruff-format started…'
	@$(CLIENT_UV_RUN) ruff format .
.PHONY: lint-client-ruff-format

lint-client-ruff-check: ## lint client python sources with ruff
	@echo 'lint-client:ruff-check started…'
	@$(CLIENT_UV_RUN) ruff check . --fix
.PHONY: lint-client-ruff-check

lint-client-ty-check: ## lint client python sources with ty
	@echo 'lint-client:ty-check started…'
	@$(CLIENT_UV_RUN) ty check
.PHONY: lint-client-ty-check

lint-playground: ## lint playground python sources
lint-playground: \
  lint-playground-source \
  lint-playground-target
.PHONY: lint-playground

lint-playground-source: ## lint playground-source python sources
lint-playground-source: \
  lint-playground-source-ruff-format \
  lint-playground-source-ruff-check
.PHONY: lint-playground-source

lint-playground-source-ruff-check: ## lint playground-source python sources with ruff
	@echo 'lint-playground-source:ruff-check started…'
	@$(COMPOSE_EXEC_SOURCE_UV) ruff check . --fix
.PHONY: lint-playground-source-ruff-check

lint-playground-source-ruff-format: ## format playground-source python sources with ruff
	@echo 'lint-playground-source:ruff-format started…'
	@$(COMPOSE_EXEC_SOURCE_UV) ruff format .
.PHONY: lint-playground-source-ruff-format

lint-playground-target: ## lint playground-target python sources
lint-playground-target: \
  lint-playground-target-ruff-format \
  lint-playground-target-ruff-check
.PHONY: lint-playground-target

lint-playground-target-ruff-check: ## lint playground-target python sources with ruff
	@echo 'lint-playground-target:ruff-check started…'
	@$(COMPOSE_EXEC_TARGET_UV) ruff check . --fix
.PHONY: lint-playground-target-ruff-check

lint-playground-target-ruff-format: ## format playground-target python sources with ruff
	@echo 'lint-playground-target:ruff-format started…'
	@$(COMPOSE_EXEC_TARGET_UV) ruff format .
.PHONY: lint-playground-target-ruff-format

test: ## run project tests
test: \
  test-back \
  test-client
.PHONY: test

test-back: ## run back-end tests
	bin/pytest
.PHONY: test-back

test-back-parallel: ## run all back-end tests in parallel
	bin/pytest -n auto
.PHONY: test-back-parallel

test-client: ## run client tests 
	$(CLIENT_UV_RUN) pytest
.PHONY: test-client

test-e2e: ## run e2e tests
	$(MAKE) stop
	# Remove containers so that we reset their state
	$(COMPOSE) up -d --force-recreate menshen-playground-source-e2e menshen-playground-target-e2e
	$(COMPOSE_RUN) playwright
.PHONY: test-e2e

test-playground: ## run playground tests
	# You should run the watcher first or rebuild the container
	@$(COMPOSE_EXEC_TARGET_UV) pytest
.PHONY: test-playground

# -- Backend
#
demo: ## flush db then create a demo for load testing purpose
	@$(MAKE) resetdb
	@$(MANAGE) create_demo
.PHONY: demo

makemigrations:  ## run django makemigrations for the menshen project.
	@echo -e "$(BOLD)Running makemigrations$(RESET)"
	@$(COMPOSE) up -d menshen-postgresql
	@$(MANAGE) makemigrations
.PHONY: makemigrations

migrate:  ## run django migrations for the menshen project.
	@echo -e "$(BOLD)Running migrations$(RESET)"
	@$(COMPOSE) up -d menshen-postgresql
	@$(MANAGE) migrate
.PHONY: migrate

superuser: ## Create an admin superuser with password "admin"
	@echo -e "$(BOLD)Creating a Django superuser$(RESET)"
	$(MANAGE) createsuperuser --no-input
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
	docker compose exec $(APP_NAME) python manage.py dbshell
.PHONY: dbshell

resetdb: ## flush database and create a superuser "admin"
	@echo -e "$(BOLD)Flush database$(RESET)"
	@$(MANAGE) flush --no-input
	@${MAKE} superuser
.PHONY: resetdb

# -- K8S
#
build-k8s-cluster: ## build the kubernetes cluster using kind
	curl \
		https://raw.githubusercontent.com/numerique-gouv/tools/refs/heads/main/kind/create_cluster.sh | \
		bash -s -- menshen
.PHONY: build-k8s-cluster

k8s-dev: ## start developing locally using Tilt
	tilt up
.PHONY: k8s-dev

# -- Misc
clean: ## restore repository state as it was freshly cloned
	git clean -idx
.PHONY: clean

help:
	@echo -e "$(BOLD)Menshen Makefile$(RESET)\n"
	@echo -e "Please use 'make $(BOLD)target$(RESET)' where $(BOLD)target$(RESET) is one of:\n"
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(firstword $(MAKEFILE_LIST)) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "$(GREEN)%-30s$(RESET) %s\n", $$1, $$2}'
.PHONY: help
