# Select the image to build based on SERVER_TYPE, defaulting to fba_server, or docker-compose build args
ARG SERVER_TYPE=fba_server
ARG FBA_HOME=/fba

# === Python environment from uv ===
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder

ARG FBA_HOME

# Used for build Python packages
RUN sed -i 's/deb.debian.org/mirrors.ustc.edu.cn/g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && apt-get install -y --no-install-recommends gcc make python3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR ${FBA_HOME}

# Configure uv environment
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/usr/local

# Install Python dependencies first so normal source changes do not invalidate this layer.
COPY pyproject.toml uv.lock ./
COPY backend/__init__.py ./backend/__init__.py

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-default-groups --group server --no-install-project

# Copy the rest of the project after dependencies are ready.
COPY . ${FBA_HOME}

# === Runtime base server image ===
FROM python:3.13-slim AS base_server

ARG FBA_HOME

RUN sed -i 's/deb.debian.org/mirrors.ustc.edu.cn/g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates supervisor ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY deploy/uv/uv-x86_64-unknown-linux-gnu.tar.gz /tmp/uv.tar.gz

RUN mkdir -p /usr/local/bin \
    && tar -xzf /tmp/uv.tar.gz -C /usr/local/bin \
    && rm /tmp/uv.tar.gz

ENV PATH="/root/.local/bin/:$PATH"

COPY --from=builder ${FBA_HOME} ${FBA_HOME}

COPY --from=builder /usr/local /usr/local

COPY deploy/backend/supervisor/supervisord.conf /etc/supervisor/supervisord.conf

WORKDIR ${FBA_HOME}/backend

# === FastAPI server image ===
FROM base_server AS fba_server

COPY deploy/backend/supervisor/fba_server.conf /etc/supervisor/conf.d/

RUN mkdir -p /var/log/fba

EXPOSE 8001

CMD ["supervisord", "-c", "/etc/supervisor/supervisord.conf"]

# Build image
FROM ${SERVER_TYPE}
