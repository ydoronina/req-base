from __future__ import annotations

import hmac
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Security
from fastapi_offline import FastAPIOffline
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from starlette.datastructures import Headers
from starlette.concurrency import run_in_threadpool

from .contracts import (
    BackupFormat, BulkCreate, BulkPatch, DiagramSource, Export, ImageFormat, TreeFilters,
    Import, Move, Preview, ProjectCreate, ProjectPatch, RenderSource, RequirementCreate,
    RequirementPatch, RequirementRecord, RequirementWrite, RestoreBackup, Rollback,
    Traceability, TreeRequirement, Versioned, payload,
)
from .domain import Problem, actor_name, project_summary
from .mcp_server import RESOURCES, mcp
from .runtime import documents, renderer, service

STATIC = Path(__file__).resolve().parents[1] / "static"
router = APIRouter()
bearer = HTTPBearer(auto_error=False)


def authorized(header):
    secret = os.getenv("REQBASE_API_TOKEN", "")
    return bool(secret and header and hmac.compare_digest(header.encode(), f"Bearer {secret}".encode()))


def check_token(credentials: Annotated[HTTPAuthorizationCredentials | None, Security(bearer)]):
    if not credentials or not authorized(f"Bearer {credentials.credentials}"):
        raise HTTPException(401, "A valid REQBASE_API_TOKEN is required", headers={"WWW-Authenticate": "Bearer"})


def validate_actor(x_actor: Annotated[str | None, Header(description="Audit actor: user or ai:<client>")] = None):
    if x_actor is not None:
        actor_name(x_actor)


def identity(request):
    if request.url.path.startswith("/ui/"):
        return "user", "ui"
    return actor_name(request.headers.get("x-actor", "ai:rest")), "rest"


class Access:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        path = scope["path"]
        headers = Headers(scope=scope)
        if path == "/mcp" or path.startswith("/mcp/"):
            if not authorized(headers.get("authorization")):
                return await JSONResponse({"message": "Invalid MCP token"}, 401,
                                          headers={"WWW-Authenticate": "Bearer"})(scope, receive, send)
            if path == "/mcp":
                scope = {**scope, "path": "/mcp/", "raw_path": b"/mcp/"}
        elif path.startswith("/ui/"):
            host = headers.get("host", "")
            host_name = host.split("]")[0].lstrip("[") if host.startswith("[") else host.split(":")[0]
            allowed = {"localhost", "127.0.0.1", "::1"} | {
                name.strip().lower() for name in os.getenv("REQBASE_UI_HOSTS", "").split(",") if name.strip()
            }
            origin = headers.get("origin")
            same_origin = origin is None or origin in (f"http://{host}", f"https://{host}")
            if host_name.lower() not in allowed or not same_origin or headers.get("x-reqbase-ui") != "1":
                return await JSONResponse({"message": "Same-origin ReqBase UI request required"}, 403)(
                    scope, receive, send)
        await self.app(scope, receive, send)


mcp_app = mcp.streamable_http_app()


@asynccontextmanager
async def lifespan(app):
    if os.getenv("REQBASE_DEMO") == "1":
        from .demo import seed
        await run_in_threadpool(seed, service)
    async with mcp.session_manager.run():
        yield


app = FastAPIOffline(title="ReqBase API", version="1.0.0", lifespan=lifespan, redoc_url=None,
              description="Project requirements, traceability, diagrams, and BRD/SRS generation.")
app.add_middleware(Access)


@app.exception_handler(Problem)
async def service_error(request, exc):
    return JSONResponse(exc.payload, status_code=exc.status)


@router.get("/projects")
def list_projects(deleted: bool = False):
    return service.list_projects(deleted)


@router.post("/projects", status_code=201)
def create_project(data: ProjectCreate, request: Request, dry_run: bool = False):
    return service.save_project(payload(data), identity(request)[0], dry_run)


@router.post("/projects/import", status_code=201)
def restore_backup(data: RestoreBackup, request: Request, dry_run: bool = False):
    return service.restore_backup(data.content, identity(request)[0], dry_run, data.expected_version)


@router.get("/projects/{project_id}")
def get_project(project_id: str):
    return project_summary(service.get_project(project_id))


@router.patch("/projects/{project_id}")
def update_project(project_id: str, data: ProjectPatch, request: Request, dry_run: bool = False):
    return service.save_project(payload(data), identity(request)[0], dry_run, project_id)


@router.delete("/projects/{project_id}")
def delete_project(project_id: str, data: Versioned, request: Request, dry_run: bool = False):
    return service.save_project(payload(data), identity(request)[0], dry_run, project_id, "delete")


