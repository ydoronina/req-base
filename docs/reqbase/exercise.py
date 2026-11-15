"""Load the ReqBase draft through MCP HTTP and check it through MCP and UI API.

Run from the project root against a local instance. Uses REQBASE_API_TOKEN from
the environment or .env and never displays it. Refuses to seed a second copy.
"""

import asyncio
import argparse
import json
import os
import re
from pathlib import Path

import httpx
from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


HERE = Path(__file__).resolve().parent
TITLE = "ReqBase · Требования к продукту"
BASE = "http://127.0.0.1:" + os.getenv("REQBASE_PORT", "8000")


def catalog(text):
    roots, diagrams = [], []
    for chunk in re.split(r"(?m)(?=^#{3,4} \[[BFND]\d+\])", text)[1:]:
        key, title, meta = re.match(r"#{3,4} \[([BFND]\d+)\] ([^\n]+)\n([^\n]+)", chunk).groups()
        if key.startswith("D"):
            kind, keys = meta.split(" · ")
            source = re.search(r"```mermaid\n(.*?)\n```", chunk, re.S)[1]
            diagrams.append((key, title, kind, keys.split(","), source))
            continue
        typ, priority, coverage = meta.split(" · ")
        body = chunk.split("\n\n", 2)[1]
        checks = re.findall(r"(?m)^- Приёмка: (.+)$", chunk)
        assert len(checks) == 1, key
        node = {"type": typ, "title": f"[{key}] {title}", "description": body,
                "status": "Draft", "priority": priority, "acceptance_criteria": checks,
                "source": "Спецификация ReqBase 0.1 и решения владельца",
                "tags": ["reqbase-spec", key, {"Есть": "реализовано", "Частично": "частично",
                                                 "Предложение": "предложено"}[coverage]]}
        if typ == "BR":
            node["children"] = []
            roots.append(node)
        else:
            roots[-1]["children"].append(node)
    assert (len(roots), sum(len(row["children"]) for row in roots), len(diagrams)) == (4, 17, 4)
    return roots, diagrams


