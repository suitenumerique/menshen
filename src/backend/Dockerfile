# Django menshen 

# ---- base image to inherit from ----
FROM python:3.14.6-alpine AS base

# Upgrade pip to its latest release to speed up dependencies installation
# We must do taht to avoid having an outdated pip version with security issues
RUN python -m pip install --upgrade pip

# Upgrade system packages to install security updates
RUN apk update && \
    apk upgrade

# ---- Back-end builder image ----
FROM base AS back-builder

# Configure uv
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
# Disable Python downloads, because we want to use the system interpreter
# across both images. If using a managed Python version, it needs to be copied
# from the build image into the final image.
ENV UV_PYTHON_DOWNLOADS=0

# Install uv
COPY --from=ghcr.io/astral-sh/uv:0.11.29 /uv /uvx /bin/

WORKDIR /app

# Install dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=src/backend/uv.lock,target=uv.lock \
    --mount=type=bind,source=src/backend/pyproject.toml,target=pyproject.toml \
      uv sync --locked --no-install-project --no-dev
COPY src/backend /app
RUN --mount=type=cache,target=/root/.cache/uv \
      uv sync --locked --no-dev

# ---- static link collector ----
FROM back-builder AS link-collector

ARG MENSHEN_STATIC_ROOT=/data/static

# Install pango & rdfind
RUN apk add --no-cache \
  pango \
  rdfind

# Copy the application from the builder
COPY --from=back-builder /app /app

WORKDIR /app

ENV PATH="/app/.venv/bin:$PATH"

# collectstatic
RUN DJANGO_CONFIGURATION=Build \
  uv run python manage.py collectstatic --noinput

# Replace duplicated file by a symlink to decrease the overall size of the
# final image
RUN rdfind \
  -makesymlinks true \
  -followsymlinks true \
  -makeresultsfile false \
  ${MENSHEN_STATIC_ROOT}

# ---- Core application image ----
FROM base AS core

ENV PYTHONUNBUFFERED=1

# Install required system libs
RUN apk add \
  gettext

# Copy entrypoint
COPY ./docker/files/usr/local/bin/entrypoint /usr/local/bin/entrypoint

# Give the "root" group the same permissions as the "root" user on /etc/passwd
# to allow a user belonging to the root group to add new users; typically the
# docker user (see entrypoint).
RUN chmod g=u /etc/passwd

# Copy the application from the builder
COPY --from=back-builder /app /app

WORKDIR /app

# Generate compiled translation messages
RUN --mount=from=ghcr.io/astral-sh/uv:0.11.29,source=/uv,target=/bin/uv \
      DJANGO_CONFIGURATION=Build \
      uv run python manage.py compilemessages --ignore=".venv/**/*"

# We wrap commands run in this container by the following entrypoint that
# creates a user on-the-fly with the container user ID (see USER) and root group
# ID.
ENTRYPOINT [ "/usr/local/bin/entrypoint" ]

# ---- Development image ----
FROM core AS backend-development

ARG DOCKER_USER

# Staticfiles root directory (used by whitenoise)
ARG MENSHEN_STATIC_ROOT=/data/static

# Configure uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_CACHE_DIR=/opt/cache

# Switch back to the root user to install development dependencies
USER root:root

# Install psql and curl
RUN apk add \
      postgresql-client \
      curl

# Install uv
COPY --from=ghcr.io/astral-sh/uv:0.11.29 /uv /uvx /bin/

# Install development dependencies and ensure the virtual 
# environment belongs to the DOCKER_USER 
RUN uv sync --all-extras --locked && \
    chown -R "${DOCKER_USER}" /opt/venv /opt/cache

# Restore the un-privileged user running the application
USER ${DOCKER_USER}

# Copy statics
COPY --from=link-collector ${MENSHEN_STATIC_ROOT} ${MENSHEN_STATIC_ROOT}

# Target database host (e.g. database engine following docker compose services
# name) & port
ENV DB_HOST=postgresql \
    DB_PORT=5432

# Run django development server
CMD ["uv", "run", "python", "manage.py", "runserver", "0.0.0.0:8000"]

# ---- Production image ----
FROM core AS backend-production

# Un-privileged user running the application
ARG DOCKER_USER

# Staticfiles root directory (used by whitenoise)
ARG MENSHEN_STATIC_ROOT=/data/static

USER ${DOCKER_USER}

# Copy dependencies
COPY --from=back-builder /app/.venv /app/.venv

# Copy statics
COPY --from=link-collector ${MENSHEN_STATIC_ROOT} ${MENSHEN_STATIC_ROOT}

# The default command runs uvicorn ASGI server in Menshen's main module
# WEB_CONCURRENCY: number of workers to run <=> --workers=4
ENV WEB_CONCURRENCY=4
CMD [\
  "/app/.venv/bin/uvicorn",\
  "--app-dir=/app",\
  "--host=0.0.0.0",\
  "--timeout-graceful-shutdown=300",\
  "--limit-max-requests=20000",\
  "--lifespan=off",\
  "menshen.asgi:application"\
]
