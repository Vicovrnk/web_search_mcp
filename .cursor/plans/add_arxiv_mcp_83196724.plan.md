---
name: Add arXiv MCP
overview: Добавить `arxiv-mcp-server` в Docker Compose как третий специализированный MCP endpoint для работы с научными статьями. План опирается на существующий шаблон `wikipedia-mcp`, с запуском по умолчанию и хранением статей в именованном Docker volume.
todos:
  - id: verify-arxiv-runtime
    content: "Подтвердить runtime-контракт upstream `mcp/arxiv-mcp-server`: transport, порт, path, storage env и подходящий healthcheck."
    status: completed
  - id: wire-compose-service
    content: Спроектировать новый сервис `arxiv-mcp` в `docker-compose.yml` с default host port `8002` и именованным volume для хранения статей.
    status: completed
  - id: document-endpoint
    content: Обновить README и `.env.example`, чтобы новый endpoint был виден в архитектуре, конфигурации и примере `mcpServers`.
    status: completed
  - id: add-arxiv-contract
    content: Добавить `contracts/specialized/arxiv.md` и связать его с catalog rules как upstream-backed specialized endpoint.
    status: completed
  - id: define-smoke-checks
    content: "Зафиксировать короткий сценарий ручной проверки: запуск, поиск статьи, скачивание, чтение и проверка сохранности после рестарта."
    status: completed
isProject: false
---

# Add arXiv Specialized Endpoint

## Goal
Интегрировать [ArXiv MCP Server](https://hub.docker.com/mcp/server/arxiv-mcp-server/overview) в текущий Docker Compose bundle как отдельный специализированный endpoint для поиска, скачивания и чтения научных статей. Зафиксированные решения: сервис поднимается по умолчанию вместе со стеком и сохраняет статьи в именованный Docker volume.

## Target Architecture
- Сохранить текущую модель из [README.md](D:/web_search_mcp/README.md) и [.cursor/rules/concept.mdc](D:/web_search_mcp/.cursor/rules/concept.mdc): один `general` endpoint и отдельный endpoint на каждый специализированный домен.
- Повторить интеграционный шаблон из [docker-compose.yml](D:/web_search_mcp/docker-compose.yml) и [contracts/specialized/wikipedia.md](D:/web_search_mcp/contracts/specialized/wikipedia.md): отдельный сервис, отдельный порт, документация интеграционной поверхности, upstream остаётся implementation authority.
- Добавить `arxiv-mcp` как новый endpoint по умолчанию на `http://localhost:8002/mcp`, с именованным volume для локальной библиотеки статей.
- Предпочесть pinned upstream image `mcp/arxiv-mcp-server`; если у образа окажется неудобный runtime-контракт для текущего стека, использовать тонкую локальную обёртку по аналогии с [wikipedia_mcp/Dockerfile](D:/web_search_mcp/wikipedia_mcp/Dockerfile).

## Planned Changes
- Обновить [docker-compose.yml](D:/web_search_mcp/docker-compose.yml): добавить сервис `arxiv-mcp`, проброс `ARXIV_MCP_PORT`, переменные для storage path, named volume, restart policy и healthcheck, соответствующий реальному способу публикации upstream MCP.
- Обновить [README.md](D:/web_search_mcp/README.md): расширить разделы architecture/configuration/run/IDE, добавить новый специализированный endpoint, его назначение и пример `mcpServers` для Cursor.
- Обновить [.env.example](D:/web_search_mcp/.env.example): добавить хотя бы `ARXIV_MCP_PORT` и связанные переменные хранения, чтобы конфигурация нового endpoint была видимой и единообразной.
- Расширить каталог контрактов: добавить [contracts/specialized/arxiv.md](D:/web_search_mcp/contracts/specialized/arxiv.md) и ссылку в [contracts/README.md](D:/web_search_mcp/contracts/README.md). В документе зафиксировать интегрируемые upstream tools (`search_papers`, `download_paper`, `list_papers`, `read_paper`), storage semantics и pinned version/image reference.
- Добавить smoke-check сценарий в документацию: запуск стека, подключение к `arxiv-mcp`, базовый вызов поиска и проверка, что скачанная статья сохраняется между рестартами контейнера.

## Verification During Execution
- Проверить runtime-контракт официального образа: внутренний порт, путь Streamable HTTP endpoint, способ health probe и минимально необходимую конфигурацию для `ARXIV_STORAGE_PATH`.
- Убедиться, что named volume не конфликтует с остальным стеком и не требует лишних bind mounts на host.
- Проверить, что новый endpoint не смешивается с `general` инструментами и остаётся отдельным специализированным MCP, как требует текущая концепция.

## Files Most Likely Touched
- [docker-compose.yml](D:/web_search_mcp/docker-compose.yml)
- [README.md](D:/web_search_mcp/README.md)
- [.env.example](D:/web_search_mcp/.env.example)
- [contracts/README.md](D:/web_search_mcp/contracts/README.md)
- [contracts/specialized/arxiv.md](D:/web_search_mcp/contracts/specialized/arxiv.md)
- При необходимости нормализации packaging/runtime: [arxiv_mcp/Dockerfile](D:/web_search_mcp/arxiv_mcp/Dockerfile)
