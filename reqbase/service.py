from __future__ import annotations

import csv
import io
import json
import re
from datetime import datetime
from uuid import UUID

from .domain import (
    COLLECTIONS, KINDS, LINKS, SECTIONS, TYPES, Problem, RequirementChange, Store,
    active, actor_name, choice, find, gaps, graph, now, optional_revision, project_summary, required,
    revision, row_projection, stamp, strings, touch, traceability, tree,
)

CSV_FIELDS = ("id", "parent_id", "code", "type", "title", "description", "status",
              "priority", "acceptance_criteria", "tags", "source", "order")
TEXT_FIELDS = {
    "diagrams": ("title", "source"),
    "comments": ("body",),
    "document-sections": ("body",),
    "glossary": ("term", "definition"),
    "views": ("title",),
}


class Service:
    def __init__(self, store=None):
        self.store = store or Store()

    def list_projects(self, deleted=False):
        with self.store.transaction() as db:
            return [project_summary(row) for row in self.store.projects(db, deleted=deleted)
                    if bool(row["deleted_at"]) == deleted]

    def get_project(self, project_id):
        with self.store.transaction() as db:
            return self.store.project(db, project_id)

    def project_fields(self, data, *, create=False):
        fields = {}
        for key in ("title", "prefix", "description", "customer", "document_version", "document_date", "locale"):
            if key in data:
                fields[key] = str(data[key] or "").strip()
        if "authors" in data:
            fields["authors"] = strings(data["authors"], "authors")
        if create or "title" in fields:
            fields["title"] = required(fields.get("title"), "title")
        if create or "prefix" in fields:
            fields["prefix"] = required(fields.get("prefix", "REQ"), "prefix").upper()
        if "locale" in fields:
            choice(fields["locale"], ("ru", "en"), "locale")
        return fields

    def save_project(self, data, actor, dry_run=False, project_id=None, operation="save"):
        with self.store.transaction(write=True, dry_run=dry_run) as db:
            if project_id is None:
                optional_revision(None, data.get("expected_version"))
                project = {**stamp(actor), **{key: [] for key in COLLECTIONS},
                           "description": "", "customer": "", "document_version": "1.0",
                           "document_date": "", "authors": [], "locale": "ru",
                           **self.project_fields(data, create=True)}
            else:
                project = self.store.project(db, project_id, deleted=operation == "restore")
                revision(project, data.get("expected_version"))
                if operation == "delete":
                    project["deleted_at"] = now()
                elif operation == "restore":
                    if not project["deleted_at"]:
                        raise Problem(422, "Project is already active")
                    project["deleted_at"] = None
                else:
                    project.update(self.project_fields(data))
                touch(project, actor)
            self.store.save(db, project)
            return project_summary(project)

    def get_data(self, project_id, collection, identifier=None, *, deleted=False, requirement_id=None):
        project = self.get_project(project_id)
        if collection not in COLLECTIONS:
            raise Problem(404, "Unknown collection")
        rows = project[collection]
        if identifier:
            result = find(rows, identifier, deleted=deleted)
            return row_projection(project, result) if collection == "requirements" else result
        rows = [row for row in rows if bool(row.get("deleted_at")) == deleted]
        if requirement_id:
            rows = [row for row in rows if requirement_id in
                    (row.get("requirement_id"), row.get("source_id"), row.get("target_id"))]
        return [row_projection(project, row) for row in rows] if collection == "requirements" else rows

    def locate(self, collection, identifier):
        with self.store.transaction() as db:
            for project in self.store.projects(db):
                if any(row["id"] == identifier for row in project[collection]):
                    return project["id"]
        raise Problem(404, "Object not found")

    def get_tree(self, project_id, filters=None, depth=None):
        return tree(self.get_project(project_id), filters, depth)

    def get_traceability(self, project_id):
        return traceability(self.get_project(project_id))

    def get_gaps(self, project_id):
        return gaps(self.get_project(project_id))

    def requirements(self, project_id, operation, data, actor, channel, dry_run=False, identifier=None):
        with self.store.transaction(write=True, dry_run=dry_run) as db:
            project = self.store.project(db, project_id)
            change = RequirementChange(project, actor, channel, operation)
            if operation in ("create", "bulk_create"):
                parent = data.get("parent_id")
                target = find(change.rows, parent) if parent else project
                optional_revision(target, data.get("expected_version"))
                items = data["items"] if operation == "bulk_create" else [data]
                for item in items:
                    change.create(item, parent)
            elif operation == "bulk_update":
                if len({item["id"] for item in data["items"]}) != len(data["items"]):
                    raise Problem(422, "A bulk update must contain unique requirement IDs")
                for item in data["items"]:
                    row = find(change.rows, item["id"])
                    revision(row, item.get("expected_version"))
                    change.update(row, item)
            else:
                row = find(change.rows, identifier, deleted=operation in ("restore", "rollback"))
                revision(row, data.get("expected_version"))
                if operation == "update":
                    change.update(row, data)
                elif operation == "move":
                    parent = data.get("parent_id")
                    change.parent(row["type"], parent, row["id"])
                    change.position(row, parent, data.get("position"))
                    change.record(row)
                elif operation == "delete":
                    change.delete(row)
                elif operation == "restore":
                    if not row["deleted_at"]:
                        raise Problem(422, "Requirement is already active")
                    change.restore(row)
                elif operation == "rollback":
                    event = find(project["history"], data.get("history_id"))
                    if event["requirement_id"] != row["id"]:
                        raise Problem(422, "History entry belongs to a different requirement")
                    previous = event["before"]
                    if not previous or previous["deleted_at"]:
                        if not row["deleted_at"]:
                            change.delete(row)
                        else:
                            change.record(row)
                    else:
                        change.parent(previous["type"], previous["parent_id"], row["id"])
                        if row["deleted_at"]:
                            row.update(type=previous["type"], parent_id=previous["parent_id"])
                            change.restore(row)
                        change.update(row, previous)
                        siblings = sum(item["parent_id"] == previous["parent_id"] and item["id"] != row["id"]
                                       for item in active(change.rows))
                        change.position(row, previous["parent_id"], min(previous["order"], siblings))
                else:
                    raise Problem(404, "Unknown requirement operation")
            result = change.finish(dry_run)
            self.store.save(db, project)
            return result

    def item_fields(self, project, collection, data, current):
        values = {}
        for key in TEXT_FIELDS.get(collection, ()):
            if key in data or current is None:
                value = data.get(key)
                if collection == "document-sections" and isinstance(value, str):
                    values[key] = value
                else:
                    values[key] = required(value, key)
        if collection == "diagrams":
            for key, options, default in (("type", ("mermaid", "plantuml"), "mermaid"),
                                          ("kind", KINDS, "other")):
                if key in data or current is None:
                    values[key] = choice(data.get(key, default), options, key)
        elif collection in ("comments", "requirement-diagrams", "links"):
            foreign = {
                "comments": {"requirement_id": "requirements"},
                "requirement-diagrams": {"requirement_id": "requirements", "diagram_id": "diagrams"},
                "links": {"source_id": "requirements", "target_id": "requirements"},
            }[collection]
            for key, table in foreign.items():
                if key in data or current is None:
                    values[key] = find(project[table], data.get(key))["id"]
            if collection == "links":
                combined = {**(current or {}), **values}
                if combined["source_id"] == combined["target_id"]:
                    raise Problem(422, "A requirement cannot link to itself")
                if "type" in data or current is None:
                    values["type"] = choice(data.get("type"), LINKS, "type")
        elif collection == "document-sections" and ("key" in data or current is None):
            values["key"] = choice(data.get("key"), SECTIONS, "key")
        elif collection == "views":
            if "mode" in data or current is None:
                values["mode"] = choice(data.get("mode", "tree"), ("tree", "flat", "kanban"), "mode")
            if "filters" in data or current is None:
                values["filters"] = data.get("filters", {})
        unique_keys = {
            "requirement-diagrams": ("requirement_id", "diagram_id"),
            "links": ("source_id", "target_id", "type"),
            "document-sections": ("key",),
            "glossary": ("term",),
        }.get(collection)
        if unique_keys:
            combined = {**(current or {}), **values}
            for row in active(project[collection]):
                if (current is None or current["id"] != row["id"]) and all(
                    row[key] == combined[key] for key in unique_keys
                ):
                    raise Problem(409, "Object already exists", current=row)
        return values

    def save_item(self, project_id, collection, data, actor, dry_run=False, identifier=None, operation="save"):
        if collection not in TEXT_FIELDS and collection not in ("links", "requirement-diagrams"):
            raise Problem(405, "Collection is read-only")
        with self.store.transaction(write=True, dry_run=dry_run) as db:
            project = self.store.project(db, project_id)
            if identifier:
                row = find(project[collection], identifier, deleted=operation == "restore")
                revision(row, data.get("expected_version"))
                if operation == "delete":
                    row["deleted_at"] = now()
                elif operation == "restore":
                    if not row["deleted_at"]:
                        raise Problem(422, "Object is already active")
                    self.item_fields(project, collection, row, row)
                    row["deleted_at"] = None
                else:
                    row.update(self.item_fields(project, collection, data, row))
                touch(row, actor)
            else:
                optional_revision(project, data.get("expected_version"))
                values = self.item_fields(project, collection, data, None)
                row = {**stamp(actor), **values, "project_id": project_id}
                project[collection].append(row)
            affected_ids = {row.get(key) for key in ("requirement_id", "source_id", "target_id")}
            if collection == "diagrams":
                attachments = project["requirement-diagrams"]
                existing = {link["requirement_id"] for link in active(attachments) if link["diagram_id"] == row["id"]}
                if operation == "save":
                    requested = set(data.get("requirement_ids", []))
                    for requirement_id in requested - existing:
                        find(project["requirements"], requirement_id)
                        attachments.append({**stamp(actor), "project_id": project_id,
                                            "requirement_id": requirement_id, "diagram_id": row["id"]})
                    existing.update(requested)
                affected_ids.update(existing)
            affected = [{"id": item["id"], "code": item["code"]}
                        for item in active(project["requirements"]) if item["id"] in affected_ids]
            self.store.save(db, project)
            return {**row, "requirements": affected, "renumbered": [], "dry_run": dry_run}

    def backup(self, project_id, format):
        project = self.get_project(project_id)
        if format == "json":
            payload = {key: value for key, value in project.items() if key != "exports"}
            return json.dumps({"schema_version": 1, "project": payload}, ensure_ascii=False, indent=2)
        choice(format, ("csv",), "format")
        stream = io.StringIO()
        writer = csv.DictWriter(stream, CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in active(project["requirements"]):
            writer.writerow({**row, **{key: json.dumps(row[key], ensure_ascii=False)
                                      for key in ("acceptance_criteria", "tags")}})
        return stream.getvalue()

    def import_requirements(self, project_id, format, content, actor, channel, dry_run=False, expected_version=None):
        choice(format, ("json", "csv"), "format")
        try:
            if format == "csv":
                rows = list(csv.DictReader(io.StringIO(content.lstrip("\ufeff"))))
                for row in rows:
                    for field in ("acceptance_criteria", "tags"):
                        row[field] = json.loads(row[field]) if row.get(field) else []
            else:
                payload = json.loads(content)
                rows = payload["project"]["requirements"] if isinstance(payload, dict) else payload
                rows = active(rows)
            nodes = {}
            for row in rows:
                identifier = required(row.get("id"), "id")
                if identifier in nodes:
                    raise Problem(422, "Duplicate import ID")
                nodes[identifier] = {**row, "children": []}
            roots = []
            for row in sorted(nodes.values(), key=lambda item: int(item.get("order") or 0)):
                parent = row.pop("parent_id", None)
                row.pop("position", None)
                if parent:
                    nodes[parent]["children"].append(row)
                else:
                    roots.append(row)

            reached = set()
            pending = roots.copy()
            while pending:
                row = pending.pop()
                reached.add(row["id"])
                pending.extend(row["children"])
            if len(reached) != len(nodes):
                raise Problem(422, "Cycle in import hierarchy")
        except (KeyError, ValueError, TypeError, AttributeError, csv.Error) as exc:
            raise Problem(422, f"Invalid {format.upper()} import: {exc}") from exc
        if format == "json" and isinstance(payload, dict):
            return self.import_backup(project_id, payload["project"], roots, actor, channel, dry_run, expected_version)
        return self.requirements(project_id, "bulk_create", {"items": roots, "expected_version": expected_version},
                                 actor, channel, dry_run)

    def import_backup(self, project_id, original, roots, actor, channel, dry_run, expected_version):
        with self.store.transaction(write=True, dry_run=dry_run) as db:
            project = self.store.project(db, project_id)
            optional_revision(project, expected_version)
            change = RequirementChange(project, actor, channel, "import")
            mapping = {}

            def create(node, parent):
                row = change.create({**node, "children": []}, parent)
                mapping[node["id"]] = row["id"]
                for child in node["children"]:
                    create(child, row["id"])

            for node in roots:
                create(node, None)
            for collection in ("diagrams", "comments", "links", "requirement-diagrams",
                               "document-sections", "glossary", "views"):
                for old in active(original.get(collection, [])):
                    data = dict(old)
                    keys = [key for key in ("requirement_id", "diagram_id", "source_id", "target_id") if key in data]
                    if any(data[key] not in mapping for key in keys):
                        continue
                    for key in keys:
                        data[key] = mapping[data[key]]
                    fields = self.item_fields(project, collection, data, None)
                    row = {**stamp(actor), **fields, "project_id": project_id}
                    project[collection].append(row)
                    mapping[old["id"]] = row["id"]
            result = change.finish(dry_run)
            self.store.save(db, project)
            return result

    def restore_backup(self, content, actor, dry_run=False, expected_version=None):
        optional_revision(None, expected_version)
        try:
            payload = json.loads(content.lstrip("\ufeff"))
            if payload["schema_version"] != 1:
                raise ValueError("Unsupported backup version")
            project = payload["project"]
            identifier = project["id"]
            self.validate_backup(project)
        except (KeyError, ValueError, TypeError, AttributeError) as exc:
            raise Problem(422, f"Invalid JSON backup: {exc}") from exc
        with self.store.transaction(write=True, dry_run=dry_run) as db:
            if db.execute("SELECT 1 FROM projects WHERE id = ?", (identifier,)).fetchone():
                raise Problem(409, "Project ID already exists")
            # Keep original identifiers and audit records for migration to another installation.
            for key in COLLECTIONS:
                project.setdefault(key, [])
            project.update(updated_by=actor, updated_at=now())
            self.store.save(db, project)
            return project_summary(project)

    def validate_backup(self, project):
        def uuid(value):
            if not isinstance(value, str) or str(UUID(value)) != value:
                raise ValueError("Expected a canonical UUID")

        def metadata(item):
            uuid(item["id"])
            if type(item["version"]) is not int or item["version"] < 1:
                raise ValueError("Invalid version")
            for key in ("created_at", "updated_at", "deleted_at"):
                if key == "deleted_at" and item[key] is None:
                    continue
                datetime.fromisoformat(item[key])
            actor_name(item["created_by"])
            actor_name(item["updated_by"])

        def requirement(item):
            metadata(item)
            RequirementChange.fields(item, True)
            choice(item["type"], TYPES, "type")
            if not re.fullmatch(item["type"] + r" [1-9][0-9]*(?:\.[1-9][0-9]*)*", item["code"]):
                raise ValueError("Invalid requirement code")
            if type(item["order"]) is not int or item["order"] < 0:
                raise ValueError("Invalid requirement order")
            if item["parent_id"] is not None:
                uuid(item["parent_id"])
            if item.get("deleted_with") is not None:
                uuid(item["deleted_with"])

        metadata(project)
        self.project_fields(project, create=True)
        for key in ("description", "customer", "document_version", "document_date", "authors", "locale"):
            if key not in project:
                raise ValueError(f"Missing project field: {key}")
        if project.get("exports"):
            raise ValueError("Export files are stored outside JSON backups")
        identifiers = {project["id"]}
        for key in COLLECTIONS:
            items = project.setdefault(key, [])
            if not isinstance(items, list):
                raise ValueError("Invalid project collections")
            for item in items:
                uuid(item["id"])
                if item["id"] in identifiers or item["project_id"] != project["id"]:
                    raise ValueError("Duplicate ID or mismatched project ID")
                identifiers.add(item["id"])
                if key == "requirements":
                    requirement(item)
                elif key == "history":
                    find(project["requirements"], item["requirement_id"], deleted=True)
                    actor_name(item["actor"])
                    choice(item["channel"], ("ui", "rest", "mcp"), "channel")
                    datetime.fromisoformat(item["created_at"])
                    for state in ("before", "after"):
                        if item[state] is None and state == "before":
                            continue
                        if item[state]["id"] != item["requirement_id"]:
                            raise ValueError("Mismatched history requirement ID")
                        requirement(item[state])
                else:
                    metadata(item)

        by_id = {row["id"]: row for row in project["requirements"]}
        for parent_id, children in graph(project).items():
            ancestor = find(project["requirements"], parent_id) if parent_id else None
            prefix = ancestor["code"].split(" ", 1)[1] + "." if ancestor else ""
            for position, row in enumerate(children):
                if (row["type"] == "BR") != (ancestor is None):
                    raise ValueError("Invalid requirement hierarchy")
                expected = f"{row['type']} {prefix}{position + 1}"
                if row["order"] != position or row["code"] != expected:
                    raise ValueError("Requirement codes and hierarchy do not agree")
        for row in by_id.values():
            if row["parent_id"] and row["parent_id"] not in by_id:
                raise ValueError("Unknown requirement parent")
        for collection, keys in {
            "comments": {"requirement_id": "requirements"},
            "links": {"source_id": "requirements", "target_id": "requirements"},
            "requirement-diagrams": {"requirement_id": "requirements", "diagram_id": "diagrams"},
        }.items():
            for item in project[collection]:
                for key, target in keys.items():
                    find(project[target], item[key], deleted=True)
