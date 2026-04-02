FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml README.md /app/
COPY mcp_server /app/mcp_server

RUN python -m pip install --upgrade pip && python -m pip install .

EXPOSE 8000

CMD ["python", "-m", "mcp_server"]
