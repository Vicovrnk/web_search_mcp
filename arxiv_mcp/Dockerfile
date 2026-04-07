FROM python:3.11-slim-bookworm

ARG PYTHON_INSTALL_VERIFY_SSL=true

ENV PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ARXIV_STORAGE_PATH=/app/papers \
    ARXIV_MCP_HOST=0.0.0.0 \
    ARXIV_MCP_PORT=8080 \
    ARXIV_MCP_PATH=/mcp \
    ARXIV_MCP_STATELESS_HTTP=true

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates git \
    && rm -rf /var/lib/apt/lists/*

ARG ARXIV_UPSTREAM_REF=main

COPY app.py /app/app.py

RUN set -eux; \
    pip_trusted_hosts=""; \
    git_ssl_verify="true"; \
    if [ "${PYTHON_INSTALL_VERIFY_SSL}" = "false" ]; then \
        pip_trusted_hosts="--trusted-host pypi.org --trusted-host files.pythonhosted.org --trusted-host download.pytorch.org"; \
        git_ssl_verify="false"; \
    fi; \
    python -m pip install --upgrade pip ${pip_trusted_hosts}; \
    python -m pip install ${pip_trusted_hosts} --index-url "https://download.pytorch.org/whl/cpu" "torch"; \
    git -c http.sslVerify=${git_ssl_verify} clone --depth 1 --branch "${ARXIV_UPSTREAM_REF}" "https://github.com/blazickjp/arxiv-mcp-server.git" /tmp/arxiv-src; \
    python -m pip install ${pip_trusted_hosts} "fastmcp" "/tmp/arxiv-src[pdf]" "sentence-transformers" "numpy"; \
    rm -rf /tmp/arxiv-src

EXPOSE 8080

CMD ["python", "/app/app.py"]
