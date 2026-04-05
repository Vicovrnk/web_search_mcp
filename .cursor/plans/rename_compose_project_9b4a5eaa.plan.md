---
name: rename compose project
overview: Rename the Docker Compose project to `open_information_mcp` so generated container names match the new repo name, while preserving internal service DNS names and documenting a one-time volume migration path for existing users.
todos:
  - id: set-compose-project-name
    content: Set the Compose project name to `open_information_mcp` in `docker-compose.yml` without renaming service keys.
    status: completed
  - id: document-volume-migration
    content: Add a short migration note explaining how existing users preserve old named-volume data after the project rename.
    status: completed
  - id: sync-docker-docs
    content: Update README.md and related onboarding docs so Docker naming and migration guidance match the new Compose project name.
    status: completed
isProject: false
---

# Rename Compose Project To `open_information_mcp`

## Goal
Align generated Docker container names with the renamed GitHub project by changing the Compose project name, while keeping the stack behavior stable and preserving existing data.

## Implementation Strategy
Use the Compose project name, not `container_name` and not service renames.

This is the safest option because inter-service communication currently depends on service hostnames, for example in [docker-compose.yml](docker-compose.yml):

```22:22:docker-compose.yml
      SEARXNG_VALKEY_URL: valkey://valkey:6379/0
```

```71:82:docker-compose.yml
      SEARXNG_BASE_URL: http://searxng:8080
      READABILITY_SERVICE_URL: ${READABILITY_SERVICE_URL:-http://readability:3010}
```

Changing only the project name updates generated container names and volume prefixes, but keeps service-to-service DNS stable.

## Planned Changes
- Update [docker-compose.yml](docker-compose.yml) to set the Compose project name to `open_information_mcp`.
- Update [README.md](README.md) so the Docker section reflects the renamed project and explains the impact on generated container names.
- Update [.env.example](.env.example) only if needed for discoverability or consistency with the chosen Compose naming approach.
- Add a short migration note for existing users who already have volumes created under the old default project name.

## Data Preservation
Because named volumes are project-scoped, switching the project name will create new volume names for the same logical entries in [docker-compose.yml](docker-compose.yml):
- `searxng_cache`
- `arxiv_papers`

For existing setups, document a one-time migration path from the old project-prefixed volumes to the new ones. The plan should explicitly cover the arXiv paper storage volume so downloaded papers are not lost.

## Scope Boundaries
- Keep service keys unchanged: `valkey`, `searxng`, `readability`, `mcp-web-search`, `wikipedia-mcp`, `arxiv-mcp`.
- Do not introduce explicit `container_name` entries.
- Do not change MCP endpoint URLs or ports.

## Success Criteria
- New `docker compose` runs generate resources under `open_information_mcp` instead of the old default project name.
- Existing internal service references keep working without changing hostnames.
- README includes a clear note for existing users about preserving current named-volume data.