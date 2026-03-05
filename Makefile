.PHONY: dev
dev:
	uv run app.py

.PHONY: prod
prod: container
	docker run -p 8080:8080 matchmaking-experiment

.PHONY: container
container:
	docker build -t matchmaking-experiment .

.PHONY: deploy
deploy:
	uv run download_model.py
	fly deploy
