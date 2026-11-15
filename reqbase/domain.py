from __future__ import annotations

import json
import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

STATUSES = ("Draft", "In Review", "Approved", "Implemented", "Rejected")
PRIORITIES = ("Must", "Should", "Could", "Won't")
TYPES = ("BR", "FR", "NFR")
KINDS = ("sequence", "class", "activity", "state", "ER", "component", "use case", "flowchart", "other")
LINKS = ("depends_on", "relates_to", "conflicts_with")
SECTIONS = ("purpose", "scope", "stakeholders", "business_goals", "assumptions",
            "constraints", "introduction", "overview", "interfaces")
COLLECTIONS = ("requirements", "diagrams", "requirement-diagrams", "comments",
               "links", "document-sections", "glossary", "exports", "history", "views")


class Problem(Exception):
    def __init__(self, status, message, **details):
        self.status = status
        self.payload = {"message": message, **details}
        super().__init__(message)


def now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def uid():
    return str(uuid4())


def required(value, label):
    if not isinstance(value, str) or not value.strip():
        raise Problem(422, f"{label} is required")
    return value.strip()


def choice(value, options, label):
    if value not in options:
        raise Problem(422, f"{label} must be one of: {', '.join(options)}")
    return value


def strings(value, label):
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise Problem(422, f"{label} must be an array of strings")
    return list(dict.fromkeys(item.strip() for item in value if item.strip()))


def active(rows):
    return [row for row in rows if not row.get("deleted_at")]


def find(rows, identifier, *, deleted=False):
    for row in rows:
        if row["id"] == identifier and (deleted or not row.get("deleted_at")):
            return row
    raise Problem(404, "Object not found")


def revision(row, expected_version):
    if expected_version is None:
        raise Problem(422, "expected_version is required")
    if type(expected_version) is not int or expected_version != row["version"]:
        current = project_summary(row) if "requirements" in row else row
        raise Problem(409, "Version conflict", current=current)


def optional_revision(row, expected_version):
    if expected_version is None:
        return
    if row is None:
        if expected_version != 0:
            raise Problem(409, "Version conflict", current=None)
        return
    revision(row, expected_version)


def stamp(actor):
    timestamp = now()
    return {"id": uid(), "version": 1, "created_at": timestamp, "updated_at": timestamp,
            "deleted_at": None, "created_by": actor, "updated_by": actor}


def touch(row, actor):
    row.update(version=row["version"] + 1, updated_at=now(), updated_by=actor)


def row_projection(project, row):
    diagrams = {diagram["id"] for diagram in active(project["diagrams"])}
    return {**row, "diagram_count": sum(link["requirement_id"] == row["id"] and link["diagram_id"] in diagrams
                                       for link in active(project["requirement-diagrams"]))}


def matches(row, filters):
    for field in ("type", "status", "priority", "updated_by"):
        if filters.get(field) and row.get(field) != filters[field]:
            return False
    if filters.get("tag") and filters["tag"].casefold() not in [tag.casefold() for tag in row["tags"]]:
        return False
    if filters.get("has_diagrams") is not None and bool(row["diagram_count"]) != filters["has_diagrams"]:
        return False
    query = (filters.get("q") or "").casefold().strip()
    return not query or query in " ".join([row["code"], row["title"], row["description"],
                                           row["source"], *row["tags"], *row["acceptance_criteria"]]).casefold()


class Store:
    def __init__(self, directory=None):
        self.directory = Path(directory or os.getenv("REQBASE_DATA", "data")).resolve()

    @contextmanager
    def transaction(self, *, write=False, dry_run=False):
        self.directory.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.directory / "reqbase.sqlite3", timeout=15)
        db.row_factory = sqlite3.Row
        try:
            db.execute("CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, body TEXT NOT NULL)")
            db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield db
            db.rollback() if dry_run else db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def projects(db, *, deleted=False):
        rows = (json.loads(row["body"]) for row in db.execute("SELECT body FROM projects"))
        return [row for row in rows if deleted or not row.get("deleted_at")]

    @staticmethod
    def project(db, identifier, *, deleted=False):
        result = db.execute("SELECT body FROM projects WHERE id = ?", (identifier,)).fetchone()
        if result:
            project = json.loads(result["body"])
            if deleted or not project.get("deleted_at"):
                return project
        raise Problem(404, "Project not found")

    @staticmethod
    def save(db, project):
        db.execute("INSERT INTO projects VALUES (?, ?) ON CONFLICT(id) DO UPDATE SET body=excluded.body",
                   (project["id"], json.dumps(project, ensure_ascii=False, separators=(",", ":"))))


