import uuid
from typing import Annotated

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import Settings, get_settings
from .db import UserRecord, get_session

DEV_USER_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")


def current_user(
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    authorization: Annotated[str | None, Header()] = None,
) -> UserRecord:
    if settings.auth_mode == "firebase":
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(401, "Firebase bearer token required")
        try:
            from firebase_admin import auth

            decoded = auth.verify_id_token(authorization.removeprefix("Bearer "))
        except Exception as exc:
            raise HTTPException(401, "Invalid authentication token") from exc
        user_id = uuid.uuid5(uuid.NAMESPACE_URL, f"firebase:{decoded['uid']}")
        email = decoded.get("email", "firebase-user@unknown.invalid")
        name = decoded.get("name", email.split("@")[0])
    else:
        user_id, email, name = (
            DEV_USER_ID,
            settings.development_user_email,
            settings.development_user_name,
        )
    user = session.scalar(select(UserRecord).where(UserRecord.id == user_id))
    if not user:
        user = UserRecord(id=user_id, email=email, display_name=name)
        session.add(user)
        session.commit()
    return user
