import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .auth import current_user
from .clickhouse import ClickHouseGateway
from .config import Settings, get_settings
from .db import (
    ActivityRecord,
    ExtractionDocumentRecord,
    ExtractionJobRecord,
    FilmVersionRecord,
    ProjectRecord,
    UserRecord,
    get_session,
)
from .extraction_service import ExtractionService
from .mcp import DisabledMCPClient, ProcessTransport, StdioMCPClient
from .repository import ProjectRepository
from .schemas import (
    ActivityOut,
    ExtractionOut,
    ExtractionUpdate,
    MediaAssetOut,
    Page,
    ProjectCreate,
    ProjectOut,
    ProjectUpdate,
    UserOut,
    VersionCreate,
    VersionOut,
)

router = APIRouter(prefix="/api/v1")
SessionDep = Annotated[Session, Depends(get_session)]
UserDep = Annotated[UserRecord, Depends(current_user)]


def repo(session: SessionDep) -> ProjectRepository:
    return ProjectRepository(session)


RepoDep = Annotated[ProjectRepository, Depends(repo)]


def require_project(project_id: uuid.UUID, user: UserDep, repository: RepoDep):
    project = repository.get_owned(project_id, user.id)
    if not project:
        raise HTTPException(404, "Project not found")
    return project


ProjectDep = Annotated[ProjectRecord, Depends(require_project)]


def require_owned_version(
    version_id: uuid.UUID, user: UserDep, session: SessionDep, repository: RepoDep
) -> FilmVersionRecord:
    version = session.get(FilmVersionRecord, version_id)
    if not version or not repository.get_owned(version.project_id, user.id):
        raise HTTPException(404, "Film version not found")
    return version


VersionDep = Annotated[FilmVersionRecord, Depends(require_owned_version)]


