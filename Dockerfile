# Render / container entrypoint for meal-agent-api
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY packages ./packages
COPY apps/api ./apps/api
COPY apps/cli ./apps/cli
COPY apps/web/public/chefs ./apps/web/public/chefs
COPY profiles ./profiles

RUN pip install --upgrade pip \
    && pip install .

# Persistent Woolworths sessions / users (mount Render disk here)
RUN mkdir -p /app/data
VOLUME ["/app/data"]

ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn meal_agent_api.main:app --host 0.0.0.0 --port ${PORT}"]
