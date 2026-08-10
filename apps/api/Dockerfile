FROM python:3.14-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock README.md ./
COPY apps/api apps/api
COPY apps/cli apps/cli
COPY packages packages

RUN uv sync --frozen --all-packages --no-dev

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 6687

CMD ["uvicorn", "gamr_api.main:app", "--host", "0.0.0.0", "--port", "6687"]
