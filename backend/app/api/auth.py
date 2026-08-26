from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth import create_token, hash_password, require_auth, verify_password
from app.db import SessionLocal
from app.models import Tenant, User

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class LoginIn(BaseModel):
    username: str
    password: str


class PasswordIn(BaseModel):
    old_password: str
    new_password: str


class UserCreateIn(BaseModel):
    username: str
    password: str
    display_name: str | None = None
    role: str = "operator"


def _user_out(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
        "enabled": user.enabled,
        "tenant_id": user.tenant_id,
    }


@router.post("/login")
def login(payload: LoginIn) -> dict:
    with SessionLocal() as db:
        user = db.query(User).filter(User.username == payload.username).first()
        if user is None or not user.enabled or not verify_password(payload.password, user.password_hash):
            raise HTTPException(status_code=401, detail="用户名或密码错误")
        token = create_token(user)
        tenant = db.get(Tenant, user.tenant_id)
        return {"token": token, "user": _user_out(user), "industry_id": tenant.industry_id if tenant else None}


@router.get("/me")
def me(auth: dict = Depends(require_auth)) -> dict:
    with SessionLocal() as db:
        user = db.get(User, auth["uid"])
        if user is None:
            raise HTTPException(status_code=401, detail="用户不存在")
        return {"user": _user_out(user)}


@router.post("/password")
def change_password(
    payload: PasswordIn,
    auth: dict = Depends(require_auth),
) -> dict:
    with SessionLocal() as db:
        user = db.get(User, auth["uid"])
        if user is None or not verify_password(payload.old_password, user.password_hash):
            raise HTTPException(status_code=400, detail="原密码错误")
        user.password_hash = hash_password(payload.new_password)
        db.commit()
        return {"ok": True}


@router.get("/users")
def list_users(auth: dict = Depends(require_auth)) -> list[dict]:
    if auth.get("role") != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    with SessionLocal() as db:
        rows = db.query(User).filter(User.tenant_id == auth["tenant"]).all()
        return [_user_out(row) for row in rows]


@router.post("/users")
def create_user(
    payload: UserCreateIn,
    auth: dict = Depends(require_auth),
) -> dict:
    if auth.get("role") != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    with SessionLocal() as db:
        if db.query(User).filter(User.username == payload.username).first():
            raise HTTPException(status_code=400, detail="用户名已存在")
        user = User(
            tenant_id=auth["tenant"],
            username=payload.username,
            password_hash=hash_password(payload.password),
            display_name=payload.display_name,
            role=payload.role,
            enabled=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return {"user": _user_out(user)}
