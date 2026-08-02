import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from .db import ActivityRecord, FilmVersionRecord, ProjectRecord
from .schemas import ProjectCreate, ProjectUpdate, VersionCreate


class ProjectRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, owner_id: uuid.UUID, data: ProjectCreate) -> ProjectRecord:
        project = ProjectRecord(owner_id=owner_id, **data.model_dump())
        self.session.add(project)
        self.session.flush()
        self.activity(project.id, owner_id, "project.created", f'Created project "{project.title}"')
        self.session.commit()
        return self.get_owned(project.id, owner_id)

    def get_owned(self, project_id: uuid.UUID, owner_id: uuid.UUID) -> ProjectRecord | None:
        return self.session.scalar(
            select(ProjectRecord)
            .options(selectinload(ProjectRecord.versions))
            .where(ProjectRecord.id == project_id, ProjectRecord.owner_id == owner_id)
        )

    def list_owned(
        self, owner_id: uuid.UUID, page: int, size: int
    ) -> tuple[list[ProjectRecord], int]:
        query = (
            select(ProjectRecord)
            .options(selectinload(ProjectRecord.versions))
            .where(ProjectRecord.owner_id == owner_id)
        )
        total = self.session.scalar(select(func.count()).select_from(query.subquery())) or 0
        items = list(
            self.session.scalars(
                query.order_by(ProjectRecord.updated_at.desc())
                .offset((page - 1) * size)
                .limit(size)
            )
        )
        return items, total

    def update(
        self, project: ProjectRecord, actor_id: uuid.UUID, data: ProjectUpdate
    ) -> ProjectRecord:
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(project, key, value)
        self.activity(project.id, actor_id, "project.updated", f'Updated project "{project.title}"')
        self.session.commit()
        return self.get_owned(project.id, actor_id)  # type: ignore[return-value]

    def create_version(
        self, project: ProjectRecord, actor_id: uuid.UUID, data: VersionCreate
    ) -> FilmVersionRecord:
        existing = self.session.scalar(
            select(FilmVersionRecord).where(
                FilmVersionRecord.project_id == project.id, FilmVersionRecord.label == data.label
            )
        )
        if existing:
            raise ValueError(f"{data.label} already exists for this project")
        version = FilmVersionRecord(
            project_id=project.id,
            label=data.label,
            version_number=1 if data.label == "Cut A" else 2,
            description=data.description,
        )
        self.session.add(version)
        self.session.flush()
        self.activity(
            project.id,
            actor_id,
            "film_version.created",
            f"Created {data.label}",
            {"version_id": str(version.id)},
        )
        self.session.commit()
        return version

    def activity(
        self,
        project_id: uuid.UUID,
        actor_id: uuid.UUID,
        event_type: str,
        message: str,
        metadata: dict | None = None,
    ) -> None:
        self.session.add(
            ActivityRecord(
                project_id=project_id,
                actor_id=actor_id,
                event_type=event_type,
                message=message,
                event_metadata=metadata or {},
            )
        )
