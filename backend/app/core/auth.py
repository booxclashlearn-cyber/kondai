from dataclasses import dataclass
from typing import Optional
from fastapi import Header, HTTPException, status
from app.core.config import get_settings
from app.core.repository import get_repository

@dataclass(frozen=True)
class Actor:
    user_id: str
    workspace_id: str
    role: str

def _verify_firebase(token: str) -> dict:
    import firebase_admin
    from firebase_admin import auth, credentials
    settings=get_settings()
    try: app=firebase_admin.get_app("kondai-auth")
    except ValueError:
        credential=credentials.Certificate(settings.firebase_service_account_path) if settings.firebase_service_account_path else credentials.ApplicationDefault()
        app=firebase_admin.initialize_app(credential,{"projectId":settings.firebase_project_id or None},name="kondai-auth")
    return auth.verify_id_token(token,app=app)

async def get_actor(authorization: Optional[str]=Header(default=None),x_user_id: Optional[str]=Header(default=None),x_workspace_id: Optional[str]=Header(default=None)) -> Actor:
    settings=get_settings()
    if settings.auth_mode.lower()=="dev": return Actor(x_user_id or settings.dev_user_id,x_workspace_id or settings.dev_workspace_id,"owner")
    if not authorization or not authorization.startswith("Bearer "): raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail="Missing Firebase bearer token.")
    try: decoded=_verify_firebase(authorization.removeprefix("Bearer ").strip())
    except Exception as exc: raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail="Invalid authentication token.") from exc
    workspace_id=x_workspace_id or decoded.get("workspace_id")
    if not workspace_id: raise HTTPException(status_code=400,detail="Select a workspace.")
    member=get_repository().get("members",decoded["uid"],workspace_id)
    if not member: raise HTTPException(status_code=403,detail="You do not belong to this workspace.")
    return Actor(decoded["uid"],workspace_id,member.get("role","viewer"))
