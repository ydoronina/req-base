from __future__ import annotations

import base64
import hashlib
import html
import os
import re
from pathlib import Path
from tempfile import NamedTemporaryFile

import httpx
from markdown_it import MarkdownIt

from .domain import Problem, active, choice, now, optional_revision, stamp, traceability

MARKDOWN = MarkdownIt("commonmark", {"html": False}).enable("table")


def atomic_file(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        stream.write(content)
        temporary = Path(stream.name)
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


class Renderer:
    def __init__(self, store):
        self.store = store

    def image(self, kind, source, format="svg"):
        choice(kind, ("mermaid", "plantuml"), "type")
        choice(format, ("svg", "png"), "format")
        if not isinstance(source, str) or not source.strip():
            raise Problem(422, "Diagram source is empty")
        key = hashlib.sha256(f"{kind}\0{format}\0{source}".encode()).hexdigest()
        path = self.store.directory / "cache" / f"{key}.{format}"
        if path.exists():
            return path.read_bytes()
        try:
            response = httpx.post(
                f"{os.getenv('KROKI_URL', 'http://127.0.0.1:8001').rstrip('/')}/{kind}/{format}",
                content=source.encode(), headers={"Content-Type": "text/plain; charset=utf-8"},
                timeout=20,
            )
        except httpx.HTTPError as exc:
            raise Problem(503, "Kroki is unavailable") from exc
        if response.status_code >= 400:
            message = response.text.strip()[:4000]
            raise Problem(422 if response.status_code < 500 else 502, message or "Kroki rendering failed")
        if not response.headers.get("content-type", "").startswith("image/"):
            raise Problem(502, "Kroki returned an invalid image")
        atomic_file(path, response.content)
        return response.content

    def validate(self, kind, source):
        try:
            self.image(kind, source)
            return {"valid": True, "error": None, "line": None}
        except Problem as exc:
            if exc.status != 422:
                raise
            message = exc.payload["message"]
            match = re.search(r"\bline\s*[: ]\s*(\d+)", message, re.I)
            return {"valid": False, "error": message, "line": int(match[1]) if match else None}


LABELS = {
    "ru": {"history": "История версий", "purpose": "Цель и бизнес-контекст", "scope": "Область применения",
           "stakeholders": "Стейкхолдеры", "business_goals": "Бизнес-цели", "br": "Бизнес-требования",
           "assumptions": "Допущения", "constraints": "Ограничения", "glossary": "Глоссарий",
           "introduction": "Введение", "overview": "Общее описание системы", "fr": "Функциональные требования",
           "nfr": "Нефункциональные требования", "interfaces": "Интерфейсы", "trace": "Матрица трассировки",
           "appendix": "Приложение · Диаграммы", "criteria": "Критерии приёмки", "date": "Дата",
           "version": "Версия", "authors": "Авторы", "customer": "Заказчик", "empty": "—"},
    "en": {"history": "Version history", "purpose": "Purpose and business context", "scope": "Scope",
           "stakeholders": "Stakeholders", "business_goals": "Business goals", "br": "Business requirements",
           "assumptions": "Assumptions", "constraints": "Constraints", "glossary": "Glossary",
           "introduction": "Introduction", "overview": "System overview", "fr": "Functional requirements",
           "nfr": "Non-functional requirements", "interfaces": "Interfaces", "trace": "Traceability matrix",
           "appendix": "Appendix · Diagrams", "criteria": "Acceptance criteria", "date": "Date",
           "version": "Version", "authors": "Authors", "customer": "Customer", "empty": "—"},
}

PDF_STYLE = """
@page { size: A4; margin: 20mm; @bottom-right { content: counter(page); color: #687477; } }
body { font: 11pt DejaVu Sans, sans-serif; color: #18312f; line-height: 1.45; overflow-wrap: anywhere; }
.cover { padding-top: 55mm; page-break-after: always; }
.cover h1 { font-size: 37pt; }
h2 { margin-top: 1.6em; color: #146758; }
h2,h3,h4,h5,h6 { break-after: avoid; }
img { max-width: 100%; max-height: 180mm; object-fit: contain; }
table { width: 100%; border-collapse: collapse; font-size: 9pt; }
td, th { padding: 7px; border-bottom: 1px solid #c4d7d3; }
pre { white-space: pre-wrap; background: #f1f6f5; padding: 10px; }
"""


def plain(value):
    return re.sub(r"([\\`*_\[\]<>#|])", r"\\\1", str(value).replace("\n", " "))


class Documents:
    def __init__(self, service, renderer):
        self.service = service
        self.renderer = renderer

    def assemble(self, project, document_type, filters):
        choice(document_type, ("BRD", "SRS"), "document_type")
        labels = LABELS[project.get("locale", "ru")]
        branches = traceability(project)["branches"]
        ids = set(filters.get("branch_ids", []))
        rows = {row["id"]: row for row in active(project["requirements"])}
        if ids - rows.keys():
            raise Problem(422, "Selected branches must belong to the active requirements of this project")
        diagram_map = {row["id"]: row for row in active(project["diagrams"])}
        sections = {row["key"]: row["body"] for row in active(project["document-sections"])}
        glossary = active(project["glossary"])
        parts = []
        links = active(project["requirement-diagrams"])
        image_urls = {}

        def supported(row):
            if filters.get("approved_only") and row["status"] != "Approved":
                return False
            if filters.get("exclude_rejected") and row["status"] == "Rejected":
                return False
            while ids and row:
                if row["id"] in ids:
                    return True
                row = rows.get(row["parent_id"])
            return not ids

        def section(key, content=None):
            parts.extend([f"## {labels[key]}", (sections.get(key) if content is None else content) or "—"])

        def diagram(row):
            if row["id"] not in image_urls:
                try:
                    raw = self.renderer.image(row["type"], row["source"], "png")
                except Problem as exc:
                    raise Problem(exc.status, f"{row['title']}: {exc}") from exc
                image_urls[row["id"]] = "data:image/png;base64," + base64.b64encode(raw).decode()
            return f"![{plain(row['title'])}]({image_urls[row['id']]})"

        def requirement(row, branch=None):
            depth = min(6, 3 + row["code"].count(".") - (1 if branch else 0))
            parts.extend([f"{'#' * depth} {row['code']} · {plain(row['title'])}",
                          f"**{row['priority']} · {row['status']}**" +
                          (f" · {branch['code']} {plain(branch['title'])}" if branch else ""),
                          row["description"] or "—"])
            if row["acceptance_criteria"]:
                parts.extend([f"**{labels['criteria']}**",
                              "\n".join(f"- {plain(item)}" for item in row["acceptance_criteria"])])
            attached = [diagram_map[link["diagram_id"]] for link in links
                        if link["requirement_id"] == row["id"] and link["diagram_id"] in diagram_map]
            parts.extend(diagram(item) for item in attached)

        cover = f"# {document_type} · {plain(project['title'])}\n\n"
        metadata = {"customer": project["customer"], "version": project["document_version"],
                    "authors": ", ".join(project["authors"]), "date": project["document_date"] or now()[:10]}
        cover += "\n\n".join(f"**{labels[key]}** · {plain(value or '—')}" for key, value in metadata.items())
        releases = [(project["document_version"], metadata["date"])]
        releases.extend((row["document_version"], row["created_at"][:10]) for row in project["exports"]
                        if row["document_type"] == document_type)
        history = f"| {labels['version']} | {labels['date']} |\n| --- | --- |\n"
        history += "\n".join(f"| {plain(version)} | {date} |" for version, date in dict.fromkeys(releases))
        section("history", history)
        glossary_md = "\n".join(f"- **{plain(row['term'])}** · {plain(row['definition'])}" for row in glossary)
        if document_type == "BRD":
            for key in ("purpose", "scope", "stakeholders", "business_goals"):
                section(key)
            parts.append(f"## {labels['br']}")
            for branch in branches:
                br = branch["br"]
                selected_descendant = ids.intersection(row["id"] for row in [*branch["fr"], *branch["nfr"]])
                status_allowed = (not filters.get("approved_only") or br["status"] == "Approved") and (
                    not filters.get("exclude_rejected") or br["status"] != "Rejected")
                if supported(br) or (selected_descendant and status_allowed):
                    requirement(br)
            for key in ("assumptions", "constraints"):
                section(key)
            section("glossary", glossary_md)
        else:
            section("introduction")
            for key in ("purpose", "scope", "glossary"):
                value = glossary_md if key == "glossary" else sections.get(key)
                parts.extend([f"### {labels[key]}", value or "—"])
            section("overview")
            for kind in ("fr", "nfr"):
                parts.append(f"## {labels[kind]}")
                for branch in branches:
                    for row in branch[kind]:
                        if supported(row):
                            requirement(row, branch["br"])
            section("interfaces")
            matrix = ["| BR | FR |", "| --- | --- |"]
            for branch in branches:
                children = [row["code"] for row in branch["fr"] if supported(row)]
                if children or supported(branch["br"]):
                    matrix.append(f"| {branch['br']['code']} | {', '.join(children) or '—'} |")
            section("trace", "\n".join(matrix))
            parts.append(f"## {labels['appendix']}")
            appendix_diagrams = diagram_map.values()
            if ids:
                included_requirements = {row["id"] for row in rows.values() if supported(row)}
                linked_diagrams = {link["diagram_id"] for link in links
                                   if link["requirement_id"] in included_requirements}
                appendix_diagrams = (row for row in appendix_diagrams if row["id"] in linked_diagrams)
            parts.extend(diagram(row) for row in appendix_diagrams)
        return cover, "\n\n".join(parts)

    def preview(self, project_id, document_type, filters):
        project = self.service.get_project(project_id)
        cover, body = self.assemble(project, document_type, filters)
        return {"document_type": document_type, "markdown": f"{cover}\n\n{body}"}

    def export(self, project_id, document_type, format, filters, actor, dry_run=False, expected_version=None):
        choice(format, ("md", "pdf"), "format")
        project = self.service.get_project(project_id)
        optional_revision(project, expected_version)
        cover, body = self.assemble(project, document_type, filters)
        artifact = {**stamp(actor), "project_id": project_id, "document_type": document_type,
                    "format": format, "document_version": project["document_version"], "filters": filters}
        artifact["filename"] = f"{document_type}-{artifact['id']}.{format}"
        if dry_run:
            return {**artifact, "download_url": None, "dry_run": True}
        if format == "pdf":
            try:
                from weasyprint import HTML
                from weasyprint.urls import URLFetcher

                title = html.escape(f"{document_type} · {project['title']}")
                document = f"<meta charset=utf-8><title>{title}</title><style>{PDF_STYLE}</style>"
                document += f"<div class=cover>{MARKDOWN.render(cover)}</div>{MARKDOWN.render(body)}"
                fetcher = URLFetcher(allowed_protocols=("data",), allow_redirects=False)
                content = HTML(string=document, url_fetcher=fetcher).write_pdf()
            except (ImportError, OSError) as exc:
                raise Problem(503, "PDF rendering requires WeasyPrint and its system libraries") from exc
        else:
            content = f"{cover}\n\n{body}\n".encode()
        path = self.service.store.directory / "exports" / artifact["filename"]
        atomic_file(path, content)
        artifact["download_url"] = f"/projects/{project_id}/exports/{artifact['id']}/file"
        try:
            with self.service.store.transaction(write=True) as db:
                current = self.service.store.project(db, project_id)
                current["exports"].append(artifact)
                self.service.store.save(db, current)
        except BaseException:
            path.unlink(missing_ok=True)
            raise
        return artifact