@router.post("/projects/{project_id}/restore")
def restore_project(project_id: str, data: Versioned, request: Request, dry_run: bool = False):
    return service.save_project(payload(data), identity(request)[0], dry_run, project_id, "restore")


@router.get("/projects/{project_id}/tree", response_model=list[TreeRequirement])
def get_tree(project_id: str, filters: Annotated[TreeFilters, Query()]):
    return service.get_tree(project_id, filters.model_dump(exclude={"depth"}, exclude_none=True), filters.depth)


@router.get("/projects/{project_id}/requirements", response_model=list[RequirementRecord])
def list_requirements(project_id: str, deleted: bool = False):
    return service.get_data(project_id, "requirements", deleted=deleted)


@router.post("/projects/{project_id}/requirements", status_code=201, response_model=RequirementWrite)
def create_requirement(project_id: str, data: RequirementCreate, request: Request, dry_run: bool = False):
    return service.requirements(project_id, "create", payload(data), *identity(request), dry_run)


@router.post("/projects/{project_id}/requirements/bulk", status_code=201, response_model=RequirementWrite)
def create_requirements_bulk(project_id: str, data: BulkCreate, request: Request, dry_run: bool = False):
    return service.requirements(project_id, "bulk_create", payload(data), *identity(request), dry_run)


@router.patch("/requirements/bulk", response_model=RequirementWrite)
def update_requirements_bulk(data: BulkPatch, request: Request, dry_run: bool = False):
    project = service.locate("requirements", data.items[0].id)
    return service.requirements(project, "bulk_update", payload(data), *identity(request), dry_run)


@router.get("/requirements/{id}", response_model=RequirementRecord)
def get_requirement(id: str, include_deleted: bool = False):
    project = service.locate("requirements", id)
    return service.get_data(project, "requirements", id, deleted=include_deleted)


def edit_requirement(identifier, operation, data, request, dry_run):
    project = service.locate("requirements", identifier)
    return service.requirements(project, operation, payload(data), *identity(request), dry_run, identifier)


@router.patch("/requirements/{id}", response_model=RequirementWrite)
def update_requirement(id: str, data: RequirementPatch, request: Request, dry_run: bool = False):
    return edit_requirement(id, "update", data, request, dry_run)


@router.delete("/requirements/{id}", response_model=RequirementWrite)
def delete_requirement(id: str, data: Versioned, request: Request, dry_run: bool = False):
    return edit_requirement(id, "delete", data, request, dry_run)


@router.post("/requirements/{id}/move", response_model=RequirementWrite)
def move_requirement(id: str, data: Move, request: Request, dry_run: bool = False):
    return edit_requirement(id, "move", data, request, dry_run)


@router.post("/requirements/{id}/restore", response_model=RequirementWrite)
def restore_requirement(id: str, data: Versioned, request: Request, dry_run: bool = False):
    return edit_requirement(id, "restore", data, request, dry_run)


@router.post("/requirements/{id}/rollback", response_model=RequirementWrite)
def rollback_requirement(id: str, data: Rollback, request: Request, dry_run: bool = False):
    return edit_requirement(id, "rollback", data, request, dry_run)


@router.get("/requirements/{id}/history")
def requirement_history(id: str):
    project = service.locate("requirements", id)
    return service.get_data(project, "history", requirement_id=id)


@router.get("/projects/{project_id}/traceability", response_model=Traceability)
def project_traceability(project_id: str):
    return service.get_traceability(project_id)


@router.get("/projects/{project_id}/gaps", response_model=dict[str, list[RequirementRecord]])
def project_gaps(project_id: str):
    return service.get_gaps(project_id)


@router.post("/diagrams/validate")
def validate_diagram(data: DiagramSource):
    return renderer.validate(data.type, data.source)


def image_response(kind, source, format, filename=None):
    headers = {"Content-Security-Policy": "sandbox; default-src 'none'", "X-Content-Type-Options": "nosniff"}
    if filename:
        headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return Response(renderer.image(kind, source, format),
                    media_type="image/svg+xml" if format == "svg" else "image/png", headers=headers)


@router.post("/diagrams/render")
def render_source(data: RenderSource):
    return image_response(data.type, data.source, data.format)


@router.get("/diagrams/{id}/render")
def render_diagram(id: str, format: ImageFormat = "svg", download: bool = False):
    project = service.locate("diagrams", id)
    data = service.get_data(project, "diagrams", id)
    return image_response(data["type"], data["source"], format, f"diagram-{id}.{format}" if download else None)