async def exercise(transport=None):
    text = (HERE / "requirements.md").read_text(encoding="utf-8")
    roots, diagrams = catalog(text)
    headers = {"Authorization": "Bearer " + os.environ["REQBASE_API_TOKEN"],
               "X-Actor": "ai:codex-analyst"}
    async with httpx.AsyncClient(base_url=BASE, headers=headers, timeout=15, transport=transport) as http:
        async with streamable_http_client(BASE + "/mcp", http_client=http) as (read, write, _):
            async with ClientSession(read, write) as session:
                async def tool(name, error=False, **args):
                    reply = await session.call_tool(name, args)
                    assert reply.isError == error, (name, str(reply.content)[:700])
                    out = reply.structuredContent
                    if error:
                        return " ".join(getattr(item, "text", "") for item in reply.content)
                    if out is None and len(reply.content) == 1:
                        out = json.loads(reply.content[0].text)
                    if isinstance(out, dict) and set(out) == {"result"}:
                        return out["result"]
                    return out

                init = await session.initialize()
                tools = await session.list_tools()
                print(f"MCP initialize: {init.serverInfo.name}; tools/list: {len(tools.tools)}", flush=True)
                assert not any(row["title"] == TITLE for row in await tool("list_projects")), TITLE
                project = await tool("create_project", data={"title": TITLE, "prefix": "REQBASE", "locale": "ru",
                     "expected_version": 0, "document_version": "0.1", "document_date": "2026-11-15",
                     "authors": ["Системный анализ ReqBase"], "description": "Черновик требований к самому ReqBase."})
                pid = project["id"]
                print(f"Project UUID: {pid}", flush=True)
                scope = {"project_id": pid}
                endpoint = "/projects/" + pid
                args = {**scope, "data": {"items": roots, "expected_version": project["version"]}}
                preview = await tool("create_requirements_bulk", dry_run=True, **args)
                assert preview["dry_run"] and len(preview["items"]) == 21
                assert await tool("list_requirements", **scope) == []
                invalid = await tool("create_requirements_bulk", error=True, **scope,
                                     data={"items": [{"title": "Допустимое BR"}, {"title": "FR без родителя", "type": "FR"}]})
                assert "descend from a BR" in invalid and await tool("list_requirements", **scope) == []
                records = (await tool("create_requirements_bulk", **args))["items"]
                by_key = {re.match(r"\[([A-Z]\d+)\]", row["title"])[1]: row for row in records}
                result = await http.get("/ui" + endpoint + "/requirements", headers={"X-ReqBase-UI": "1"})
                result.raise_for_status()
                assert {row["id"] for row in result.json()} == {row["id"] for row in records}
                tree = await tool("get_requirement_tree", **scope, filters={"tag": "F02"})
                assert len(tree) == 1 and not tree[0]["matches"] and tree[0]["children"][0]["matches"]
                trace = await tool("get_traceability", **scope)
                assert len(trace["branches"]) == 4 and not trace["orphans"]
                print("PASS atomic bulk, dry_run, UI API identity, search, traceability", flush=True)

                req = by_key["F08"]
                ref = {"requirement_id": req["id"]}
                changed = (await tool("update_requirement", **ref,
                           data={"expected_version": req["version"], "status": "In Review"}))["items"][0]
                assert changed["version"] == req["version"] + 1
                stale = await tool("update_requirement", error=True, **ref,
                                   data={"expected_version": req["version"], "status": "Rejected"})
                assert "Version conflict" in stale
                rest = await http.get("/requirements/" + req["id"])
                assert rest.json()["status"] == "In Review"
                audit = await tool("get_requirement_history", **ref)
                event = audit[-1]
                assert (event["actor"], event["channel"]) == ("ai:codex-analyst", "mcp")
                assert (event["before"]["status"], event["after"]["status"]) == ("Draft", "In Review")
                await tool("rollback_requirement", **ref,
                           data={"expected_version": changed["version"], "history_id": event["id"]})
                assert (await tool("get_requirement", **ref))["status"] == "Draft"
                assert len(await tool("get_requirement_history", **ref)) == len(audit) + 1
                print("PASS MCP mutation, stale version conflict, audit and rollback", flush=True)

                paragraphs = {
                    "purpose": "Единый реестр требований, схем и документов по каждому проекту. Аналитик и ИИ работают с одной моделью.",
                    "scope": "Веб RU/EN, REST и MCP, проекты, каталог BR/FR/NFR, схемы, трассировка, история, BRD/SRS и перенос данных.",
                    "stakeholders": "Аналитик — ведёт и согласует требования. ИИ-ассистент — читает и правит напрямую через MCP. Читатель получает экспорт.",
                    "business_goals": "Уменьшить расхождения между каталогом, схемами и документами; обеспечить проверяемость изменений ИИ.",
                    "assumptions": "Один аналитик и его ИИ-ассистент. Approved ставит аналитик в UI или ассистент через MCP по явной команде аналитика. Запись MCP прямая; аудит и откат предусмотрены для требований.",
                    "constraints": "Первый релиз локальный. Многопользовательские роли, утверждённый baseline и откат объектов кроме требований вне объёма. Численные SLO предложены к обсуждению.",
                    "introduction": "Черновик 0.1 описывает текущие функции и предлагаемые критерии для ReqBase.",
                    "overview": "FastAPI и MCP используют один сервис и SQLite. Kroki отвечает за серверный рендер. Связи и клиенты используют UUID.",
                    "interfaces": "Веб: /; REST: /docs; MCP: /mcp с Bearer либо stdio. Для изменения требования передаётся expected_version.",
                }
                for key, body in paragraphs.items():
                    await tool("create_document_section", **scope, data={"key": key, "body": body})
                for term, definition in {"BRD": "Документ бизнес-требований", "SRS": "Спецификация требований к системе",
                                         "UUID": "Постоянный идентификатор записи", "MCP": "Протокол подключения ИИ к инструментам ReqBase"}.items():
                    await tool("create_glossary_term", **scope, data={"term": term, "definition": definition})
                for source, target in [("F08", "F07"), ("F10", "F06"), ("F05", "F02")]:
                    await tool("create_requirement_link", **scope, data={"source_id": by_key[source]["id"],
                              "target_id": by_key[target]["id"], "type": "depends_on"})
                for key, title, kind, keys, source in diagrams:
                    saved = await tool("create_diagram", **scope, data={"title": f"[{key}] {title}", "kind": kind,
                                       "source": source, "type": "mermaid", "requirement_ids": [by_key[k]["id"] for k in keys]})
                    assert len(saved["requirements"]) == len(keys)
                gaps = await tool("find_gaps", **scope)
                assert not any(gaps[key] for key in gaps if key != "must_draft")
                print("PASS 4 diagrams linked, 9 document sections, 4 terms, 3 dependencies; no structural gaps", flush=True)
                backup = await http.get(endpoint + "/backup")
                backup.raise_for_status()
                body = backup.json()["project"]
                assert len(body["requirements"]) == 21 and len(body["diagrams"]) == 4
                (HERE / "reqbase-project.json").write_bytes(backup.content)
                for kind in ("BRD", "SRS"):
                    result = await http.post(endpoint + "/exports/preview", json={"document_type": kind})
                    if result.is_success:
                        print(f"PASS {kind} preview ({len(result.json()['markdown'])} chars)", flush=True)
                    else:
                        print(f"{kind} preview: HTTP {result.status_code}, {result.json().get('message')}", flush=True)
                print(json.dumps({"project_id": pid, "requirements": len(records), "diagrams": len(diagrams),
                                  "draft_must": len(gaps["must_draft"])}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asgi", action="store_true", help="Run the real HTTP handlers in process, without TCP.")
    options = parser.parse_args()
    load_dotenv()
    if options.asgi:
        import sys

        sys.path.insert(0, str(HERE.parents[1]))
        from reqbase.api import app

        async def in_process():
            async with app.router.lifespan_context(app):
                await exercise(httpx.ASGITransport(app=app))

        asyncio.run(in_process())
    else:
        asyncio.run(exercise())
