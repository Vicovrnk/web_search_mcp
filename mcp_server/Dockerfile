FROM python:3.12-slim

ARG PYTHON_INSTALL_VERIFY_SSL=true

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml README.md /app/
COPY mcp_server /app/mcp_server

RUN set -eux; \
    pip_trusted_hosts=""; \
    if [ "${PYTHON_INSTALL_VERIFY_SSL}" = "false" ]; then \
        pip_trusted_hosts="--trusted-host pypi.org --trusted-host files.pythonhosted.org"; \
    fi; \
    python -m pip install --upgrade pip ${pip_trusted_hosts}; \
    python -m pip install ${pip_trusted_hosts} .

EXPOSE 8000

CMD ["python", "-m", "mcp_server"]
