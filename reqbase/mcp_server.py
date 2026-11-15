import os
from functools import partial, wraps
from typing import Any

from anyio import to_thread

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from .contracts import (
    AttachmentCreate, AttachmentPatch, BackupFormat, BulkCreate, BulkPatch, CommentCreate,
    CommentPatch, DiagramCreate, DiagramPatch, DiagramSource, Export, Filters, Import,
    LinkCreate, LinkPatch, Move, Preview, ProjectCreate, ProjectPatch, RequirementCreate,
    RequirementPatch, Rollback, SectionCreate, SectionPatch, TermCreate, TermPatch,
    RestoreBackup, Versioned, ViewCreate, ViewPatch, payload,
)
from .domain import actor_name, project_summary
from .runtime import documents, renderer, service

mcp = FastMCP(
    "ReqBase", instructions="Use stable UUIDs for links. Codes change when requirements are reordered. "
    "Read the current version before mutations. Use dry_run to preview a proposed change.",
    stateless_http=True, json_response=True, streamable_http_path="/",
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)


def tool(**options):
    def register(function):
        @wraps(function)
        async def offloaded(**arguments):
            return await to_thread.run_sync(partial(function, **arguments))

        return mcp.tool(**options)(offloaded)

    return register


def actor(ctx):
    request = ctx.request_context.request
    return actor_name(request.headers.get("x-actor", "ai:mcp") if request is not None
                      else os.getenv("REQBASE_MCP_ACTOR", "ai:mcp"))


@tool()
def list_projects(deleted: bool = False) -> list[dict]:
    """List active or soft-deleted projects with stable IDs, title, prefix and revision."""
    return service.list_projects(deleted)


@tool()
def get_project(project_id: str) -> dict:
    """Read the metadata and current version of a project."""
    return project_summary(service.get_project(project_id))


@tool()
def create_project(data: ProjectCreate, ctx: Context, dry_run: bool = False) -> dict:
    """Create an independent project with optional BRD/SRS title page metadata."""
    return service.save_project(payload(data), actor(ctx), dry_run)


@tool()
def update_project(project_id: str, data: ProjectPatch, ctx: Context, dry_run: bool = False) -> dict:
    """Patch project metadata after checking its expected revision."""
    return service.save_project(payload(data), actor(ctx), dry_run, project_id)


@tool()
def delete_project(project_id: str, data: Versioned, ctx: Context, dry_run: bool = False) -> dict[str, Any]:
    """Soft-delete a project while retaining its requirements, documents, and audit data."""
    return service.save_project(payload(data), actor(ctx), dry_run, project_id, "delete")


@tool()
def restore_project(project_id: str, data: Versioned, ctx: Context, dry_run: bool = False) -> dict[str, Any]:
    """Restore a soft-deleted project at its expected revision."""
    return service.save_project(payload(data), actor(ctx), dry_run, project_id, "restore")


@tool()
def list_requirements(project_id: str, deleted: bool = False) -> list[dict]:
    """Read requirements in a project or list its soft-deleted requirements and versions."""
    return service.get_data(project_id, "requirements", deleted=deleted)


@tool()
def restore_backup(data: RestoreBackup, ctx: Context, dry_run: bool = False) -> dict[str, Any]:
    """Restore a ReqBase JSON snapshot as a separate project with its original UUIDs and audit records."""
    return service.restore_backup(data.content, actor(ctx), dry_run, data.expected_version)


@tool()
def get_requirement_tree(project_id: str, filters: Filters | None = None, depth: int | None = None) -> list[dict]:
    """Read the hierarchy in document order. Filter ancestors retain context and have matches=false."""
    return service.get_tree(project_id, payload(filters) if filters else {}, depth)


@tool()
def get_requirement(requirement_id: str, include_deleted: bool = False) -> dict[str, Any]:
    """Read a requirement by UUID, including its current code, body, criteria and expected-version input."""
    project = service.locate("requirements", requirement_id)
    return service.get_data(project, "requirements", requirement_id, deleted=include_deleted)


