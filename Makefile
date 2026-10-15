.PHONY: test test-postgres check migrate work

test:
	cd backend && ../.venv/bin/python manage.py test

check:
	.venv/bin/python backend/manage.py check
	.venv/bin/python backend/manage.py makemigrations --check --dry-run
	.venv/bin/python -m pip check

migrate:
	.venv/bin/python backend/manage.py migrate

work:
	.venv/bin/python backend/manage.py process_work

test-postgres:
	.venv/bin/python scripts/test_postgres.py
