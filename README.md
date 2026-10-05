# MyNews

An AI-powered news feed. It aggregates Reuters (World, Technology), Ars Technica (AI, Biz & IT, Security) and the Hacker News front page, then uses Gemini to translate, describe and rank every story. The goal is a personalised "For You" feed that learns from what each reader finds interesting.

## Features

- **Ingestion**: concurrent, idempotent fetching with retries and backoff; deduplication by normalised URL and headline similarity. Hacker News follows [`/front`](https://news.ycombinator.com/front), the list of stories that made the front page each day, in the same order.
- **AI enrichment** (Gemini Flash-Lite, batched, once per article): translated headline, a short description in English and Spanish, topics and a global relevance score. Descriptions are written from the original article text and skipped when there is nothing beyond the headline.
- **Hacker News discussions**: full comment trees fetched on demand, stored as rows and rebuilt with a recursive SQL query; translated to Spanish on request.
- **Feedback**: thumbs up/down per story from an anonymous per-browser session, stored as the training signal for the upcoming For You feed.
- **Web app**: editorial layout, English/Spanish interface, light and dark themes, source and section filters.

## Stack

| Layer | Technology |
| --- | --- |
| Backend | Python 3.12, FastAPI, SQLAlchemy (async), Pydantic, httpx, APScheduler |
| Frontend | React, TypeScript, Vite |
| Data | PostgreSQL 16 + pgvector, Alembic |
| AI | Gemini API behind a provider-agnostic client with rate limiting and retries |
| Infra | Docker Compose, Caddy, GitHub Actions |

## Getting started

Requirements: Docker with Compose, and Node 22 for the frontend dev server.

```bash
cp .env.example backend/.env   # then set the passwords and GEMINI_API_KEY
docker compose -f infra/docker-compose.yml up --build
```

The API runs on http://localhost:8000 (interactive docs at `/docs`). The worker fetches the sources on startup and then on a schedule. If ports 5432 or 8000 are taken, run with `DB_PORT=5433 API_PORT=8001`.

Frontend:

```bash
cd frontend
npm install
npm run dev   # http://localhost:5173, proxies /api to http://localhost:8000
```

Set `VITE_API_TARGET=http://localhost:8001` if the API runs on another port.

## Tests

```bash
# Backend: needs PostgreSQL with pgvector (set TEST_DATABASE_URL)
cd backend && pip install -e ".[dev]" && ruff check . && pytest

# Frontend
cd frontend && npm run lint && npm test
```

Source parsers are tested against recorded responses and the Gemini client is always mocked.

## CI/CD

- **CI** runs on every push and pull request: backend lint and tests against PostgreSQL, migrations applied from scratch, frontend type checks, tests and build, and both Docker images.
- **Deploy** runs after CI passes on `main`: it publishes the images to GitHub Container Registry tagged with the commit SHA. Deploying to a server is opt-in; see the comments in `.github/workflows/deploy.yml`.

## Configuration

All settings come from environment variables; see [.env.example](.env.example). Never commit `backend/.env`.

## Roadmap

- [x] Multi-source ingestion and deduplication
- [x] Hacker News comment trees
- [x] Gemini enrichment and translation
- [x] Ratings from readers
- [ ] Embeddings and semantic search
- [ ] For You feed: interest profile, candidate scoring and re-ranking
- [ ] Ranking evals and A/B experiments
- [ ] Daily briefing agent and MCP server

## License

[MIT](LICENSE)
