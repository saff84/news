## News Intelligence Parser (MVP scaffold)

Production-oriented scaffold for a modular news ingestion + reporting system:

- Backend: Python 3.11, FastAPI, SQLAlchemy 2, Alembic
- DB: PostgreSQL
- Queue: Redis + RQ (worker + scheduler)
- Frontend: React + TS + Vite + Tailwind (RU UI)

### Quick start (dev)

1. Start stack:

```bash
docker compose up --build
```

[http://localhost:5173](http://localhost:5173)
2) Open:

- Admin UI: `http://localhost:5173`
- API docs (OpenAPI): `http://localhost:8000/docs`

1. Create first Admin (dev only)

- On the Login page click **"Создать первого Admin (только dev)"**
- This calls `POST /api/admin/bootstrap` which is enabled only when:
  - `APP_ENV != prod|production`
  - there are **no users** yet

1. Login, then add Regions in UI (manual)

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
  - `fetch_source` job runs real ingestion for RSS/HTML/SITEMAP/Telegram/MAX/VK and writes into `news_items` (de-dup by canonical_url)
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

### Сбор, обработка и генерация PDF

#### Сбор данных

**Источники** (RSS, HTML, SITEMAP, Telegram, MAX, VK) парсятся планировщиком по расписанию:

- Частота задаётся для каждого источника (`fetch_frequency_min`, по умолчанию 60 мин)
- Планировщик проверяет очередь каждые 10 сек (`SCHEDULER_SLEEP_SECONDS`)
- Worker выполняет `fetch_source`: загрузка → парсинг → запись в `news_items` (дедупликация по `canonical_url`)

**Новости** (`news_items`): `title`, `snippet`, `content_text`, `published_at`, `url`, `source_id`, `region_ids`, `topic_tags`, `competitor_mentions`.

**Индикаторы**:

- CNY→RUB (MOEX) — собирается планировщиком (~раз в час), пишется в `indicators_daily`
- Произвольные показатели — импорт из PDF/изображений через раздел «Индикаторы», пишется в `parsed_indicators`

**Регионы** — создаются вручную в Admin UI.

#### Обработка

- **Тегирование**: `region_ids`, `topic_tags`, `competitor_mentions` — по правилам в `tagging/rules.py`
- **Дедупликация**: simhash + `canonical_url`
- **Кластеры похожих новостей**: таблица `news_item_clusters`; пересборка по simhash (Hamming ≤ 3, окно ~90 дней, размер кластера ≥ 2). Планировщик может ставить задачу в очередь с интервалом `NEWS_CLUSTER_REBUILD_INTERVAL_S` (по умолчанию 21600 с, `0` — отключить). Вручную: `POST /api/diagnostics/rebuild-news-clusters` (Admin) или кнопка в UI «Диагностика».
- **ИИ** (OpenRouter / RouterAI): для каждого раздела — промпт + данные за период, в т.ч. `prompt_clusters` для саммари по кластерам. Валидация запроса (api_key, model, prompt, data) и ответа (choices, message, content). Раздел «Подключение ИИ».

#### Период и вход в PDF

- **Период** задаётся в «Отчёт для PDF» (`date_range_days`, по умолчанию 30 дней), опционально **месяц** `YYYY-MM` (строгая фильтрация новостей)
- **Разделы отчёта** (вкл/выкл): новости (общие / конкуренты), кластеры похожих новостей, индикаторы, регионы
- **Поток с ИИ**:
  1. Сбор данных за период по каждому разделу; индикаторы из `parsed_indicators` за тот же период
  2. Кластеры: только те, у которых `primary_item_id` входит в набор новостей отчёта
  3. В каждый раздел: промпт (из `ai_config`) + сериализованные данные
  4. Ответы ИИ попадают в `processed_`* (в т.ч. `processed_clusters` при заданном `prompt_clusters`)
- **PDF/HTML**: `POST /api/reports/generate-pdf` и `POST /api/reports/generate-html` (ReportLab и шаблон HTML на бэкенде). При вызове **без** `processed_`* отчёт строится из сырых данных; после `POST /api/reports/generate` фронт может передать `processed_*` в `generate-pdf`, чтобы в файл попали те же выводы ИИ, что в превью
- **Шапка/подвал**: из `report_config`

### Notes

- **Telegram ingestion** requires one-time session authorization (Telethon):
  - `docker compose run -it --rm tg-auth` — интерактивный ввод кода (код приходит в приложение Telegram, не SMS)
  - tg-auth не запускается при `docker compose up` (профиль `manual`), только по запросу
  - Альтернатива: `python backend/scripts/generate_telegram_session_qr.py` — вход по QR (Настройки → Устройства)
- **MAX ingestion**:
  - добавьте source с типом `MAX_CHANNEL`
  - укажите `settings_json.max_channel_id` (ID канала/чата)
  - укажите токен бота через `MAX_BOT_TOKEN` (или в `settings_json.max_bot_token` для конкретного источника)
  - в UI есть раздел **MAX-парсер**: сохранение токена, проверка `/bots`, тест чтения `/messages`
- **VK ingestion**:
  - добавьте source с типом `VK_GROUP`
  - укажите `settings_json.vk_group_id` (например: `public123456`, `club123456`, `123456` или domain)
  - укажите токен через `VK_ACCESS_TOKEN` (или `settings_json.vk_access_token` для конкретного источника)
  - в UI есть раздел **VK-парсер**: сохранение токена, проверка токена и тестовый fetch `wall.get`

