FROM python:3.12 AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

RUN python -m venv .venv
COPY pyproject.toml ./
RUN .venv/bin/pip install .

FROM python:3.12-slim
WORKDIR /app
COPY --from=builder /app/.venv .venv/
COPY fastembed_cache ./fastembed_cache/
COPY data ./data/
COPY static ./static/
COPY *.py .
CMD ["/app/.venv/bin/gunicorn", "--bind=0.0.0.0:8080", "app:app"]