def project_summary(project):
    return {key: value for key, value in project.items() if key not in COLLECTIONS}


def graph(project):
    rows = sorted(active(project["requirements"]), key=lambda row: row["order"])
    children = {}
    for row in rows:
        children.setdefault(row["parent_id"], []).append(row)
    return children


def tree(project, filters=None, depth=None):
    filters = filters or {}
    children = graph(project)

    def visit(parent, level):
        result = []
        for row in children.get(parent, []):
            item = row_projection(project, row)
            descendants = visit(row["id"], level + 1)
            matched = matches(item, filters)
            if matched or descendants:
                result.append({**item, "matches": matched,
                               "children": descendants if depth is None or level < depth else []})
        return result

    return visit(None, 0)


def traceability(project):
    rows = {row["id"]: row_projection(project, row) for row in active(project["requirements"])}
    branches = {row["id"]: {"br": row, "fr": [], "nfr": []}
                for row in rows.values() if row["type"] == "BR"}
    orphans = []
    for row in rows.values():
        if row["type"] == "BR":
            continue
        ancestor = rows.get(row["parent_id"])
        visited = {row["id"]}
        while ancestor and ancestor["type"] != "BR" and ancestor["id"] not in visited:
            visited.add(ancestor["id"])
            ancestor = rows.get(ancestor["parent_id"])
        if ancestor and ancestor["id"] in branches:
            branches[ancestor["id"]][row["type"].lower()].append(row)
        else:
            orphans.append(row)
    key = lambda row: tuple(map(int, row["code"].split(" ", 1)[1].split(".")))
    ordered = sorted(branches.values(), key=lambda branch: key(branch["br"]))
    for branch in ordered:
        for kind in ("fr", "nfr"):
            branch[kind].sort(key=key)
    return {"branches": ordered, "orphans": orphans}


def gaps(project):
    trace = traceability(project)
    rows = [row_projection(project, row) for row in active(project["requirements"])]
    return {
        "br_without_fr": [branch["br"] for branch in trace["branches"] if not branch["fr"]],
        "fr_without_br": [row for row in trace["orphans"] if row["type"] == "FR"],
        "without_acceptance_criteria": [row for row in rows if not row["acceptance_criteria"]],
        "br_without_diagrams": [row for row in rows if row["type"] == "BR" and not row["diagram_count"]],
        "must_draft": [row for row in rows if row["priority"] == "Must" and row["status"] == "Draft"],
    }


