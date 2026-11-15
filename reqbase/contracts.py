from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

Status = Literal["Draft", "In Review", "Approved", "Implemented", "Rejected"]
Priority = Literal["Must", "Should", "Could", "Won't"]
Kind = Literal["BR", "FR", "NFR"]
DiagramType = Literal["mermaid", "plantuml"]
DiagramKind = Literal["sequence", "class", "activity", "state", "ER", "component", "use case", "flowchart", "other"]
SectionKey = Literal["purpose", "scope", "stakeholders", "business_goals", "assumptions",
                     "constraints", "introduction", "overview", "interfaces"]
LinkType = Literal["depends_on", "relates_to", "conflicts_with"]
DocType = Literal["BRD", "SRS"]
DocFormat = Literal["md", "pdf"]
ImageFormat = Literal["svg", "png"]
BackupFormat = Literal["csv", "json"]
Position = Annotated[int, Field(ge=0, strict=True)]
Version = Annotated[int, Field(ge=1, strict=True)]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Versioned(Input):
    expected_version: Version


class ScopedCreate(Input):
    expected_version: Position | None = None


class ProjectFields(Input):
    title: str | None = None
    prefix: str | None = None
    description: str | None = None
    customer: str | None = None
    document_version: str | None = None
    document_date: str | None = None
    authors: list[str] = Field(default_factory=list)
    locale: Literal["ru", "en"] | None = None


class ProjectCreate(ProjectFields, ScopedCreate):
    title: str


class ProjectPatch(ProjectFields, Versioned):
    pass


class RequirementFields(Input):
    title: str | None = None
    type: Kind | None = None
    status: Status | None = None
    priority: Priority | None = None
    description: str | None = None
    source: str | None = None
    tags: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)


class RequirementNode(RequirementFields):
    title: str
    position: Position | None = None
    children: list[RequirementNode] = Field(default_factory=list)


class RequirementCreate(RequirementNode, ScopedCreate):
    parent_id: str | None = None


class RequirementPatch(RequirementFields, Versioned):
    pass


class BulkPatchItem(RequirementPatch):
    id: str


class BulkPatch(Input):
    items: list[BulkPatchItem] = Field(min_length=1)


class BulkCreate(ScopedCreate):
    items: list[RequirementNode] = Field(min_length=1)
    parent_id: str | None = None


class Move(Versioned):
    parent_id: str | None = None
    position: Position | None = None


class Rollback(Versioned):
    history_id: str


class Filters(Input):
    q: str | None = None
    type: Kind | None = None
    status: Status | None = None
    priority: Priority | None = None
    tag: str | None = None
    has_diagrams: bool | None = None
    updated_by: str | None = None


class TreeFilters(Filters):
    depth: Annotated[int, Field(ge=0)] | None = None


class DiagramSource(Input):
    type: DiagramType
    source: str


class RenderSource(DiagramSource):
    format: ImageFormat = "svg"


class DiagramCreate(DiagramSource, ScopedCreate):
    title: str
    kind: DiagramKind = "other"
    requirement_ids: list[str] = Field(default_factory=list)


class DiagramPatch(Versioned):
    type: DiagramType | None = None
    source: str | None = None
    title: str | None = None
    kind: DiagramKind | None = None
    requirement_ids: list[str] = Field(default_factory=list)


class CommentCreate(ScopedCreate):
    requirement_id: str
    body: str


class CommentPatch(Versioned):
    body: str


class AttachmentCreate(ScopedCreate):
    requirement_id: str
    diagram_id: str


class AttachmentPatch(Versioned):
    requirement_id: str | None = None
    diagram_id: str | None = None


class LinkCreate(ScopedCreate):
    source_id: str
    target_id: str
    type: LinkType


class LinkPatch(Versioned):
    source_id: str | None = None
    target_id: str | None = None
    type: LinkType | None = None


class SectionCreate(ScopedCreate):
    key: SectionKey
    body: str


class SectionPatch(Versioned):
    key: SectionKey | None = None
    body: str | None = None


class TermCreate(ScopedCreate):
    term: str
    definition: str


class TermPatch(Versioned):
    term: str | None = None
    definition: str | None = None


class ViewCreate(ScopedCreate):
    title: str
    mode: Literal["tree", "flat", "kanban"] = "tree"
    filters: Filters = Field(default_factory=Filters)


class ViewPatch(Versioned):
    title: str | None = None
    mode: Literal["tree", "flat", "kanban"] | None = None
    filters: Filters = Field(default_factory=Filters)


class ExportFilters(Input):
    approved_only: bool = False
    exclude_rejected: bool = False
    branch_ids: list[str] = Field(default_factory=list)


class Preview(Input):
    document_type: DocType
    filters: ExportFilters = Field(default_factory=ExportFilters)


class Export(Preview, ScopedCreate):
    format: DocFormat


class Import(ScopedCreate):
    format: BackupFormat
    content: str


class RestoreBackup(ScopedCreate):
    content: str


class RequirementRecord(BaseModel):
    id: str
    project_id: str
    code: str
    type: Kind
    parent_id: str | None
    title: str
    description: str
    acceptance_criteria: list[str]
    status: Status
    priority: Priority
    tags: list[str]
    source: str
    order: int
    version: int
    created_at: str
    updated_at: str
    deleted_at: str | None
    created_by: str
    updated_by: str
    diagram_count: int


class TreeRequirement(RequirementRecord):
    matches: bool
    children: list[TreeRequirement]


class CodeChange(BaseModel):
    id: str
    code: str
    previous_code: str
    version: int


class RequirementWrite(BaseModel):
    items: list[RequirementRecord]
    renumbered: list[CodeChange]
    dry_run: bool


class TraceBranch(BaseModel):
    br: RequirementRecord
    fr: list[RequirementRecord]
    nfr: list[RequirementRecord]


class Traceability(BaseModel):
    branches: list[TraceBranch]
    orphans: list[RequirementRecord]


def payload(model):
    return model.model_dump(exclude_unset=True)