def extraction_out(document: ExtractionDocumentRecord, session: Session) -> ExtractionOut:
    job = session.get(ExtractionJobRecord, document.job_id)
    if not job:
        raise HTTPException(500, "Extraction job record is unavailable")
    return ExtractionOut(
        id=document.id,
        job_id=document.job_id,
        version_id=document.version_id,
        job_status=job.status,
        provider=job.provider,
        model_name=job.model_name,
        review_status=document.review_status,
        content=document.content,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


@router.get("/auth/me", response_model=UserOut, summary="Get the authenticated user")
def me(user: UserDep, settings: Annotated[Settings, Depends(get_settings)]) -> UserOut:
    result = UserOut.model_validate(user)
    return result.model_copy(update={"local_only": settings.auth_mode == "development"})


@router.post(
    "/projects", response_model=ProjectOut, status_code=201, summary="Create a film project"
)
def create_project(data: ProjectCreate, user: UserDep, repository: RepoDep) -> ProjectOut:
    return ProjectOut.model_validate(repository.create(user.id, data))


@router.get("/projects", response_model=Page, summary="List owned projects")
def list_projects(
    user: UserDep,
    repository: RepoDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> Page:
    items, total = repository.list_owned(user.id, page, page_size)
    return Page(
        items=[ProjectOut.model_validate(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/projects/{project_id}", response_model=ProjectOut, summary="Get a project")
def get_project(project: ProjectDep) -> ProjectOut:
    return ProjectOut.model_validate(project)


@router.patch("/projects/{project_id}", response_model=ProjectOut, summary="Update a project")
def update_project(
    data: ProjectUpdate, user: UserDep, repository: RepoDep, project: ProjectDep
) -> ProjectOut:
    return ProjectOut.model_validate(repository.update(project, user.id, data))


@router.post(
    "/projects/{project_id}/versions",
    response_model=VersionOut,
    status_code=201,
    summary="Create Cut A or Cut B",
)
def create_version(
    data: VersionCreate, user: UserDep, repository: RepoDep, project: ProjectDep
) -> VersionOut:
    try:
        return VersionOut.model_validate(repository.create_version(project, user.id, data))
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/projects/{project_id}/versions", response_model=Page, summary="List project versions")
def list_versions(
    session: SessionDep,
    project: ProjectDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> Page:
    values = list(
        session.scalars(
            select(FilmVersionRecord)
            .where(FilmVersionRecord.project_id == project.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return Page(
        items=[VersionOut.model_validate(value) for value in values],
        page=page,
        page_size=page_size,
        total=len(project.versions),
    )


@router.get("/versions/{version_id}", response_model=VersionOut, summary="Get a film version")
def get_version(
    version_id: uuid.UUID, user: UserDep, session: SessionDep, repository: RepoDep
) -> VersionOut:
    version = session.get(FilmVersionRecord, version_id)
    if not version or not repository.get_owned(version.project_id, user.id):
        raise HTTPException(404, "Film version not found")
    return VersionOut.model_validate(version)


@router.get("/projects/{project_id}/activity", response_model=Page, summary="List project activity")
def activity(
    session: SessionDep,
    project: ProjectDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> Page:
    query = (
        select(ActivityRecord)
        .where(ActivityRecord.project_id == project.id)
        .order_by(ActivityRecord.created_at.desc())
    )
    all_items = list(session.scalars(query))
    selected = all_items[(page - 1) * page_size : page * page_size]
    items = [
        ActivityOut(
            id=x.id,
            project_id=x.project_id,
            actor_id=x.actor_id,
            event_type=x.event_type,
            message=x.message,
            metadata=x.event_metadata,
            created_at=x.created_at,
        )
        for x in selected
    ]
    return Page(items=items, page=page, page_size=page_size, total=len(all_items))


@router.post(
    "/versions/{version_id}/uploads/{kind}",
    response_model=MediaAssetOut,
    status_code=201,
    summary="Upload screenplay or rough cut",
)
async def upload_media(
    kind: str,
    version: VersionDep,
    user: UserDep,
    session: SessionDep,
    repository: RepoDep,
    settings: Annotated[Settings, Depends(get_settings)],
    file: Annotated[UploadFile, File()],
    duration_seconds: int | None = Form(None),
) -> MediaAssetOut:
    if kind not in {"script", "video"}:
        raise HTTPException(404, "Upload kind not found")
    data = await file.read(500 * 1024 * 1024 + 1)
    try:
        asset = ExtractionService(session, settings).save_asset(
            version,
            kind,
            file.filename or "unnamed",
            file.content_type or "application/octet-stream",
            data,
            duration_seconds,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    repository.activity(
        version.project_id,
        user.id,
        "media.uploaded",
        f"Uploaded {kind} for {version.label}",
        {"asset_id": str(asset.id), "kind": kind},
    )
    session.commit()
    return MediaAssetOut.model_validate(asset)


@router.get(
    "/versions/{version_id}/uploads",
    response_model=list[MediaAssetOut],
    summary="List version media metadata",
)
def list_media(
    version: VersionDep,
    session: SessionDep,
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[MediaAssetOut]:
    return [
        MediaAssetOut.model_validate(asset)
        for asset in ExtractionService(session, settings).assets(version.id)
    ]


@router.post(
    "/versions/{version_id}/extract",
    response_model=ExtractionOut,
    status_code=201,
    summary="Start extraction",
)
def start_extraction(
    version: VersionDep,
    user: UserDep,
    session: SessionDep,
    repository: RepoDep,
    settings: Annotated[Settings, Depends(get_settings)],
) -> ExtractionOut:
    try:
        document = ExtractionService(session, settings).start(version)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(503, "Extraction provider is unavailable") from exc
    repository.activity(
        version.project_id,
        user.id,
        "extraction.completed",
        f"Created extraction review for {version.label}",
        {"extraction_id": str(document.id)},
    )
    session.commit()
    return extraction_out(document, session)


@router.get(
    "/versions/{version_id}/extraction",
    response_model=ExtractionOut,
    summary="Read latest extraction",
)
def get_extraction(
    version: VersionDep,
    session: SessionDep,
    settings: Annotated[Settings, Depends(get_settings)],
) -> ExtractionOut:
    document = ExtractionService(session, settings).latest(version.id)
    if not document:
        raise HTTPException(404, "Extraction not found")
    return extraction_out(document, session)


@router.patch(
    "/versions/{version_id}/extraction",
    response_model=ExtractionOut,
    summary="Apply human extraction corrections",
)
def update_extraction(
    data: ExtractionUpdate,
    version: VersionDep,
    user: UserDep,
    session: SessionDep,
    repository: RepoDep,
    settings: Annotated[Settings, Depends(get_settings)],
) -> ExtractionOut:
    service = ExtractionService(session, settings)
    document = service.latest(version.id)
    if not document:
        raise HTTPException(404, "Extraction not found")
    try:
        service.update(document, data.content)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    repository.activity(
        version.project_id,
        user.id,
        "extraction.updated",
        f"Corrected extraction for {version.label}",
    )
    session.commit()
    return extraction_out(document, session)


@router.post(
    "/versions/{version_id}/extraction/approve",
    response_model=ExtractionOut,
    summary="Approve extraction for later analysis",
)
def approve_extraction(
    version: VersionDep,
    user: UserDep,
    session: SessionDep,
    repository: RepoDep,
    settings: Annotated[Settings, Depends(get_settings)],
) -> ExtractionOut:
    service = ExtractionService(session, settings)
    document = service.latest(version.id)
    if not document:
        raise HTTPException(404, "Extraction not found")
    try:
        service.approve(document, user)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    repository.activity(
        version.project_id,
        user.id,
        "extraction.approved",
        f"Approved extraction for {version.label}",
    )
    session.commit()
    return extraction_out(document, session)


@router.get("/system/readiness", summary="Report independent dependency readiness")
async def readiness(
    session: SessionDep, settings: Annotated[Settings, Depends(get_settings)]
) -> dict:
    statuses = {"api": {"status": "ready", "detail": "API process is responding"}}
    try:
        session.execute(text("SELECT 1"))
        statuses["postgresql"] = {"status": "ready", "detail": "Metadata database connected"}
    except Exception:
        statuses["postgresql"] = {
            "status": "unavailable",
            "detail": "Metadata database connection failed",
        }
    ch_status, ch_detail = ClickHouseGateway(settings).health()
    statuses["clickhouse"] = {"status": ch_status, "detail": ch_detail}
    if settings.clickhouse_mcp_command:
        client = StdioMCPClient(
            ProcessTransport(settings.clickhouse_mcp_command, settings.clickhouse_mcp_args.split()),
            settings.request_timeout_seconds,
        )
    else:
        client = DisabledMCPClient()
    mcp_status, mcp_detail = await client.readiness()
    statuses["clickhouse_mcp"] = {"status": mcp_status, "detail": mcp_detail}
    statuses["firebase"] = {
        "status": "ready"
        if settings.auth_mode == "firebase" and settings.firebase_project_id
        else "not_configured",
        "detail": "Configured"
        if settings.firebase_project_id
        else "Firebase mode is optional locally",
    }
    statuses["google_cloud_storage"] = {
        "status": "ready"
        if settings.google_cloud_project and settings.gcs_bucket
        else "not_configured",
        "detail": "Configured"
        if settings.google_cloud_project and settings.gcs_bucket
        else "Using local storage boundary",
    }
    return {"services": statuses}
