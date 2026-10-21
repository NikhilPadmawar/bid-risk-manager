# Bid Risk Manager

A small FastAPI service for tracking client bids. Phase 1 (this release) is a complete CRUD API with a database, CSV import, validation, logging, tests and a Docker setup. Phase 2 will add an AI agent that assesses how risky each bid is.

## Problem

Our team bids on many client proposals, but bid details (value, cost, deadline, client history) are scattered across spreadsheets and documents, so nobody can say which bids are risky. This service gives bids one home and a clean API, and is the base for automatic risk assessment.

## What Phase 1 includes

- CRUD API for clients and bids (create, list with filters, view, update, delete)
- Bulk import of bids from a CSV file, with bad rows skipped and reported
- Request validation and one consistent JSON error format
- Request logging to console and file
- 19 automated tests
- Docker image for running locally

## Tech stack

Python 3.12, FastAPI, Pydantic, SQLAlchemy, SQLite, uv, pytest, Docker.

## Quick start (local)

Prerequisite: [uv](https://docs.astral.sh/uv/) installed. uv downloads the right Python version for you.

```bash
git clone https://github.com/NikhilPadmawar/bid-risk-manager.git
cd bid-risk-manager
uv sync
cp .env.example .env
uv run uvicorn app.main:app --reload
```

Open http://localhost:8000/docs for the interactive API page (Swagger UI), where every endpoint can be tried from the browser. Tables are created automatically on startup in a local `bids.db` file.

To load the 16 sample bids, call `POST /import/bids` on that page.

## Configuration

Settings are read from environment variables or a `.env` file (copy `.env.example`).

| Variable | Default | Purpose |
| --- | --- | --- |
| `APP_NAME` | Bid Risk Manager | Title shown in the API docs |
| `DATABASE_URL` | `sqlite:///./bids.db` | Database location |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING` or `ERROR` |
| `LOG_FILE` | `app.log` | Where logs are written |
| `BIDS_CSV_PATH` | `data/bids.csv` | File used by the CSV import |

Restart the server after changing `.env`.

## API

| Method | Path | Description |
| --- | --- | --- |
| GET | `/health` | Health check |
| POST | `/clients` | Create a client (409 if the name already exists) |
| POST | `/bids` | Create a bid for an existing client |
| GET | `/bids` | List bids. Optional filters: `status`, `client_id` |
| GET | `/bids/{id}` | View one bid |
| PUT | `/bids/{id}` | Update a bid. Only the fields you send change |
| DELETE | `/bids/{id}` | Delete a bid |
| POST | `/import/bids` | Import bids from the CSV file |

Bid status is one of `draft`, `submitted`, `won`, `lost`.

Example: `GET /bids?status=submitted&client_id=1`

### Errors

Every error uses the same shape:

```json
{"error": "not_found", "message": "Bid 999 not found"}
```

Validation errors (422) add a `details` list naming each bad field. Unexpected failures return a generic 500 message, and the full traceback goes to the log only.

### CSV import

`data/bids.csv` has these columns:

```
client_name,industry,past_bids_won,past_bids_lost,title,value,estimated_cost,deadline,status,notes
```

- Clients are created by name the first time they appear.
- Invalid rows are skipped and listed in the response with their line number.
- A bid with the same client and title is treated as a duplicate and skipped, so the import can be run safely more than once.

Example response: `{"created": 16, "duplicates": 0, "errors": []}`

## Tests

```bash
uv run pytest -v
```

Tests run against a throwaway in-memory database, so they never touch `bids.db`.

## Docker

```bash
docker build -t bid-risk-manager .
docker run --rm -p 8000:8000 -v bid-data:/data -e DATABASE_URL=sqlite:////data/bids.db bid-risk-manager
```

Then open http://localhost:8000/docs. The `-v bid-data:/data` volume keeps the database between runs. Remove that option for a fresh, empty database each time.

## Project structure

```
app/
  main.py             app setup, request logging, routers
  config.py           settings from .env
  logger.py           logging setup
  database.py         database engine and session
  models.py           SQLAlchemy tables (Client, Bid)
  schemas.py          Pydantic request and response shapes
  exceptions.py       custom error types
  decorators.py       database error handling decorator
  error_handlers.py   consistent JSON error responses
  routers/            clients, bids and import endpoints
  services/           CSV import logic
data/bids.csv         sample data
tests/                pytest test suite
Dockerfile
```

## Phase 2 (planned)

An agent that assesses each bid and explains the risk. Not built yet.

- A rule-based risk score as a baseline: margin under 15%, deadline under 7 days, or a client with 2 or more lost bids
- Agent tools for looking up a bid, client history, margin and deadline
- A LangChain agent using an LLM through OpenRouter
- `POST /bids/{id}/assess` returning a structured risk report (score, level, reasons, recommendation)
- Assessment history and a portfolio summary of the riskiest open bids

## Scope

Out of scope for now: authentication, a frontend (the Swagger page serves as the UI) and cloud deployment.
