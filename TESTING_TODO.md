# Testing TODO

What remains to test the restricted ETL agent end-to-end.

## 1. Install dependencies

```bash
cd /home/runemal/codex/claude_sdk/etl_tool
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## 2. Fill environment variables

```bash
cp .env.example .env
cp litellm/config.example.yaml litellm/config.yaml
```

Required values:

```bash
ANTHROPIC_API_KEY=...
LITELLM_MASTER_KEY=...
LITELLM_AGENT_KEY=... # optional dedicated LiteLLM key for the agent
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

Python commands load `.env` automatically. If an external process needs these variables directly, you can still load them with `set -a; source .env; set +a`.

## 3. Prepare pipeline config

```bash
cp configs/pipeline.example.yaml configs/pipeline.yaml
```

`configs/pipeline.yaml` can stay based on env references:

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

The usage monitor must be reachable from the remote server as:

```text
http://127.0.0.1:9108/export/usage-events
```

Locally, the tool will access it through the SSH tunnel at:

```text
http://127.0.0.1:18080
```

## 4. Prepare SQL queries

Edit `queries/report.sql`.

Only read-only statements are allowed: `SELECT` or `WITH`.

Example:

```sql
SELECT COUNT(*) AS row_count FROM usage_events;

SELECT *
FROM usage_events
LIMIT 10;
```

The table name must match `storage.dataset_name`; currently this is `usage_events`.

## 5. Test ETL without Claude first

This checks SSH, usage monitor export, quota fetch, SQL queries, and Telegram. CSV/SQLite files are temporary and deleted after sending. This direct ETL mode sends a deterministic report without the agent-written intro.

```bash
set -a
source .env
set +a

.venv/bin/python -c "from etl_tool.pipeline import run_pipeline; print(run_pipeline('configs/pipeline.yaml', 'queries/report.sql').model_dump_json(indent=2))"
```

## 6. Run the Claude agent

The agent collects the same data, generates a short Russian ironic intro based on the returned facts, then sends the final Telegram message. Python appends the immutable pipeline summary; the model does not rewrite it.

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

## 7. Optional: test through LiteLLM

Start proxy:

```bash
cd litellm
docker compose --env-file ../.env up -d
cd ..
```

Run agent through proxy:

```bash
ANTHROPIC_BASE_URL="$LITELLM_BASE_URL" \
ANTHROPIC_API_KEY="${LITELLM_AGENT_KEY:-$LITELLM_MASTER_KEY}" \
.venv/bin/python -m etl_tool.agent \
  --config configs/pipeline.yaml \
  --queries queries/report.sql
```

Fetch spend logs:

```bash
.venv/bin/etl-spend-logs --limit 20
```

## Recommended Order Tomorrow

1. Install dependencies.
2. Fill `.env`.
3. Create `configs/pipeline.yaml` and `litellm/config.yaml`.
4. Start LiteLLM if the agent should route through the proxy.
5. Verify ETL directly with step 5.
6. Run `etl-agent`.
