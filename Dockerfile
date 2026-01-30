# Dockerfile for tishcode webhook server
FROM python:3.12.8-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.5.18 /uv /uvx /bin/

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-dev

COPY main.py server.py ./
COPY src/ ./src/

# Fixed paths inside container
ENV TC_GITHUB_PRIVATE_KEY_PATH=/app/private-key.pem
ENV TC_REPOS_BASE_PATH=/app/repos
ENV TC_DB_PATH=/app/data/tishcode.db

RUN mkdir -p /app/data /app/repos

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
