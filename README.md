# Life alert

Django REST backend foundation for the Life alert care/response service. The Android/iOS client foundation uses Flutter under `frontend/mobile`; its routes currently use shared placeholders.

Start with [the product requirements](docs/PRD.md) and [the backend/API guide](docs/BACKEND.md). This foundation has **simulated providers only**; it does not operate a live emergency, payment or messaging service.

## Local setup

Tested with Python 3.14.6. Python 3.12–3.14 is the recommended project range. Exact installed dependencies are pinned in `requirements.txt`.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cd backend
../.venv/bin/python manage.py migrate
../.venv/bin/python manage.py createsuperuser
../.venv/bin/python manage.py runserver 127.0.0.1:8000
```

In another terminal, from `backend/`:

```sh
../.venv/bin/python manage.py test
../.venv/bin/python manage.py check
../.venv/bin/python manage.py makemigrations --check --dry-run
../.venv/bin/python manage.py process_work
```

Run `process_work` manually to consume durable simulated notification/EMS work, review configured response fallbacks and expire unaccepted offers/reservations. No periodic scheduler or external provider is enabled. Liveness: `/health/`; database/migration readiness: `/health/ready/`. API base: `/api/v1/`. Run `make schema` to validate the OpenAPI contract in `docs/openapi.yaml`.

SQLite is for single-process local exploration. PostgreSQL is required to validate row locking and concurrent operational workflows. See the backend guide for configuration and tests. Do not use real child data in local development.

Settings read environment variables directly; `.env.example` is a reference, not an automatically loaded file. Keep actual `.env`, database, media, credentials and `.venv` out of Git. No default account or active subscription is seeded. With existing local PostgreSQL tools, `make test-postgres` runs the complete suite in a temporary socket-only cluster and cleans it up afterward.

The repository lives on `/Volumes/ANDRE_DEV/Projects/Life-alert`; the previous `/Users/macbook/Developer/Life-alert` path is a compatibility symlink. Keep the SSD mounted while working. The relocation backup predates implementation and is not a current code backup.
