# Django menshen 

# ---- base image to inherit from ----
FROM python:3.14.3-alpine AS base

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
COPY --from=ghcr.io/astral-sh/uv:0.11.1 /uv /uvx /bin/

WORKDIR /app

# Install dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=src/backend/uv.lock,target=uv.lock \
    --mount=type=bind,source=src/backend/pyproject.toml,target=pyproject.toml \
      uv sync --locked --no-install-project --no-dev
COPY src/backend /app
RUN --mount=type=cache,target=/root/.cache/uv \
      uv sync --locked --no-dev

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
RUN --mount=from=ghcr.io/astral-sh/uv:0.11.1,source=/uv,target=/bin/uv \
      DJANGO_CONFIGURATION=Build \
      uv run python manage.py compilemessages --ignore=".venv/**/*"

# We wrap commands run in this container by the following entrypoint that
# creates a user on-the-fly with the container user ID (see USER) and root group
# ID.
ENTRYPOINT [ "/usr/local/bin/entrypoint" ]

# ---- Development image ----
FROM core AS backend-development

ARG DOCKER_USER

# Configure uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_CACHE_DIR=/opt/cache

# Switch back to the root user to install development dependencies
USER root:root

# Install psql
RUN apk add postgresql-client

# Install uv
COPY --from=ghcr.io/astral-sh/uv:0.11.1 /uv /uvx /bin/

# Install development dependencies and ensure the virtual 
# environment belongs to the DOCKER_USER 
RUN uv sync --all-extras --locked && \
    chown -R "${DOCKER_USER}" /opt/venv /opt/cache

# Restore the un-privileged user running the application
USER ${DOCKER_USER}

# Target database host (e.g. database engine following docker compose services
# name) & port
ENV DB_HOST=postgresql \
    DB_PORT=5432

# Run django development server
CMD ["uv", "run", "python", "manage.py", "runserver", "0.0.0.0:8000"]

# ---- Production image ----
FROM core AS backend-production

ARG MENSHEN_STATIC_ROOT=/data/static

# Gunicorn
RUN mkdir -p /usr/local/etc/gunicorn
COPY docker/files/usr/local/etc/gunicorn/menshen.py /usr/local/etc/gunicorn/menshen.py

# Un-privileged user running the application
ARG DOCKER_USER
USER ${DOCKER_USER}

ENV PATH="/app/.venv/bin:$PATH"

# The default command runs gunicorn WSGI server in menshen's main module
CMD [ \
  "gunicorn", \
  "-c", \
  "/usr/local/etc/gunicorn/menshen.py", \
  "menshen.wsgi:application" \
]
