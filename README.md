# Restricted ETL Agent

Python tool for a Claude Agent SDK custom agent that sends a daily Russian Telegram report for CLIProxyAPI usage.

1. Start LiteLLM proxy with Postgres for model routing and Admin UI.
2. Open an SSH local port-forward to the remote `cliproxy-usage-monitor`.
3. Export usage events for the current calendar day from `/export/usage-events`.
4. Query the temporary SQLite copy with read-only SQL.
5. Fetch Codex/ChatGPT quota limits through CLIProxyAPI Management API.
6. Let the Claude agent generate only a short Russian ironic intro based on the collected facts.
7. Send the final analytical Telegram message with bold section headers.
8. Delete temporary CSV/SQLite files after the run.

The agent is intentionally narrow: it exposes only `run_etl_pipeline` and `send_telegram_report`. Built-in file, shell, and delete-capable actions are denied by SDK permissions and a `PreToolUse` hook.

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
cp configs/pipeline.example.yaml configs/pipeline.yaml
cp litellm/config.example.yaml litellm/config.yaml
```

Edit `.env`. Required values:

```env
ANTHROPIC_API_KEY=...          # upstream provider key used by LiteLLM
LITELLM_MASTER_KEY=...
LITELLM_AGENT_KEY=...          # optional; use a dedicated LiteLLM key for the agent
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

The default ETL target is:

```env
SSH_REMOTE_PORT=9108
API_PATH="/export/usage-events?since={since_utc}&until={until_utc}&format=json"
API_DATA_PATH=data
STORAGE_DATASET_NAME=usage_events
REPORT_TIMEZONE=Europe/Moscow
```

Start LiteLLM and Postgres:

```bash
cd litellm
docker compose --env-file ../.env up -d
cd ..
```

If LiteLLM has separate user or service-account keys, run the agent with that dedicated key in `LITELLM_AGENT_KEY`. Use `LITELLM_MASTER_KEY` only for bootstrap or admin workflows.

## Manual Run

Run the full agent through LiteLLM. This mode lets the agent add a short ironic Russian intro before sending the Telegram report. The factual summary is appended by Python code and is not rewritten by the model:

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

Run only the ETL pipeline without the Claude agent. This sends the deterministic report without the agent-written intro:

```bash
set -a
source .env
set +a

.venv/bin/python -c "from etl_tool.pipeline import run_pipeline; print(run_pipeline('configs/pipeline.yaml', 'queries/report.sql').model_dump_json(indent=2))"
```

Fetch LiteLLM spend logs:

```bash
set -a
source .env
set +a

.venv/bin/etl-spend-logs --limit 20
```

The LiteLLM Admin UI is available at `LITELLM_BASE_URL` with `/ui` appended, for example `http://localhost:4000/ui`.

## Telegram Format

Lines that start with `#` in the generated report are rendered as bold headings in Telegram.
The `#` marker itself is not shown. The agent-written intro is plain text at the top of the message. Example:

```text
Сегодня статистика выглядит так, будто токены устроили корпоратив без бюджета: ошибок нет, но latency явно просила отпуск.

#Лимиты Codex/ChatGPT:
План: Pro.
#Сводка по использованию за день: 2026-06-27 (Europe/Moscow)
```

## Safety Model

- The custom tool accepts paths only for the pipeline config and SQL query file.
- The MCP server is bound to the CLI-provided config/query paths; model-supplied alternative paths are rejected.
- The SSH command is built as an argument list, never through a shell.
- API extraction uses only `GET` and only through the SSH tunnel.
- SQL statements must be `SELECT` or `WITH`; destructive keywords are rejected.
- SQLite is reopened in read-only mode for report queries.
- Local writes are limited to `output_dir` from the config and temporary CSV/SQLite files are deleted after the run.
- The Claude agent gets only the MCP tool, plus a hook that denies delete/destructive tool use.
- The model generates only the intro; the immutable pipeline summary is appended by `send_telegram_report`.
- Structured output is a Pydantic JSON schema (`AgentRunReport`).

## Levels

- Min: read-only/restricted Claude Agent SDK agent, custom tool, delete blocked by hook.
- Medium: structured Pydantic output and optional LiteLLM proxy endpoint.
- Hard: LiteLLM fallback config and `/spend/logs` client.
