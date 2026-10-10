# Sprint 2 — Production Infrastructure

## Added
- PostgreSQL via SQLAlchemy 2 with Alembic migration `0001`.
- Redis/Celery delayed reconciliation and accelerated demo-time scheduling.
- Simulation-first `PaymentStatusGateway` plus Razorpay status adapter.
- JWT authentication and RBAC (`viewer`, `operator`, `reviewer`, `admin`).
- Simulated email adapter plus Meta email Cloud API sandbox adapter.
- Playwright browser smoke test.
- Docker Compose topology: Postgres, Redis, migration job, API, worker, web.
- Render deployment blueprint.

## Local demo
```bash
docker compose up --build
```
Login: `admin@revive.local` / `ChangeMe123!` (development only; change in production).

The default remains `RAZORPAY_USE_API=false` and `MESSAGING_PROVIDER=simulated`, so the full benchmark is safe and reproducible without external credentials.
