from sqlalchemy import select

from .auth import DEV_USER_ID
from .config import get_settings
from .db import Base, SessionLocal, UserRecord, engine
from .repository import ProjectRepository
from .schemas import ProjectCreate, VersionCreate


def seed() -> None:
    settings = get_settings()
    Base.metadata.create_all(engine)
    with SessionLocal() as session:
        user = session.get(UserRecord, DEV_USER_ID)
        if not user:
            user = UserRecord(
                id=DEV_USER_ID,
                email=settings.development_user_email,
                display_name=settings.development_user_name,
            )
            session.add(user)
            session.commit()
        existing = session.scalar(select(UserRecord).where(UserRecord.id == DEV_USER_ID))
        projects, _ = ProjectRepository(session).list_owned(existing.id, 1, 100)
        if not any(p.title == "The Red Key" for p in projects):
            repo = ProjectRepository(session)
            project = repo.create(
                existing.id,
                ProjectCreate(
                    title="The Red Key",
                    genre="Mystery thriller",
                    intended_audience="Adult mystery audiences",
                    target_duration_seconds=240,
                    description="A synthetic short film for EchoCut development.",
                ),
            )
            repo.create_version(
                project,
                existing.id,
                VersionCreate(
                    label="Cut A", description="Original doorway reaction and key close-up."
                ),
            )


if __name__ == "__main__":
    seed()
