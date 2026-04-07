FROM python:3.12-slim

ARG PYTHON_INSTALL_VERIFY_SSL=true

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

ARG WIKIPEDIA_MCP_VERSION=2.0.0
RUN set -eux; \
    pip_trusted_hosts=""; \
    if [ "${PYTHON_INSTALL_VERIFY_SSL}" = "false" ]; then \
        pip_trusted_hosts="--trusted-host pypi.org --trusted-host files.pythonhosted.org"; \
    fi; \
    python -m pip install --upgrade pip ${pip_trusted_hosts}; \
    python -m pip install ${pip_trusted_hosts} --no-cache-dir "wikipedia-mcp==${WIKIPEDIA_MCP_VERSION}"

EXPOSE 8080

CMD ["wikipedia-mcp", "--transport", "streamable-http", "--host", "0.0.0.0", "--port", "8080", "--path", "/mcp"]