@tool()
def create_requirement(project_id: str, data: RequirementCreate, ctx: Context, dry_run: bool = False) -> dict:
    """Create a root BR or a descendant FR/NFR. Returns the created objects and changed codes."""
    return service.requirements(project_id, "create", payload(data), actor(ctx), "mcp", dry_run)


@tool()
def create_requirements_bulk(project_id: str, data: BulkCreate, ctx: Context, dry_run: bool = False) -> dict:
    """Create multiple requirements and their nested children in a single atomic operation."""
    return service.requirements(project_id, "bulk_create", payload(data), actor(ctx), "mcp", dry_run)


@tool()
def update_requirements_bulk(data: BulkPatch, ctx: Context, dry_run: bool = False) -> dict:
    """Patch fields on several requirements in one project. Supply expected_version for each row."""
    project_id = service.locate("requirements", data.items[0].id)
    return service.requirements(project_id, "bulk_update", payload(data), actor(ctx), "mcp", dry_run)


def edit_requirement(identifier, operation, data, ctx, dry_run):
    project = service.locate("requirements", identifier)
    return service.requirements(project, operation, payload(data), actor(ctx), "mcp", dry_run, identifier)


@tool()
def update_requirement(requirement_id: str, data: RequirementPatch, ctx: Context, dry_run: bool = False) -> dict[str, Any]:
    """Patch one requirement by UUID using its current expected_version."""
    return edit_requirement(requirement_id, "update", data, ctx, dry_run)


@tool()
def move_requirement(requirement_id: str, data: Move, ctx: Context, dry_run: bool = False) -> dict:
    """Move a requirement to a parent and a zero-based position. Returns all renumbered requirements."""
    return edit_requirement(requirement_id, "move", data, ctx, dry_run)


@tool()
def delete_requirement(requirement_id: str, data: Versioned, ctx: Context, dry_run: bool = False) -> dict:
    """Soft-delete a requirement and its active descendants, keeping their UUIDs and relationships."""
    return edit_requirement(requirement_id, "delete", data, ctx, dry_run)


@tool()
def restore_requirement(requirement_id: str, data: Versioned, ctx: Context, dry_run: bool = False) -> dict:
    """Restore a soft-deleted requirement and descendants deleted in the same operation."""
    return edit_requirement(requirement_id, "restore", data, ctx, dry_run)


@tool()
def get_requirement_history(requirement_id: str) -> list[dict]:
    """List field-level history, actor, origin, and before/after values for a requirement."""
    project = service.locate("requirements", requirement_id)
    return service.get_data(project, "history", requirement_id=requirement_id)


@tool()
def rollback_requirement(requirement_id: str, data: Rollback, ctx: Context, dry_run: bool = False) -> dict:
    """Restore the state before a selected history event and record a new rollback history entry."""
    return edit_requirement(requirement_id, "rollback", data, ctx, dry_run)


@tool()
def get_traceability(project_id: str) -> dict:
    """Read BR branches with their FR and NFR descendants and any unlinked descendants."""
    return service.get_traceability(project_id)


@tool()
def find_gaps(project_id: str) -> dict:
    """Find missing FR coverage, orphan FRs, absent acceptance criteria or BR diagrams, and Draft Must items."""
    return service.get_gaps(project_id)


@tool()
def validate_diagram(data: DiagramSource) -> dict:
    """Ask Kroki to validate Mermaid or PlantUML syntax. Returns valid, error, and available line number."""
    return renderer.validate(data.type, data.source)


@tool()
def preview_document(project_id: str, data: Preview) -> dict:
    """Assemble a BRD or SRS preview in Markdown with optional approved, rejected and branch filters."""
    return documents.preview(project_id, data.document_type, data.filters.model_dump())


