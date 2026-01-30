# tishcode

AI coding agent для автоматизации работы с GitHub issues и pull requests.

## Установка

```bash
uv sync
cp .env.example .env
# Заполни .env своими значениями
```

## Запуск

### CLI

```bash
# Создать PR для решения issue
uv run python main.py fixissue <issue-url>

# Сделать ревью PR
uv run python main.py review <pr-url>

# Внести исправления в существующий PR
uv run python main.py fixpr <pr-url>
```

### Webhook сервер

```bash
uv run uvicorn server:app --reload --port 8000
```

Webhook endpoint: `POST /webhook`

Health check: `GET /health`
