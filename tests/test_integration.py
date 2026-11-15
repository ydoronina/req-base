import asyncio
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

from httpx import ASGITransport, AsyncClient, Response
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

scratch = tempfile.TemporaryDirectory()
os.environ.update(REQBASE_DATA=scratch.name, REQBASE_API_TOKEN="reqbase-test-token", REQBASE_DEMO="0")

from reqbase.api import app
from reqbase.domain import Store
from reqbase.service import Service

AUTH = {"Authorization": "Bearer reqbase-test-token", "X-Actor": "ai:test"}
MCP_AUTH = {**AUTH, "Accept": "application/json, text/event-stream"}


class Integration(unittest.IsolatedAsyncioTestCase):
    async def test_shared_workspace(self):
        async with app.router.lifespan_context(app):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as client:
                await self.scenario(client)

    async def scenario(self, client):
        async def call(method, url, body=None, code=200, headers=AUTH):
            args = {"json": body} if body is not None else {}
            response = await client.request(method, url, headers=headers, **args)
            self.assertEqual(response.status_code, code, response.text[:700])
            return response

        await call("GET", "/projects", code=401, headers={})
        await call("GET", "/ui/projects", code=403, headers={"X-ReqBase-UI": "1", "Origin": "http://foreign.invalid"})
        spec = (await call("GET", "/openapi.json", headers={})).json()
        self.assertIn("/requirements/bulk", spec["paths"])
        docs = (await call("GET", "/docs", headers={})).text
        self.assertIn("/static-offline-docs/swagger-ui-bundle.js", docs)
        await call("GET", "/static-offline-docs/swagger-ui-bundle.js", headers={})
        await call("POST", "/projects", {"title":"Conflict", "expected_version":1}, 409)
        project = (await call("POST", "/projects", {"title": "Проверка"}, 201)).json()
        path = f"/projects/{project['id']}"
        bulk = path + "/requirements/bulk"
        await call("POST", bulk, {"items": [{"title": "Atomic"}, {"title": "Invalid", "type": "FR"}]}, 422)
        self.assertEqual((await call("GET", path + "/tree")).json(), [])
        creation = {"items": [
            {"title": "Доступ", "children": [{"title": "Вход", "status": "Approved",
                                             "children": [{"title": "Latency", "type": "NFR"}]}]},
            {"title": "Профиль"},
        ]}
        await call("POST", bulk, {**creation,"expected_version":2}, 409)
        await call("POST", bulk + "?dry_run=true", {**creation,"expected_version":1}, 201)
        self.assertEqual((await call("GET", path + "/requirements")).json(), [])
        result = (await call("POST", bulk, creation, 201)).json()
        br, fr, nfr, second = result["items"]
        self.assertEqual([item["code"] for item in result["items"]], ["BR 1", "FR 1.1", "NFR 1.1.1", "BR 2"])
        filtered = (await call("GET", path + "/tree?type=FR&depth=0")).json()
        self.assertFalse(filtered[0]["matches"])
        self.assertEqual(filtered[0]["children"], [])
        endpoint = "/requirements/" + fr["id"]
        await call("POST", endpoint + "/move", {"parent_id": nfr["id"], "expected_version": 1}, 422)
        moved = (await call("POST", endpoint + "/move", {"parent_id": second["id"], "expected_version": 1})).json()
        self.assertEqual(moved["items"][0]["code"], "FR 2.1")
        self.assertEqual({item["code"] for item in moved["renumbered"]}, {"FR 2.1", "NFR 2.1.1"})
        conflict = (await call("PATCH", endpoint, {"expected_version": 1,"title": "Stale"}, 409)).json()
        self.assertEqual(conflict["current"]["code"], "FR 2.1")
        await call("PATCH", "/requirements/bulk", {"items": [
            {"id": fr["id"], "priority": "Must", "expected_version": 2},
            {"id": second["id"], "status": "Approved", "expected_version": 1},
        ]})
        audit = (await call("GET", endpoint + "/history")).json()
        self.assertEqual((audit[-1]["actor"],audit[-1]["channel"]),("ai:test","rest"))
        rolled_back = (await call("POST", endpoint + "/rollback", {"expected_version": 3,"history_id": audit[1]["id"]})).json()
        self.assertEqual(rolled_back["items"][0]["code"], "FR 1.1")
        deleted = (await call("DELETE", endpoint, {"expected_version": 4})).json()
        self.assertEqual(len(deleted["items"]), 2)
        await call("GET", endpoint, code=404)
        await call("POST", endpoint + "/restore", {"expected_version": 5})
        self.assertEqual((await call("GET", endpoint)).json()["parent_id"], br["id"])
        trace = (await call("GET", path + "/traceability")).json()
        self.assertEqual(trace["branches"][0]["nfr"][0]["id"], nfr["id"])
        self.assertEqual((await call("GET", path + "/gaps")).json()["br_without_fr"][0]["id"], second["id"])
        ui = (await call("PATCH", "/ui" + endpoint, {"expected_version": 6,"tags":["ui"]},
                         headers={"X-ReqBase-UI":"1","Origin":"http://localhost"},)).json()
        self.assertEqual(ui["items"][0]["updated_by"], "user")
        for fmt in ["csv", "json"]:
            backup = (await call("GET", path + "/backup?format=" + fmt)).text
            imported = (await call("POST", path + "/import?dry_run=true", {"format":fmt, "content":backup})).json()
            self.assertEqual(len(imported["items"]), 4)
        preview = (await call("POST", path + "/exports/preview", {"document_type":"SRS"})).json()
        self.assertIn("FR 1.1", preview["markdown"])
        exported = (await call("POST", path + "/exports", {"document_type":"SRS", "format":"md"}, 201)).json()
        self.assertIn("FR 1.1", (await call("GET", exported["download_url"])).text)
        result = (await call("GET", path + "/exports")).json()
        self.assertEqual(result[0]["id"], exported["id"])
        message = {"jsonrpc":"2.0","id":1,"method":"tools/call",
                   "params":{"name":"get_requirement","arguments":{"requirement_id":fr["id"]}}}
        await call("POST", "/mcp", message, 401, headers={})
        outcome = (await call("POST", "/mcp", message, headers=MCP_AUTH)).json()["result"]
        self.assertFalse(outcome.get("isError",False), outcome)
        self.assertEqual(outcome["structuredContent"]["code"], "FR 1.1")
        message["params"] = {"name":"update_requirement","arguments":{"requirement_id":fr["id"],
            "data":{"expected_version":7,"title":"MCP update"}}}
        outcome = (await call("POST", "/mcp", message, headers=MCP_AUTH)).json()["result"]
        self.assertFalse(outcome.get("isError",False), outcome)
        audit = (await call("GET", endpoint + "/history")).json()
        self.assertEqual(audit[-1]["channel"], "mcp")
        self.assertEqual(audit[-1]["after"]["title"], "MCP update")
        concurrent = await asyncio.gather(*[
            client.patch(endpoint, headers=AUTH, json={"title": title, "expected_version": 8})
            for title in ("First editor", "Second editor")
        ])
        self.assertEqual(sorted(item.status_code for item in concurrent), [200, 409])
        await self.diagrams_and_backup(call, path, fr["id"])
        await self.stdio(fr["id"])

    async def diagrams_and_backup(self, call, path, requirement_id):
        diagrams = path + "/diagrams"
        data = {"title": "Sequence", "type": "plantuml", "kind": "sequence",
                "source": "@startuml\nAlice -> Bob: Call\n@enduml", "requirement_ids": [requirement_id]}
        await call("POST", diagrams, {**data, "requirement_ids": [requirement_id, "invalid"]}, 404)
        self.assertEqual((await call("GET", diagrams)).json(), [])
        created = (await call("POST", diagrams, data, 201)).json()
        self.assertEqual(created["requirements"], [{"id":requirement_id, "code":"FR 1.1"}])
        attachment = (await call("GET", path + "/requirement-diagrams")).json()
        self.assertEqual(attachment[0]["diagram_id"], created["id"])
        svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"></svg>'
        with patch("reqbase.rendering.httpx.post", return_value=Response(200, headers={"content-type":"image/svg+xml"}, content=svg)) as kroki:
            for _ in range(2):
                image = await call("GET", "/diagrams/" + created["id"] + "/render")
                self.assertEqual(image.content, svg)
            self.assertEqual(kroki.call_count, 1)
            self.assertTrue(kroki.call_args.args[0].endswith("/plantuml/svg"))
        with patch("reqbase.rendering.httpx.post", return_value=Response(400, text="Syntax error at line 2")):
            invalid = (await call("POST", "/diagrams/validate", {"source":"wrong","type":"mermaid"})).json()
        self.assertEqual(invalid, {"valid":False,"error":"Syntax error at line 2","line":2})
        tree = (await call("GET", path + "/tree")).json()
        selected, other = tree
        nfr_id = selected["children"][0]["children"][0]["id"]
        for title, ids in [("Shared", [selected["id"], requirement_id, other["id"]]),
                           ("Other branch", [other["id"]]), ("Unattached", []),
                           ("Draft child", [nfr_id])]:
            await call("POST", diagrams, {**data, "title": title, "requirement_ids": ids}, 201)
        png = bytes.fromhex("89504e470d0a1a0a")
        with patch("reqbase.rendering.httpx.post", return_value=Response(200, headers={"content-type":"image/png"}, content=png)):
            async def appendix(filters):
                doc = (await call("POST", path + "/exports/preview", {"document_type": "SRS",
                                  "filters": filters})).json()["markdown"]
                return doc.split("## Приложение · Диаграммы", 1)[1]

            filtered = await appendix({"branch_ids": [selected["id"]], "approved_only": True})
            self.assertIn("![Sequence](data:image/png;base64,", filtered)
            self.assertEqual(filtered.count("![Shared]("), 1)
            full = await appendix({})
            for title in ("Other branch", "Unattached", "Draft child"):
                self.assertNotIn(f"![{title}](", filtered)
                self.assertIn(f"![{title}](", full)
        backup = (await call("GET", path + "/backup")).text
        with tempfile.TemporaryDirectory() as directory:
            restored = Service(Store(directory))
            project = restored.restore_backup(backup, "user")
            self.assertEqual(project["id"], path.split("/")[-1])
            self.assertEqual(restored.get_data(project["id"], "requirements", requirement_id)["id"], requirement_id)
            self.assertEqual(restored.get_data(project["id"], "diagrams", created["id"])["source"], data["source"])

    async def stdio(self, requirement_id):
        params = StdioServerParameters(command=sys.executable, args=["-m", "reqbase.mcp_server"], env=dict(os.environ))
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                reply = await session.call_tool("get_requirement", {"requirement_id":requirement_id})
                self.assertFalse(reply.isError, reply)
                self.assertEqual(reply.structuredContent["id"], requirement_id)


if __name__ == "__main__":
    unittest.main()
