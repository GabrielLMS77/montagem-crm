from datetime import UTC, datetime
import hashlib
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from clinicaflow.auth.models import LoginSession, User
from clinicaflow.core.database import get_db
from clinicaflow.core.security import (
    AdminUser, CurrentUser, SESSION_COOKIE, create_session, hash_password,
    is_local_request, verify_password,
)

router = APIRouter(prefix="/auth", tags=["Autenticação"])
DbSession = Annotated[Session, Depends(get_db)]


class BootstrapData(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=12, max_length=256)


class LoginData(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class EmployeeCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=12, max_length=256)


class EmployeeUpdate(BaseModel):
    active: bool


class PasswordUpdate(BaseModel):
    password: str = Field(min_length=12, max_length=256)


class AdminRecoveryData(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=12, max_length=256)


def user_view(user: User) -> dict[str, object]:
    return {"id": user.id, "name": user.name, "email": user.email, "role": user.role, "active": user.active}


@router.get("/setup-status")
def setup_status(db=Depends(get_db)):
    return {"needs_setup": db.scalar(select(func.count(User.id))) == 0}


@router.post("/bootstrap", status_code=status.HTTP_201_CREATED)
def bootstrap(data: BootstrapData, request: Request, response: Response, db=Depends(get_db)):
    if not is_local_request(request):
        raise HTTPException(status_code=403, detail="Configuração inicial permitida apenas no computador local.")
    if db.scalar(select(func.count(User.id))) != 0:
        raise HTTPException(status_code=409, detail="O administrador inicial já foi configurado.")
    user = User(name=data.name.strip(), email=str(data.email).lower(), password_hash=hash_password(data.password), role="admin", active=True)
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="A configuração inicial já foi concluída.") from exc
    create_session(user, db, response, request)
    return user_view(user)


@router.post("/login")
def login(data: LoginData, request: Request, response: Response, db=Depends(get_db)):
    user = db.scalar(select(User).where(User.email == str(data.email).lower()))
    if user is None or not user.active or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="E-mail ou senha inválidos.")
    create_session(user, db, response, request)
    return user_view(user)


@router.post("/recover-admin")
def recover_admin(data: AdminRecoveryData, request: Request, response: Response, db: DbSession):
    # Keep account recovery unavailable through public hostnames or reverse proxies.
    if not is_local_request(request) or request.url.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise HTTPException(status_code=403, detail="A recuperação só pode ser feita no computador local.")
    admins = db.scalars(select(User).where(User.role == "admin").order_by(User.id)).all()
    if len(admins) != 1:
        raise HTTPException(status_code=409, detail="A recuperação exige exatamente uma conta administradora.")
    admin = admins[0]
    admin.name = data.name.strip()
    admin.email = str(data.email).lower()
    admin.password_hash = hash_password(data.password)
    db.query(LoginSession).filter(LoginSession.user_id == admin.id).delete(synchronize_session=False)
    try:
        db.commit()
        db.refresh(admin)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Este e-mail já está associado a outra conta.") from exc
    create_session(admin, db, response, request)
    return user_view(admin)


@router.get("/me")
def me(user: CurrentUser):
    return user_view(user)


@router.get("/status")
def session_status(request: Request, db: DbSession):
    token = request.cookies.get(SESSION_COOKIE)
    user = None
    if token:
        session = db.scalar(select(LoginSession).where(LoginSession.token_hash == hashlib.sha256(token.encode()).hexdigest()))
        if session:
            expiry = session.expires_at.replace(tzinfo=UTC) if session.expires_at.tzinfo is None else session.expires_at
            if expiry > datetime.now(UTC):
                candidate = db.get(User, session.user_id)
                if candidate and candidate.active:
                    user = user_view(candidate)
    return {"authenticated": user is not None, "user": user, "needs_setup": db.scalar(select(func.count(User.id))) == 0}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db=Depends(get_db)):
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        session = db.scalar(select(LoginSession).where(LoginSession.token_hash == hashlib.sha256(token.encode()).hexdigest()))
        if session:
            db.delete(session)
            db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/", httponly=True, samesite="strict")


@router.get("/employees")
def employees(_admin: AdminUser, db: DbSession):
    users = db.scalars(select(User).where(User.role == "employee").order_by(User.name)).all()
    return [user_view(user) for user in users]


@router.post("/employees", status_code=status.HTTP_201_CREATED)
def create_employee(data: EmployeeCreate, _admin: AdminUser, db: DbSession):
    user = User(name=data.name.strip(), email=str(data.email).lower(), password_hash=hash_password(data.password), role="employee", active=True)
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Já existe uma conta com este e-mail.") from exc
    return user_view(user)


@router.patch("/employees/{user_id}")
def update_employee(user_id: int, data: EmployeeUpdate, _admin: AdminUser, db: DbSession):
    user = db.get(User, user_id)
    if user is None or user.role != "employee":
        raise HTTPException(status_code=404, detail="Funcionário não encontrado.")
    user.active = data.active
    db.commit()
    return user_view(user)


@router.put("/employees/{user_id}/password", status_code=status.HTTP_204_NO_CONTENT)
def reset_employee_password(user_id: int, data: PasswordUpdate, _admin: AdminUser, db: DbSession):
    user = db.get(User, user_id)
    if user is None or user.role != "employee":
        raise HTTPException(status_code=404, detail="Funcionário não encontrado.")
    user.password_hash = hash_password(data.password)
    db.query(LoginSession).filter(LoginSession.user_id == user.id).delete(synchronize_session=False)
    db.commit()
