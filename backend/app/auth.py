"""登录与访问令牌（HMAC 签名，无额外依赖）。"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any

from fastapi import Depends, HTTPException, Request

from app.config import get_settings
from app.db import SessionLocal
from app.models import User

TOKEN_TTL_SECONDS = 7 * 24 * 3600


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
    return "pbkdf2$120000${}${}".format(
        base64.b64encode(salt).decode(),
        base64.b64encode(digest).decode(),
    )


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iterations, salt_b64, hash_b64 = stored.split("$")
        if algo != "pbkdf2":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            base64.b64decode(salt_b64),
            int(iterations),
        )
        return hmac.compare_digest(digest, base64.b64decode(hash_b64))
    except Exception:  # noqa: BLE001
        return False


def create_token(user: User) -> str:
    settings = get_settings()
    payload = {
        "uid": user.id,
        "tenant": user.tenant_id,
        "role": user.role,
        "exp": int(time.time()) + TOKEN_TTL_SECONDS,
    }
    raw = base64.urlsafe_b64encode(json.dumps(payload, ensure_ascii=False).encode()).decode()
    signature = hmac.new(settings.auth_secret.encode(), raw.encode(), hashlib.sha256).hexdigest()
    return f"{raw}.{signature}"


def verify_token(token: str) -> dict[str, Any] | None:
    settings = get_settings()
    try:
        raw, signature = token.split(".")
        expected = hmac.new(settings.auth_secret.encode(), raw.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return None
        payload = json.loads(base64.urlsafe_b64decode(raw.encode()).decode())
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:  # noqa: BLE001
        return None


def require_auth(request: Request) -> dict[str, Any]:
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录")
    payload = verify_token(header[len("Bearer ") :].strip())
    if payload is None:
        raise HTTPException(status_code=401, detail="登录已过期")
    return payload


def require_roles(*roles: str):
    def dependency(payload: dict = Depends(require_auth)) -> dict:
        if payload.get("role") not in roles:
            raise HTTPException(status_code=403, detail="当前角色无权限执行此操作")
        return payload

    return dependency


def load_user(user_id: str) -> User | None:
    with SessionLocal() as db:
        return db.get(User, user_id)