@router.post("/projects/{project_id}/exports/preview")
def preview_document(project_id: str, data: Preview):
    return documents.preview(project_id, data.document_type, data.filters.model_dump())


@router.post("/projects/{project_id}/exports", status_code=201)
def create_export(project_id: str, data: Export, request: Request, dry_run: bool = False):
    return documents.export(project_id, data.document_type, data.format,
                            data.filters.model_dump(), identity(request)[0], dry_run, data.expected_version)


@router.get("/projects/{project_id}/exports/{id}/file")
def download_export(project_id: str, id: str):
    artifact = service.get_data(project_id, "exports", id)
    path = service.store.directory / "exports" / Path(artifact["filename"]).name
    if not path.is_file():
        raise Problem(404, "Export file not found")
    media_type = "application/pdf" if artifact["format"] == "pdf" else "text/markdown"
    return FileResponse(path, media_type=media_type, filename=artifact["filename"])


@router.get("/projects/{project_id}/backup")
def download_backup(project_id: str, format: BackupFormat = "json"):
    media_type = "application/json" if format == "json" else "text/csv"
    headers = {"Content-Disposition": f'attachment; filename="reqbase-backup.{format}"'}
    return Response(service.backup(project_id, format), media_type=media_type, headers=headers)


@router.post("/projects/{project_id}/import", response_model=RequirementWrite)
def import_requirements(project_id: str, data: Import, request: Request, dry_run: bool = False):
    return service.import_requirements(project_id, data.format, data.content, *identity(request),
                                       dry_run, data.expected_version)


def register_collection(collection, create_model=None, patch_model=None):
    path = "/projects/{project_id}/" + collection

    def listing(project_id: str, deleted: bool = False, requirement_id: str | None = None):
        return service.get_data(project_id, collection, deleted=deleted, requirement_id=requirement_id)

    def get(project_id: str, id: str, include_deleted: bool = False):
        return service.get_data(project_id, collection, id, deleted=include_deleted)

    router.add_api_route(path, listing, methods=["GET"], name=f"list_{collection}", tags=[collection])
    router.add_api_route(path + "/{id}", get, methods=["GET"], name=f"get_{collection}", tags=[collection])
    if not create_model:
        return

    def create(project_id: str, data, request: Request, dry_run: bool = False):
        return service.save_item(project_id, collection, payload(data), identity(request)[0], dry_run)

    def update(project_id: str, id: str, data, request: Request, dry_run: bool = False):
        return service.save_item(project_id, collection, payload(data), identity(request)[0], dry_run, id)

    def delete(project_id: str, id: str, data: Versioned, request: Request, dry_run: bool = False):
        return service.save_item(project_id, collection, payload(data), identity(request)[0], dry_run, id, "delete")

    def restore(project_id: str, id: str, data: Versioned, request: Request, dry_run: bool = False):
        return service.save_item(project_id, collection, payload(data), identity(request)[0], dry_run, id, "restore")

    create.__annotations__["data"] = create_model
    update.__annotations__["data"] = patch_model
    router.add_api_route(path, create, methods=["POST"], status_code=201, name=f"create_{collection}", tags=[collection])
    router.add_api_route(path + "/{id}", update, methods=["PATCH"], name=f"update_{collection}", tags=[collection])
    router.add_api_route(path + "/{id}", delete, methods=["DELETE"], name=f"delete_{collection}", tags=[collection])
    router.add_api_route(path + "/{id}/restore", restore, methods=["POST"], name=f"restore_{collection}", tags=[collection])


for collection, (_, create_model, patch_model, _) in RESOURCES.items():
    register_collection(collection, create_model, patch_model)
for collection in ("history", "exports"):
    register_collection(collection)

app.include_router(router, dependencies=[Depends(check_token), Depends(validate_actor)])
app.include_router(router, prefix="/ui", include_in_schema=False)
app.mount("/mcp", mcp_app)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/", include_in_schema=False)
def index():
    source = (STATIC / "index.html").read_text(encoding="utf-8")
    manifest = STATIC / "assets" / ".vite" / "manifest.json"
    if manifest.is_file():
        entry = json.loads(manifest.read_text(encoding="utf-8"))["web/app.js"]
        script = f'<script type="module" src="/static/assets/{entry["file"]}"></script>'
        links = "".join(f'<link rel="stylesheet" href="/static/assets/{css}">' for css in entry.get("css", []))
    else:
        return HTMLResponse("<h1>ReqBase</h1><p>Build the frontend with npm run build, or start Docker Compose.</p>",
                            status_code=503)
    return HTMLResponse(source.replace("<!-- APP -->", links + script))
