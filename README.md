# MRUDA — Modular Real-time Unified Data Analyzer

> Pull Meta ad data → Normalize → Analyze → Generate structured intelligence

## Quick Start

### Local Development (SQLite)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env with your Meta token and ad account ID

# 3. Run server
uvicorn app.main:app --reload --port 8000
```

### Docker (PostgreSQL)

```bash
docker-compose up --build
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/run-analysis` | Trigger full pipeline |
| `GET` | `/insights/latest` | Get latest insight |
| `GET` | `/insights?date=YYYY-MM-DD` | Get historical insights |
| `GET` | `/health` | Health check |
| `GET` | `/meta/validate-token` | Validate Meta token |
| `GET` | `/meta/account-info` | Get ad account info |
| `POST` | `/generate-summary` | Generate AI narrative (optional) |

## Run Analysis

```bash
# Last 7 days (default)
curl -X POST http://localhost:8000/run-analysis \
  -H "Content-Type: application/json" \
  -d '{"date_range": "last_7d"}'

# Custom date range
curl -X POST http://localhost:8000/run-analysis \
  -H "Content-Type: application/json" \
  -d '{"start_date": "2026-02-01", "end_date": "2026-02-18"}'
```

## Architecture

```
Connectors → Raw Store → Normalizer → Metric Registry → Analyzer Engines → Versioned Output → AI (optional)
```

## Docs

Visit `http://localhost:8000/docs` for interactive Swagger UI.
