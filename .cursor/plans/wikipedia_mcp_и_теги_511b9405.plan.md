---
name: Wikipedia MCP и теги
overview: Добавить в Docker Compose отдельный сервис на базе [wikipedia-mcp](https://pypi.org/project/wikipedia-mcp/) (Streamable HTTP), задать теги инструментам текущего FastMCP-сервера через встроенный параметр `tags`, и зафиксировать для разработки на Windows использование `\.venv\Scripts\python.exe`.
todos:
  - id: docker-wikipedia
    content: Dockerfile + сервис docker-compose для wikipedia-mcp (streamable-http, порт, env/token)
    status: completed
  - id: readme-wikipedia
    content: "README: второй MCP URL, переменные, пример конфигурации клиента"
    status: completed
  - id: tool-tags
    content: Добавить tags= в @mcp.tool для web_search, read_url, search_config
    status: completed
  - id: verify-build
    content: compose build/up + pytest через .venv\Scripts\python.exe
    status: completed
isProject: false
---

# План: Wikipedia MCP в сборке и теги инструментов

## Конвенция Python (Windows)

Для любых локальных команд в этом репозитории использовать интерпретатор из виртуального окружения проекта:

`d:\web_search_mcp\.venv\Scripts\python.exe`

(или относительно корня репозитория: `.venv\Scripts\python.exe`). Это исключает путаницу с глобальным Python и гарантирует те же зависимости, что в [pyproject.toml](pyproject.toml).

---

## 1. Wikipedia MCP в Docker-сборке

**Текущее состояние:** [docker-compose.yml](docker-compose.yml) поднимает `valkey`, `searxng`, `readability`, `mcp-web-search`; образ MCP собирается из [mcp_server/Dockerfile](mcp_server/Dockerfile) и ставит только пакет `searxng-mcp-search`.

**Подход:** отдельный сервис в Compose (не смешивать процессы в одном контейнере с `mcp-web-search`), чтобы:

- не раздувать зависимости основного образа;
- соответствовать модели [wikipedia-mcp](https://pypi.org/project/wikipedia-mcp/) как отдельного MCP-сервера с собственным HTTP-транспортом.

**Предлагаемые шаги:**

1. Добавить лёгкий [Dockerfile](mcp_server/Dockerfile) **или** отдельный `wikipedia_mcp/Dockerfile` в корне: базовый `python:3.12-slim`, `pip install wikipedia-mcp` (пин версии, например `wikipedia-mcp==2.0.0`, по желанию через build-arg).
2. В [docker-compose.yml](docker-compose.yml) объявить сервис (условно `wikipedia-mcp`):
   - команда в духе: `wikipedia-mcp --transport streamable-http --host 0.0.0.0 --port <внутренний> --path /mcp` (согласовать с тем, что клиенты ожидают; в README основного стека уже указан Streamable HTTP для SearXNG MCP).
   - проброс порта на хост, например `${WIKIPEDIA_MCP_PORT:-8001}:8080` (точные значения — при реализации).
   - опционально: переменные `WIKIPEDIA_ACCESS_TOKEN`, аргументы `--language` / `--country` через `command` или env, если пакет это поддерживает из env (в описании PyPI есть `WIKIPEDIA_ACCESS_TOKEN`).
3. Обновить [README.md](README.md): второй URL MCP, пример фрагмента конфигурации клиента (два `mcpServers`: `searxng` / `wikipedia`), переменные Compose.

**Ограничение:** инструменты **внутри** процесса `wikipedia-mcp` помечаются кодом этого пакета; этот репозиторий не сможет добавить им `tags` без форка/vendoring. В плане явно разделить: теги — для **нашего** сервера; Wikipedia — отдельный endpoint.

---

## 2. Теги инструментов (SearXNG MCP)

В проекте уже используется **FastMCP**; сигнатура `FastMCP.tool` включает `tags: set[str] | None` (проверено через `.venv\Scripts\python.exe`).

**Файлы регистрации:**

| Инструмент      | Файл                         | Предлагаемые теги (согласовать с вами при реализации) |
|----------------|------------------------------|--------------------------------------------------------|
| `web_search`   | [mcp_server/tools/search.py](mcp_server/tools/search.py) | например `general_search`, `web`, `searxng`           |
| `read_url`     | [mcp_server/tools/read_url.py](mcp_server/tools/read_url.py) | например `general_read`, `readability`, `web`        |
| `search_config`| [mcp_server/tools/config.py](mcp_server/tools/config.py)  | например `searxng`, `meta` (вспомогательный к поиску)  |

Пример вызова декоратора:

```python
@mcp.tool(
    name="web_search",
    description="...",
    tags={"general_search", "web"},
)
```

Тег `wikipedia` для инструментов **этого** сервера не использовать (он резервируется под сценарий «энциклопедия» на отдельном MCP). При необходимости единого каталога тегов — короткая таблица в README: какой сервер какие теги отдаёт.

Опционально позже: `meta` / `annotations` для совместимости с клиентами, ожидающими расширенные поля MCP; на первом этапе достаточно `tags`.

---

## 3. Проверка

- `docker compose up --build` — оба MCP-сервиса healthy (для Wikipedia — healthcheck через `curl` к HTTP endpoint или минимальный probe, если пакет не даёт `/healthz`).
- Локально: `.venv\Scripts\python.exe -m pytest` (существующие тесты в [tests](tests)).
- При желании — скрипт или одноразовая проверка клиентом FastMCP, что в listing инструментов присутствуют ожидаемые `tags` (если тестовая инфраструктура это позволяет без лишнего усложнения).

---

## Зависимости и риски

- **Два MCP в Cursor/IDE:** пользователь подключает два сервера; это ожидаемо.
- **Версия Python:** wikipedia-mcp с PyPI требует `>=3.10`; образ `python:3.12-slim` подходит.
- **Сеть:** Wikipedia идёт наружу из контейнера; при корпоративном прокси могут понадобиться переменные `HTTP_PROXY` (документировать при необходимости).
