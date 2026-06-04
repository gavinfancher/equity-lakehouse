FROM ghcr.io/astral-sh/uv:latest AS uv
FROM python:3.12-slim

COPY --from=uv /uv /uvx /bin/

WORKDIR /app
COPY pyproject.toml ./
RUN uv pip install --system --no-cache .

COPY main.py ./

ENTRYPOINT ["python", "main.py"]
