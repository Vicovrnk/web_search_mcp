FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

ARG WIKIPEDIA_MCP_VERSION=2.0.0
RUN python -m pip install --upgrade pip \
    && python -m pip install --no-cache-dir "wikipedia-mcp==${WIKIPEDIA_MCP_VERSION}"

EXPOSE 8080

CMD ["wikipedia-mcp", "--transport", "streamable-http", "--host", "0.0.0.0", "--port", "8080", "--path", "/mcp"]
