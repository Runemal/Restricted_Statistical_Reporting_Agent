# Restricted ETL Agent

Python-инструмент для restricted Claude Agent SDK агента, который собирает дневную статистику CLIProxyAPI и отправляет аналитическую сводку в Telegram на русском языке.

1. Поднимает LiteLLM proxy с Postgres для роутинга моделей и Admin UI.
2. Открывает SSH local port-forward до удаленного `cliproxy-usage-monitor`.
3. Забирает usage events за текущий календарный день через `/export/usage-events`.
4. Выполняет read-only SQL по временной SQLite-копии.
5. Получает лимиты Codex/ChatGPT через CLIProxyAPI Management API.
6. Даёт Claude agent сгенерировать только короткое ироничное вступление по фактам из отчёта.
7. Отправляет финальную аналитическую сводку в Telegram.
8. Удаляет временные CSV/SQLite файлы после запуска.

Агент намеренно узкий: наружу открыты только `run_etl_pipeline` и `send_telegram_report`. Встроенные файловые, shell и delete-действия запрещены permissions и `PreToolUse` hook.

## Быстрый Старт

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
cp configs/pipeline.example.yaml configs/pipeline.yaml
cp litellm/config.example.yaml litellm/config.yaml
```

Заполни `.env`. Обязательные значения:

```env
ANTHROPIC_API_KEY=...          # upstream provider key, который использует LiteLLM
LITELLM_MASTER_KEY=...
LITELLM_AGENT_KEY=...          # опционально: отдельный ключ LiteLLM для агента
LITELLM_SALT_KEY=...
LITELLM_POSTGRES_PASSWORD=...
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
SSH_TARGET=user@server
CPA_MANAGEMENT_KEY=...
CPA_BASE_URL=http://your-cpa-proxy.example:8317
AUTH_INDEX=...
CHATGPT_ACCOUNT_ID=...
```

Целевой сервис статистики по умолчанию:

```env
SSH_REMOTE_PORT=9108
API_PATH="/export/usage-events?since={since_utc}&until={until_utc}&format=json"
API_DATA_PATH=data
STORAGE_DATASET_NAME=usage_events
REPORT_TIMEZONE=Europe/Moscow
```

Запуск LiteLLM и Postgres:

```bash
cd litellm
docker compose --env-file ../.env up -d
cd ..
```

Если в LiteLLM созданы отдельные user/service-account ключи, для агента указывай такой ключ в `LITELLM_AGENT_KEY`. `LITELLM_MASTER_KEY` лучше оставлять для bootstrap и администрирования.

## Ручной Запуск Агента

В этом режиме агент сначала собирает данные, затем генерирует короткое ироничное вступление на русском языке. Фактическая сводка добавляется Python-кодом и не переписывается моделью.

```bash
set -a
source .env
set +a

ANTHROPIC_BASE_URL="$LITELLM_BASE_URL" \
ANTHROPIC_API_KEY="${LITELLM_AGENT_KEY:-$LITELLM_MASTER_KEY}" \
.venv/bin/python -m etl_tool.agent \
  --config configs/pipeline.yaml \
  --queries queries/report.sql
```

Запуск только ETL-пайплайна без Claude agent. Этот режим отправляет обычную детерминированную сводку без агентского вступления:

```bash
set -a
source .env
set +a

.venv/bin/python -c "from etl_tool.pipeline import run_pipeline; print(run_pipeline('configs/pipeline.yaml', 'queries/report.sql').model_dump_json(indent=2))"
```

Получить spend logs из LiteLLM:

```bash
set -a
source .env
set +a

.venv/bin/etl-spend-logs --limit 20
```

LiteLLM Admin UI доступен по адресу `LITELLM_BASE_URL` + `/ui`, например `http://localhost:4000/ui`.

## Формат Telegram

Строки, которые начинаются с `#`, отправляются в Telegram как жирные заголовки. Сам символ `#` не показывается. Ироничное вступление агента находится обычным текстом в начале сообщения.

```text
Сегодня статистика выглядит так, будто токены устроили корпоратив без бюджета: ошибок нет, но latency явно просила отпуск.

#Лимиты Codex/ChatGPT:
План: Pro.
#Сводка по использованию за день: 2026-06-27 (Europe/Moscow)
```

## Модель Безопасности

- Custom tool принимает только пути к конфигу пайплайна и SQL-файлу.
- MCP server привязан к путям `--config` и `--queries`, переданным в CLI; альтернативные пути от модели отклоняются.
- SSH-команда собирается как список аргументов, без shell.
- API extraction делает только `GET` и только через SSH tunnel.
- SQL должен быть `SELECT` или `WITH`; destructive keywords запрещены.
- SQLite открывается повторно в read-only режиме для отчетных запросов.
- Локальные записи ограничены `output_dir` из конфига, временные CSV/SQLite удаляются после запуска.
- Claude agent получает только MCP tool и hook, который запрещает delete/destructive tool use.
- Модель генерирует только вступление; неизменяемая сводка пайплайна добавляется в `send_telegram_report`.
- Структурированный результат описан Pydantic JSON schema (`AgentRunReport`).