@tool()
def export_document(project_id: str, data: Export, ctx: Context, dry_run: bool = False) -> dict:
    """Generate a BRD or SRS in PDF or Markdown, recording a snapshot and returning a REST download URL."""
    return documents.export(project_id, data.document_type, data.format, data.filters.model_dump(),
                            actor(ctx), dry_run, data.expected_version)


@tool()
def list_exports(project_id: str) -> list[dict]:
    """List export snapshots, filters, document versions and REST download URLs."""
    return service.get_data(project_id, "exports")


@tool()
def export_backup(project_id: str, format: BackupFormat) -> str:
    """Export a JSON project backup or a CSV requirement hierarchy."""
    return service.backup(project_id, format)


@tool()
def import_requirements(project_id: str, data: Import, ctx: Context, dry_run: bool = False) -> dict:
    """Atomically append a CSV or JSON requirement hierarchy, remapping imported UUIDs."""
    return service.import_requirements(project_id, data.format, data.content, actor(ctx), "mcp",
                                       dry_run, data.expected_version)


RESOURCES = {
    "diagrams": ("diagram", DiagramCreate, DiagramPatch, "diagram source and metadata"),
    "comments": ("comment", CommentCreate, CommentPatch, "requirement discussion"),
    "requirement-diagrams": ("diagram_attachment", AttachmentCreate, AttachmentPatch, "requirement-to-diagram association"),
    "links": ("requirement_link", LinkCreate, LinkPatch, "typed dependency or relationship between requirements"),
    "document-sections": ("document_section", SectionCreate, SectionPatch, "Markdown section used in BRD/SRS"),
    "glossary": ("glossary_term", TermCreate, TermPatch, "project glossary definition"),
    "views": ("saved_view", ViewCreate, ViewPatch, "saved requirements view and filter configuration"),
}


def register_resource(collection, noun, create_model, patch_model, description):
    def listing(project_id: str, requirement_id: str | None = None, deleted: bool = False) -> list[dict]:
        return service.get_data(project_id, collection, requirement_id=requirement_id, deleted=deleted)

    def get(project_id: str, id: str, include_deleted: bool = False) -> dict[str, Any]:
        return service.get_data(project_id, collection, id, deleted=include_deleted)

    def restore(project_id: str, id: str, data: Versioned, ctx: Context, dry_run: bool = False) -> dict[str, Any]:
        return service.save_item(project_id, collection, payload(data), actor(ctx), dry_run, id, "restore")

    def create(project_id: str, data, ctx: Context, dry_run: bool = False) -> dict:
        return service.save_item(project_id, collection, payload(data), actor(ctx), dry_run)

    def update(project_id: str, id: str, data, ctx: Context, dry_run: bool = False) -> dict:
        return service.save_item(project_id, collection, payload(data), actor(ctx), dry_run, id)

    def delete(project_id: str, id: str, data: Versioned, ctx: Context, dry_run: bool = False) -> dict:
        return service.save_item(project_id, collection, payload(data), actor(ctx), dry_run, id, "delete")

    create.__annotations__["data"] = create_model
    update.__annotations__["data"] = patch_model
    names = {"diagram_attachment": "diagram_attachments", "glossary_term": "glossary_terms"}
    tool(name=f"list_{names.get(noun, noun + 's')}", description=f"List project records for {description}.")(listing)
    tool(name=f"create_{noun}", description=f"Create a project record for {description}.")(create)
    tool(name=f"update_{noun}", description=f"Update {description} using its current expected version.")(update)
    tool(name=f"delete_{noun}", description=f"Soft-delete {description} using its current expected version.")(delete)
    tool(name=f"get_{noun}", description=f"Read {description} by ID.")(get)
    tool(name=f"restore_{noun}", description=f"Restore soft-deleted {description} at its expected version.")(restore)


for collection, specification in RESOURCES.items():
    register_resource(collection, *specification)


def main():
    if not os.getenv("REQBASE_API_TOKEN"):
        raise SystemExit("Set REQBASE_API_TOKEN before starting ReqBase MCP.")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
