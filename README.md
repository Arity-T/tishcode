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
