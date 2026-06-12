# Freight Copilot — Runbook

Operating runbook for day-to-day use, development, and troubleshooting.

---

## Start and Stop

### Start the demo environment (first time or after reseed)

```bash
cd /home/user/doomdoja-ai/freight-copilot
make demo
```

This command:
1. Creates a Python 3.11+ virtual environment at `backend/.venv` if it does not exist
2. Installs all Python dependencies from `backend/requirements.txt`
3. Runs `scripts/seed_demo.py` to (re)create `freight.db` with synthetic demo data
4. Starts `uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload`

Open **http://127.0.0.1:8000** in your browser when you see:
```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

### Start without reseeding (use existing DB)

```bash
cd /home/user/doomdoja-ai/freight-copilot
make dev
```

### Stop

Press **Ctrl+C** in the terminal running uvicorn. The process exits cleanly.

---

## Database Operations

### Location of the database file

```
backend/freight.db        # SQLite (default)
```

When `DATABASE_URL` is set to a PostgreSQL DSN, no local file is used.

### Reseed demo data (destroys all current data)

```bash
make reseed
```

Or directly:

```bash
cd backend
python scripts/seed_demo.py --drop-and-recreate
```

This drops all tables, re-creates them from the current SQLAlchemy models, and inserts all fixture data from `fixtures/`.

### Apply schema migrations (Alembic)

```bash
cd backend
alembic upgrade head
```

To generate a new migration after changing a model:

```bash
alembic revision --autogenerate -m "describe the change"
alembic upgrade head
```

### Backup the SQLite database

```bash
cp backend/freight.db backend/freight.db.bak.$(date +%Y%m%d-%H%M%S)
```

For PostgreSQL, use `pg_dump`:

```bash
pg_dump "$DATABASE_URL" > backup_$(date +%Y%m%d-%H%M%S).sql
```

---

## Running Tests

### All tests

```bash
cd backend
pytest
```

### With coverage report

```bash
pytest --cov=app --cov-report=term-missing
```

### Agent unit tests only

```bash
pytest tests/agents/
```

### API integration tests only

```bash
pytest tests/api/
```

### Run a specific test file

```bash
pytest tests/agents/test_pricing_agent.py -v
```

Tests use `MockProvider` for the LLM layer and `MockTimocomAdapter` / `MockTransEuAdapter` / `MockEmailAdapter` for all external services. No network calls are made during tests.

---

## Environment Variables and Feature Flags

All configuration is controlled via environment variables. Copy `backend/.env.example` to `backend/.env` and edit as needed.

### Core configuration

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./freight.db` | SQLAlchemy DSN. Set to `postgresql+asyncpg://user:pass@host/db` for Postgres |
| `SECRET_KEY` | `change-me-in-production` | Session signing key — change before any non-local deployment |
| `LOG_LEVEL` | `INFO` | Python logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `TIMEZONE` | `Europe/Warsaw` | Timezone for display and scheduling |

### Feature flags (all default to `false` or `true` as shown)

| Variable | Default | Effect when `true` |
|---|---|---|
| `DEMO_MODE` | `true` | Shows demo banner; uses fixture data labels; disables destructive actions |
| `EXTERNAL_READS_ENABLED` | `false` | Allows adapter read calls (exchange data fetching) |
| `EXTERNAL_WRITES_ENABLED` | `false` | Allows adapter write calls (publish, send) after human approval |
| `TIMOCOM_ENABLED` | `false` | Activates real `TimocomAdapter` instead of mock |
| `TRANSEU_ENABLED` | `false` | Activates real `TransEuAdapter` instead of mock |
| `EMAIL_ENABLED` | `false` | Activates real `ImapEmailAdapter` and `SmtpEmailAdapter` instead of mock |
| `TRACKING_ENABLED` | `false` | Activates real tracking data adapter instead of mock |
| `LOCAL_LLM_ENABLED` | `false` | Activates `LocalOpenAIProvider` for agent LLM calls |
| `ANTHROPIC_LLM_ENABLED` | `false` | Activates `AnthropicProvider` for agent LLM calls |

### LLM configuration (only relevant if an LLM flag is `true`)

| Variable | Default | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | _(unset)_ | Required when `ANTHROPIC_LLM_ENABLED=true` |
| `LOCAL_LLM_BASE_URL` | `http://localhost:11434/v1` | Base URL for local OpenAI-compatible endpoint |
| `LOCAL_LLM_MODEL` | `mistral` | Model name to pass to the local endpoint |

### Exchange adapter credentials (only relevant if exchange flags are `true`)

| Variable | Description |
|---|---|
| `TIMOCOM_API_KEY` | API key for TIMOCOM official API |
| `TIMOCOM_COMPANY_ID` | Company identifier for TIMOCOM |
| `TRANSEU_CLIENT_ID` | OAuth client ID for Trans.eu API |
| `TRANSEU_CLIENT_SECRET` | OAuth client secret for Trans.eu API |

### Email adapter credentials (only relevant if `EMAIL_ENABLED=true`)

| Variable | Description |
|---|---|
| `EMAIL_IMAP_HOST` | IMAP server hostname |
| `EMAIL_IMAP_PORT` | IMAP port (typically 993 for IMAPS) |
| `EMAIL_IMAP_USERNAME` | IMAP login username |
| `EMAIL_IMAP_PASSWORD` | IMAP password or app password |
| `EMAIL_SMTP_HOST` | SMTP server hostname |
| `EMAIL_SMTP_PORT` | SMTP port (typically 587 for STARTTLS) |
| `EMAIL_FROM_ADDRESS` | From address for outbound emails |

