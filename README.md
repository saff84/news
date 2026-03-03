## News Intelligence Parser (MVP scaffold)

Production-oriented scaffold for a modular news ingestion + reporting system:
- Backend: Python 3.11, FastAPI, SQLAlchemy 2, Alembic
- DB: PostgreSQL
- Queue: Redis + RQ (worker + scheduler)
- Frontend: React + TS + Vite + Tailwind (RU UI)

### Quick start (dev)

1) Start stack:

```bash
docker compose up --build
```

2) Open:
- Admin UI: `http://localhost:5173`
- API docs (OpenAPI): `http://localhost:8000/docs`

3) Create first Admin (dev only)
- On the Login page click **"Создать первого Admin (только dev)"**
- This calls `POST /api/admin/bootstrap` which is enabled only when:
  - `APP_ENV != prod|production`
  - there are **no users** yet

4) Login, then add Regions in UI (manual)

### What is implemented now
- **Auth**: JWT access + refresh rotation, roles: Admin/Analyst/Viewer
- **RBAC**: write operations are Admin-only (regions)
- **Audit logs**: `audit_logs` table + writes for regions and bootstrap
- **DB schema + migrations**:
  - `0001_init_auth`: users/refresh_tokens/audit_logs
  - `0002_domain_schema`: regions/competitors/sources/parsing_templates/rss_state/tg_state/news_items/clusters/indicators/reports
- **Admin UI**:
  - Login + dev bootstrap
  - Regions CRUD (Admin-only writes)
- **Workers**:
  - Scheduler loop enqueues due sources based on frequency/backoff
  - `fetch_source` job runs real ingestion for RSS/HTML/SITEMAP/Telegram and writes into `news_items` (de-dup by canonical_url)
- **Template dry-run**:
  - `POST /api/templates/test` (Admin) fetches URL and extracts fields using provided template JSON
- **Indicators (MOEX)**:
  - CNY→RUB курс (CNYRUB_TOM) собирается планировщиком и отображается в Admin UI (раздел “Индикаторы”)

### System architecture (current)

```
                 +-------------------+
   React Admin   |  FastAPI backend  |
  (Vite/Tailwind)|  /api/* + OpenAPI |
        |        +----+----------+---+
        |             |          |
        |             |          +------------------+
        |             |                             |
        v             v                             v
   Browser       PostgreSQL                     Redis (RQ)
                 (metadata,                     (jobs queue)
                 items, states)                     |
                                                     v
                                           worker: fetch_source()
                                           scheduler: enqueue_due_sources()
```

### Notes
- **PDF export / Playwright** is not wired yet in this MVP scaffold.
- Telegram ingestion requires a one-time session authorization (Telethon) before workers can read channels.
  - Run: `docker compose run --rm tg-auth` (interactive; saves session into `tgdata` volume)
- To proceed next: clustering, reporting, PDF export.

