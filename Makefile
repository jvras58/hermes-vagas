.PHONY: install test scan scan-commit build up down logs

install:
	python -m pip install -e .

test:
	PYTHONPATH=src python -m unittest discover -s tests -v

scan:
	PYTHONPATH=src python -m job_hunter.main scan --source mock --dry-run

scan-commit:
	PYTHONPATH=src python -m job_hunter.main scan --source mock --commit

build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

