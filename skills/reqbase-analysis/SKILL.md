---
name: reqbase-analysis
description: Maintain ReqBase product requirements and diagrams, reconcile approved decisions with the local catalog, and operate or verify the local ReqBase stack, including Kroki, BRD/SRS and MCP.
---

# ReqBase analysis

Use the ReqBase workspace containing `reqbase/`, `web/`, and `docs/reqbase/`. Read `docs/reqbase/knowledge.md` from that workspace for the current product decisions and source locations.

For startup or real rendering checks on the Windows workstation, read `docs/reqbase/local-windows.md` from that workspace. It records the portable Kroki launcher, how to identify the local database, and what the rendering smoke tests verified.

## Requirements and changes

- Record a user decision in the relevant requirement and its acceptance criteria. Distinguish current behavior, agreed target behavior, and proposals. Start new requirements in Draft by default. Set Approved only on the analyst's explicit instruction.
- When a task changes an existing catalog requirement, keep its `Bxx`/`Fxx`/`Nxx` tag and UUID. Update the Markdown specification and, when in scope, the existing local requirement through MCP. Export a new JSON snapshot after checking the update. Use the snapshot to restore a missing project, not to replace an active project for a one-record change.
- Use branch-specific examples for changes to BRD/SRS. Check both the selected branches and a full-project document. Preview and export share `reqbase/rendering.py`.

## Working through MCP

- Confirm the targeted instance and project before writes. The Docker volume and the source checkout's SQLite database can contain different projects. Discover tools with `tools/list`. Read the current object and version, then use `expected_version` for changes. Use UUIDs for links and updates because positional BR/FR/NFR codes can change. Use `dry_run` for bulk or uncertain changes when it helps review the effect.
- On version conflict, re-read the object and reconcile the intended fields. For requirement history and rollback, use the current requirement version and the history event ID. Check the resulting state and the new audit event. History and rollback cover individual requirements.
- For MCP HTTP use the instance's Bearer token and an applicable `X-Actor` value such as `ai:codex-analyst`. For stdio use the same `REQBASE_DATA` as the intended instance. Treat the token as a secret. Notebook and shell output should contain verification results, not credentials.
- Use a separate SQLite database or test project for smoke tests. `docs/reqbase/exercise.py` seeds the product catalog into a fresh instance and refuses a duplicate title. Use `tests/test_integration.py` for regressions. If network sockets are unavailable, exercise the real handlers via ASGI and report that limit. A mocked or absent Kroki does not verify browser rendering or real PDF output.
