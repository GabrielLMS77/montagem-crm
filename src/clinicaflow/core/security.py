from datetime import UTC, datetime, timedelta
import hashlib
import hmac
import ipaddress
import secrets

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from typing import Annotated

from clinicaflow.auth.models import LoginSession, User
from clinicaflow.core.database import get_db


DbSession = Annotated[Session, Depends(get_db)]
SESSION_COOKIE = "clinicaflow_session"
SESSION_HOURS = 12


def is_local_request(request: Request) -> bool:
    try:
        return ipaddress.ip_address(request.client.host if request.client else "").is_loopback
    except ValueError:
        return False


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=64)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, salt_hex, digest_hex = encoded.split("$", 2)
        if algorithm != "scrypt":
            return False
        digest = hashlib.scrypt(password.encode("utf-8"), salt=bytes.fromhex(salt_hex), n=2**14, r=8, p=1, dklen=64)
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def create_session(user: User, db: Session, response, request: Request) -> None:
    token = secrets.token_urlsafe(48)
    expires = datetime.now(UTC) + timedelta(hours=SESSION_HOURS)
    db.add(LoginSession(token_hash=hashlib.sha256(token.encode()).hexdigest(), user_id=user.id, expires_at=expires))
    db.commit()
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="strict",
        max_age=SESSION_HOURS * 3600,
        path="/",
    )


def get_current_user(request: Request, db: DbSession) -> User:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Faça login para continuar.")
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    session = db.scalar(select(LoginSession).where(LoginSession.token_hash == token_hash))
    if session is None:
        raise HTTPException(status_code=401, detail="Sessão inválida ou expirada.")
    expiry = session.expires_at.replace(tzinfo=UTC) if session.expires_at.tzinfo is None else session.expires_at
    if expiry <= datetime.now(UTC):
        db.delete(session)
        db.commit()
        raise HTTPException(status_code=401, detail="Sessão inválida ou expirada.")
    user = db.get(User, session.user_id)
    if user is None or not user.active:
        raise HTTPException(status_code=401, detail="Conta inativa.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_admin(user: CurrentUser) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Acesso restrito ao administrador.")
    return user


AdminUser = Annotated[User, Depends(require_admin)]
