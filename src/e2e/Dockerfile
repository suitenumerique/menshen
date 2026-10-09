# Menshen playground e2e testing using Playright
FROM python:3.14.8-trixie

ARG DEBIAN_FRONTEND=noninteractive
ARG DOCKER_UID

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
# Disable Python downloads, because we want to use the system interpreter
# across both images. If using a managed Python version, it needs to be copied
# from the build image into the final image.
ENV UV_PYTHON_DOWNLOADS=0

# Install uv
COPY --from=ghcr.io/astral-sh/uv:0.12.5 /uv /uvx /bin/

WORKDIR /app

# Install dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=src/e2e/uv.lock,target=uv.lock \
    --mount=type=bind,source=src/e2e/pyproject.toml,target=pyproject.toml \
      uv sync --locked --no-install-project --no-dev
COPY src/e2e /app
RUN --mount=type=cache,target=/root/.cache/uv \
      uv sync --locked --no-dev

# Install playwright system dependencies
RUN apt-get update && \
    apt-get install -y nodejs npm && \
    npm install npx && \
    npx playwright install-deps && \
    npm uninstall npx && \
    apt-get remove -y nodejs npm && \
    apt-get clean

# Create running user
RUN useradd -d /tmp/docker -u ${DOCKER_UID} -m docker
USER ${DOCKER_UID}

# Install Playright along with system dependencies
RUN uv run playwright install --only-shell chromium 

# Tun tests
CMD uv run pytest