---

## Where Data and Logs Live

| Location | Contents |
|---|---|
| `backend/freight.db` | SQLite database (all application data) |
| `backend/logs/app.log` | Application log (when `LOG_FILE` env var is set) |
| `backend/logs/audit.log` | Agent audit log entries (JSON-lines format) |
| `fixtures/` | Synthetic demo seed data (JSON files) |
| `backend/.env` | Local environment variable overrides (not committed to git) |

Logs are written to stdout by default. To write to a file, set `LOG_FILE=backend/logs/app.log`.

---

## Enabling a Real Adapter Safely

Follow this sequence when transitioning from mock to a real exchange adapter.

### Pre-conditions (complete all before touching flags)

1. Obtain official API credentials from the exchange (TIMOCOM or Trans.eu). Do not use unofficial endpoints.
2. Review the exchange's API documentation for rate limits, authentication flow, and terms of service.
3. Set credentials in `backend/.env` (never in code or committed files).
4. Verify credentials work: run the adapter's built-in connectivity check:
   ```bash
   cd backend
   python -m app.adapters.timocom --check-connection
   ```
5. Ensure `EXTERNAL_WRITES_ENABLED` remains `false`. Enable reads first.

### Enable read-only access

```bash
# In backend/.env
TIMOCOM_ENABLED=true
EXTERNAL_READS_ENABLED=true
EXTERNAL_WRITES_ENABLED=false   # keep false
DEMO_MODE=false
```

Restart the server (`make dev`). Verify in the UI that live data appears with a "LIVE" indicator (not the "DEMO" badge).

### Smoke-test read operations

- Open Opportunity Inbox: confirm offers load without errors
- Check application logs for any adapter errors
- Monitor rate-limit headers in debug logs (`LOG_LEVEL=DEBUG`)

### Enable write operations (advanced — do not rush)

Write operations are gated by both `EXTERNAL_WRITES_ENABLED=true` AND a human-approved ApprovalRequest. Enabling the flag does not cause any writes — it only removes the dry-run override, so that when a human approves a request, the adapter call executes for real.

```bash
# In backend/.env — only after reads are stable and you understand the implications
EXTERNAL_WRITES_ENABLED=true
```

Restart the server. **From this point, approved ApprovalRequests will make real API calls.** Test with a low-stakes approval (e.g., a rate enquiry, not a booking confirmation).

---

## Troubleshooting

### App fails to start: "ModuleNotFoundError"

The virtual environment is not activated or dependencies are missing.

```bash
cd backend
python -m venv .venv
source .venv/bin/activate    # Linux/macOS
pip install -r requirements.txt
```

### App fails to start: "alembic.exc.CommandError: Can't locate revision"

The database schema is out of sync with the codebase. Run migrations:

```bash
cd backend
alembic upgrade head
```

If the database is a demo instance, it is faster to reseed: `make reseed`.

### "Database is locked" error (SQLite)

Two processes are writing to the database simultaneously. Stop all running instances of the app, then restart one.

```bash
# Find any running uvicorn processes
ps aux | grep uvicorn
# Kill if needed
kill <PID>
make dev
```

### Agent returns `success=False` with missing fields

This is expected behaviour when input data is incomplete. The agent logs the missing fields; the UI surfaces them as warnings. No action is needed unless the missing data is critical for the workflow.

### LLM calls time out or return parse errors

The LLM provider will set `safe_fallback=True` on the affected AgentResult. The agent returns a deterministic fallback response. Check:
- `ANTHROPIC_API_KEY` is set correctly
- Network connectivity to the Anthropic API endpoint
- `LOG_LEVEL=DEBUG` to see the raw LLM response and parse error

Fallback to deterministic mode by setting `ANTHROPIC_LLM_ENABLED=false` and restarting.

### Exchange adapter returns errors

Set `LOG_LEVEL=DEBUG` and restart. Adapter errors are logged with the HTTP status code and response body. Common causes:
- Expired or invalid API credentials
- Rate limit exceeded (check `Retry-After` header in logs)
- Exchange API maintenance window

The adapter will fall back to returning an empty result set (not mock data) when `EXTERNAL_READS_ENABLED=true` and the API call fails. Mock data is only used when the adapter is in mock mode.

### Demo data looks wrong or corrupted

Reseed from scratch:

```bash
make reseed
```

This is non-destructive to the codebase — only `freight.db` is affected.

### Port 8000 already in use

```bash
# Find what is using port 8000
lsof -i :8000
# Or change the port in the Makefile / start command
uvicorn backend.app.main:app --host 127.0.0.1 --port 8001
```

---

## Production Deployment Checklist

This checklist applies before deploying to any non-local environment.

- [ ] Set a strong random `SECRET_KEY` (at least 32 random bytes, base64-encoded)
- [ ] Set `DEMO_MODE=false`
- [ ] Switch `DATABASE_URL` to PostgreSQL
- [ ] Run `alembic upgrade head` against the production database before starting the app
- [ ] Set `LOG_LEVEL=WARNING` (or `ERROR`) for production; redirect logs to a file or log aggregator
- [ ] Ensure `backend/.env` is not committed to git and not readable by other OS users (`chmod 600 .env`)
- [ ] Confirm `EXTERNAL_WRITES_ENABLED=false` until you are ready to enable real writes
- [ ] Set up regular database backups (`pg_dump` on a cron schedule)
- [ ] Restrict network access to port 8000 — the app has no built-in TLS; put it behind a reverse proxy (nginx/caddy) with HTTPS
- [ ] Review all API credentials: exchange adapters, email, LLM — rotate any that were used during development
