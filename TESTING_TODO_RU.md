# Для Тестирования

План проверки restricted ETL agent end-to-end.

## 1. Установить зависимости

```bash
cd /home/runemal/codex/claude_sdk/etl_tool
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## 2. Заполнить переменные окружения

```bash
cp .env.example .env
cp litellm/config.example.yaml litellm/config.yaml
```

Нужно заполнить:

```bash
ANTHROPIC_API_KEY=...
LITELLM_MASTER_KEY=...
LITELLM_AGENT_KEY=... # опционально, отдельный ключ LiteLLM для агента
LITELLM_BASE_URL=http://localhost:4000
LITELLM_SALT_KEY=...
LITELLM_POSTGRES_PASSWORD=...
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
SSH_TARGET=etl-user@your-server
SSH_REMOTE_PORT=9108
API_PATH="/export/usage-events?since={since_utc}&until={until_utc}&format=json"
API_DATA_PATH=data
STORAGE_DATASET_NAME=usage_events
REPORT_TIMEZONE=Europe/Moscow
CPA_MANAGEMENT_KEY=...
CPA_BASE_URL=http://your-cpa-proxy.example:8317
AUTH_INDEX=...
CHATGPT_ACCOUNT_ID=...
```

Python-команды сами загрузят `.env`. Если запускаешь внешние процессы, которым нужны эти переменные напрямую, можно по-прежнему загрузить файл через `set -a; source .env; set +a`.

## 3. Подготовить конфиг пайплайна

```bash
cp configs/pipeline.example.yaml configs/pipeline.yaml
```

`configs/pipeline.yaml` можно оставить на env-ссылках:

```yaml
ssh:
  target: "${SSH_TARGET}"
  identity_file: "${SSH_IDENTITY_FILE:-~/.ssh/id_ed25519}"
  local_port: "${SSH_LOCAL_PORT:-18080}"
  remote_host: "${SSH_REMOTE_HOST:-127.0.0.1}"
  remote_port: "${SSH_REMOTE_PORT}"

api:
  path: "${API_PATH}"
  data_path: "${API_DATA_PATH:-data}"

storage:
  output_dir: "${STORAGE_OUTPUT_DIR:-./out}"
  dataset_name: "${STORAGE_DATASET_NAME:-usage_events}"
```

Usage monitor должен быть доступен с удаленного сервера по адресу:

```text
http://127.0.0.1:9108/export/usage-events
```

Локально тул будет ходить к нему через SSH tunnel:

```text
http://127.0.0.1:18080
```

## 4. Подготовить SQL-запросы

Отредактировать `queries/report.sql`.

Разрешены только read-only запросы: `SELECT` или `WITH`.

Пример:

```sql
SELECT COUNT(*) AS row_count FROM usage_events;

SELECT *
FROM usage_events
LIMIT 10;
```

Имя таблицы должно совпадать со значением `storage.dataset_name`, сейчас это `usage_events`.

## 5. Сначала проверить ETL без Claude

Этот шаг проверяет SSH, usage monitor, лимиты, SQL-запросы и отправку в Telegram. CSV/SQLite создаются временно и удаляются после отправки. Прямой ETL отправляет обычную детерминированную сводку без агентского вступления.

```bash
set -a
source .env
set +a

.venv/bin/python -c "from etl_tool.pipeline import run_pipeline; print(run_pipeline('configs/pipeline.yaml', 'queries/report.sql').model_dump_json(indent=2))"
```

## 6. Запустить Claude agent

Агент собирает те же данные, генерирует короткий ироничный комментарий на русском по фактам из отчёта и отправляет финальное сообщение в Telegram. Python добавляет неизменяемую сводку пайплайна; модель её не переписывает.

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

## 7. Опционально: проверить через LiteLLM

Запустить proxy:

```bash
cd litellm
docker compose --env-file ../.env up -d
cd ..
```

Запустить агента через proxy:

```bash
ANTHROPIC_BASE_URL="$LITELLM_BASE_URL" \
ANTHROPIC_API_KEY="${LITELLM_AGENT_KEY:-$LITELLM_MASTER_KEY}" \
.venv/bin/python -m etl_tool.agent \
  --config configs/pipeline.yaml \
  --queries queries/report.sql
```

Получить spend logs:

```bash
.venv/bin/etl-spend-logs --limit 20
```

## Рекомендуемый порядок завтра

1. Установить зависимости.
2. Заполнить `.env`.
3. Создать `configs/pipeline.yaml` и `litellm/config.yaml`.
4. Запустить LiteLLM, если агент должен ходить через proxy.
5. Проверить ETL напрямую через шаг 5.
6. Запустить `etl-agent`.
