# Select the image to build based on SERVER_TYPE, defaulting to fbapy, or docker-compose build args
ARG SERVER_TYPE=fbapy

# === Python environment from uv ===
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder

# Used for build Python packages
RUN sed -i 's/deb.debian.org/mirrors.ustc.edu.cn/g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && apt-get install -y --no-install-recommends gcc python3-dev libportaudio2 portaudio19-dev \
    && rm -rf /var/lib/apt/lists/*

COPY . /fbapy

WORKDIR /fbapy

# Configure uv environment
ENV UV_COMPILE_BYTECODE=1 \
    UV_NO_CACHE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/usr/local

# Install dependencies with cache
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-default-groups --group server --no-install-project

# === Runtime base server image ===
FROM python:3.13-slim AS base_server

RUN sed -i 's/deb.debian.org/mirrors.ustc.edu.cn/g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates supervisor \
    && rm -rf /var/lib/apt/lists/*

COPY deploy/uv/uv-installer.sh /uv-installer.sh
COPY deploy/uv/uv-x86_64-unknown-linux-gnu.tar.gz /uv-x86_64-unknown-linux-gnu.tar.gz

RUN sh /uv-installer.sh --local /uv-x86_64-unknown-linux-gnu.tar.gz \
    && rm /uv-installer.sh /uv-x86_64-unknown-linux-gnu.tar.gz

ENV PATH="/root/.local/bin/:$PATH"

COPY --from=builder /fbapy /fbapy

COPY --from=builder /usr/local /usr/local

COPY deploy/backend/supervisor/supervisord.conf /etc/supervisor/supervisord.conf

WORKDIR /fbapy/backend

# === FastAPI server image ===
FROM base_server AS fbapy

COPY deploy/backend/supervisor/fbapy.conf /etc/supervisor/conf.d/

RUN mkdir -p /var/log/fba

EXPOSE 8000

CMD ["supervisord", "-c", "/etc/supervisor/supervisord.conf"]

# Build image
FROM ${SERVER_TYPE}
