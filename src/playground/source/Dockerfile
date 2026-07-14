# Django menshen playground: source

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
COPY --from=ghcr.io/astral-sh/uv:0.11.28 /uv /uvx /bin/

WORKDIR /app

# Install dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=src/playground/source/uv.lock,target=uv.lock \
    --mount=type=bind,source=src/playground/source/pyproject.toml,target=pyproject.toml \
      uv sync --locked --no-install-project --no-dev
COPY src/playground/source /app
RUN --mount=type=cache,target=/root/.cache/uv \
      uv sync --locked --no-dev

# ---- Back-end builder image ----
FROM back-builder AS backend-development

ENV DJANGO_SUPERUSER_PASSWORD=admin

# Run migrations to create the SQLite database in the container and the super user
RUN uv run python manage.py migrate && \
    uv run python manage.py createsuperuser \
      --no-input \
      --username admin \
      --email admin@example.org && \
    uv run python manage.py loaddata recordings

# Run django development server
CMD ["uv", "run", "python", "manage.py", "runserver", "0.0.0.0:8000"]
