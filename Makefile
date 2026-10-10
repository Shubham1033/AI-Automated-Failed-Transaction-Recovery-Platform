.PHONY: dev api web test seed clean

dev:
	docker compose up --build

api:
	cd backend && uvicorn app.main:app --reload --port 8000

web:
	cd frontend && npm run dev

test:
	python -m unittest discover -s backend/tests -v

seed:
	cd backend && python -m app.cli seed --count 100 --seed 42

clean:
	find . -type d -name __pycache__ -prune -exec rm -r {} +