class RequirementChange:
    def __init__(self, project, actor, channel, action):
        self.project = project
        self.rows = project["requirements"]
        self.actor = actor
        self.channel = channel
        self.action = action
        self.before = {row["id"]: dict(row) for row in self.rows}
        self.primary = []

    def record(self, row):
        if row["id"] not in self.primary:
            self.primary.append(row["id"])

    def parent(self, kind, parent_id, row_id=None):
        if kind == "BR" and parent_id is not None:
            raise Problem(422, "Business requirements must be roots")
        if kind != "BR" and not parent_id:
            raise Problem(422, "FR and NFR must descend from a BR")
        while parent_id is not None:
            if parent_id == row_id:
                raise Problem(422, "A requirement cannot move into its own branch")
            parent_id = find(self.rows, parent_id)["parent_id"]

    def position(self, row, parent_id, position):
        siblings = sorted((item for item in active(self.rows)
                           if item["parent_id"] == parent_id and item["id"] != row["id"]),
                          key=lambda item: item["order"])
        if position is None:
            position = len(siblings)
        if type(position) is not int or not 0 <= position <= len(siblings):
            raise Problem(422, "position must be a zero-based sibling index")
        row["parent_id"] = parent_id
        siblings.insert(position, row)
        for index, sibling in enumerate(siblings):
            sibling["order"] = index

    @staticmethod
    def fields(data, defaults=False):
        values = {}
        if defaults or "title" in data:
            values["title"] = required(data.get("title"), "title")
        for field in ("description", "source"):
            if defaults or field in data:
                value = data.get(field, "")
                if not isinstance(value, str):
                    raise Problem(422, f"{field} must be a string")
                values[field] = value
        for field in ("acceptance_criteria", "tags"):
            if defaults or field in data:
                values[field] = strings(data.get(field, []), field)
        for field, options, default in (("status", STATUSES, "Draft"), ("priority", PRIORITIES, "Should")):
            if defaults or field in data:
                values[field] = choice(data.get(field, default), options, field)
        return values

    def create(self, data, parent_id):
        kind = choice(data.get("type", "BR" if parent_id is None else "FR"), TYPES, "type")
        self.parent(kind, parent_id)
        row = {**stamp(self.actor), **self.fields(data, True), "type": kind,
               "project_id": self.project["id"], "code": "", "parent_id": parent_id, "order": 0}
        self.position(row, parent_id, data.get("position"))
        self.rows.append(row)
        self.record(row)
        children = data.get("children", [])
        if not isinstance(children, list) or any(not isinstance(child, dict) for child in children):
            raise Problem(422, "children must be an array of requirements")
        for child in children:
            self.create(child, row["id"])
        return row

    def update(self, row, data):
        row.update(self.fields(data))
        if "type" in data:
            kind = choice(data["type"], TYPES, "type")
            self.parent(kind, row["parent_id"], row["id"])
            row["type"] = kind
        self.record(row)

    def delete(self, row):
        timestamp = now()
        pending = [row]
        children = graph(self.project)
        while pending:
            node = pending.pop()
            node.update(deleted_at=timestamp, deleted_with=row["id"])
            self.record(node)
            pending.extend(children.get(node["id"], []))

    def restore(self, row):
        self.parent(row["type"], row["parent_id"], row["id"])
        deleted_at = row["deleted_at"]
        branch = [item for item in self.rows if item.get("deleted_with") == row["id"]
                  and item["deleted_at"] == deleted_at]
        for item in branch or [row]:
            item["deleted_at"] = None
            item.pop("deleted_with", None)
            available = sum(sibling["parent_id"] == item["parent_id"] and sibling["id"] != item["id"]
                            for sibling in active(self.rows))
            self.position(item, item["parent_id"], min(item["order"], available))
            self.record(item)

    def finish(self, dry_run=False):
        children = graph(self.project)

        def number(parent, prefix):
            for index, row in enumerate(children.get(parent, [])):
                path = [*prefix, str(index + 1)]
                row.update(order=index, code=f"{row['type']} {'.'.join(path)}")
                number(row["id"], path)

        number(None, [])
        renumbered = []
        for row in self.rows:
            previous = self.before.get(row["id"], {})
            changes = {
                key: {"before": previous.get(key), "after": row.get(key)}
                for key in previous.keys() | row.keys()
                if previous.get(key) != row.get(key)
            }
            if not changes:
                continue
            if previous:
                touch(row, self.actor)
                if "code" in changes:
                    renumbered.append({"id": row["id"], "code": row["code"],
                                       "previous_code": previous["code"], "version": row["version"]})
            self.project["history"].append({"id": uid(), "project_id": self.project["id"],
                                            "requirement_id": row["id"], "actor": self.actor,
                                            "channel": self.channel, "action": self.action,
                                            "created_at": now(), "diff": changes,
                                            "before": previous or None, "after": dict(row)})
        by_id = {row["id"]: row for row in self.rows}
        return {"items": [row_projection(self.project, by_id[identifier]) for identifier in self.primary],
                "renumbered": renumbered, "dry_run": dry_run}


def actor_name(value):
    if not re.fullmatch(r"(?:user|ai:[\w.-]{1,64})", value):
        raise Problem(422, "X-Actor must be user or ai:<client>")
    return value
