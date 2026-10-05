# Contributing

Thanks for your interest! Before opening a pull request:

1. Fork the repository and create a branch from `main`.
2. Backend: run `ruff check .` and `pytest` in `backend/`. Frontend: run `npm run lint` and `npm test` in `frontend/`.
3. If you change the data model, add an Alembic migration (`alembic revision --autogenerate`). CI checks that models and migrations match.
4. Add tests. Parsers are tested with recorded responses; the Gemini client is always mocked, never called for real.
5. Never include keys or `.env` files in commits or issues.

Code, comments and documentation are written in English.
