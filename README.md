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

**Endpoints:**
- `POST /webhook` - GitHub webhook
- `GET /health` - health check

**Обрабатываемые события:**
- `issues/opened` → fixissue (создаёт PR)
- `pull_request_review/submitted` (changes_requested) → fixpr
- `check_suite/completed` → review

**Автоматический цикл:**
1. Создаётся issue → агент создаёт PR
2. CI завершается → агент делает review
3. Если review=changes_requested → агент фиксит PR
4. Повтор шагов 2-3 до approve или достижения `TC_MAX_RETRIES`

Состояние (количество попыток) хранится в SQLite (`TC_DB_PATH`).

## Docker

Пример `.env` для Docker: `.env.docker-example` (без переменных с путями, они фиксированы в образе).

### Сервер (webhook)

```bash
# Подготовка
cp .env.docker-example .env.docker
# .env.docker заполняем своими значениями

# Помещаем private-key.pem в директорию с проектом, либо задаём переменную окружения
# export HOST_GITHUB_PRIVATE_KEY_PATH=/path/to/your/private-key.pem

# Также можно задать переменную для указание порта, отличного от 8000
# export HOST_PORT=8001

# Сборка и запуск
docker compose build
docker compose up -d
```

### CLI

```bash
# Сборка
docker build -f Dockerfile.cli -t tishcode-cli .

# Запуск (укажи путь к своему .pem файлу)
docker run --rm \
  --env-file .env.docker \
  -v ./private-key.pem:/app/private-key.pem:ro \
  tishcode-cli fixissue <issue-url>

docker run --rm \
  --env-file .env.docker \
  -v ./private-key.pem:/app/private-key.pem:ro \
  tishcode-cli review <pr-url>

docker run --rm \
  --env-file .env.docker \
  -v ./private-key.pem:/app/private-key.pem:ro \
  tishcode-cli fixpr <pr-url>
```

## Проверка кода

В проекте используются ruff для форматирования кода.

```bash
uv run ruff check .
uv run ruff check . --fix
```

Mypy для проверки типов.

```bash
uv run mypy .
```
