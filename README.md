# tishcode 🤖

AI coding agent для автоматизации работы с GitHub!

## Getting started

Чтобы подключить tishcode к репозиторию достаточно в несколько нажатий установить [tishenko-code](https://github.com/apps/tishenko-code) GitHub App и выбрать нужный репозиторий. После этого для всех новых issues агенты будут автоматически создавать Pull Requests.

Если в репозитории есть тесты в GitHub Actions, то по-мимо агентов для написания кода, в дело вступят агенты ревьюверы. Они автоматически будут анализировать изменения и результаты запуска тестов.

Пример минимального workflow для GitHub Actions, после которого будут запускаться агенты ревьюверы:

```yml
name: Trigger AIReviewer workflow

on:
  pull_request:
    types: [opened, synchronize, reopened]

jobs:
  trigger-airviewer:
    name: Trigger AIReviewer
    runs-on: ubuntu-latest
    steps:
      - name: Anything here
        run: |
          echo "It's not a real check, just a trigger for AIReviewer workflow."
```

## Локальный запуск

Если вы хотите протестировать tishcode локально или развернуть собственную копию, нужно сначала создать GitHub App и получить приватный ключ.

### Создание GitHub App

1. [Создайте GitHub App](https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/registering-a-github-app) с разрешениями: **Actions, Checks, Contents, Issues, Pull requests, Workflows** (Read and write)

2. [Сгенерируйте приватный ключ](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/managing-private-keys-for-github-apps) — скачается `.pem` файл

3. Для webhook-сервера: настройте [Webhook URL](https://docs.github.com/en/webhooks/using-webhooks/creating-webhooks) и подпишитесь на события: **Issues, Pull Request, Pull Request Review, Check Suite**

   Для локальной разработки можно использовать [smee.io](https://smee.io) для проксирования вебхуков как [рекомендует документация GitHub](https://docs.github.com/en/webhooks/using-webhooks/handling-webhook-deliveries#forward-webhooks):
   ```bash
   npm install -g smee-client
   smee --url https://smee.io/<your-channel> --path /webhook --port 8000
   ```

### Установка зависимостей

```bash
uv sync
cp .env.example .env
# Заполняем .env своими значениями
```

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
3. Если во время review были замечания → агент фиксит PR
4. Агент повторяет цикл пока не выполнит задачу или достигнет `TC_MAX_RETRIES`

Состояние (количество попыток) хранится в SQLite (`TC_DB_PATH`).

## Запуск через Docker

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

и mypy для проверки типов.

```bash
uv run mypy .
```
