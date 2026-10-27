from datetime import date, datetime, time, timedelta
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from clinicaflow.agenda.models import Appointment, Intake
from clinicaflow.auth.models import User
from clinicaflow.core.database import get_db
from clinicaflow.core.security import AdminUser, CurrentUser
from clinicaflow.customers.models import Customer

router = APIRouter(prefix="/agenda", tags=["Agenda"])
DbSession = Annotated[Session, Depends(get_db)]
CLINIC_TIMEZONE = ZoneInfo("America/Sao_Paulo")


class IntakeCreate(BaseModel):
    customer_name: str = Field(min_length=2, max_length=150)
    customer_document: str | None = Field(default=None, min_length=11, max_length=14)
    customer_email: EmailStr | None = None
    customer_phone: str | None = Field(default=None, max_length=20)
    employee_id: int | None = Field(default=None, gt=0)
    service: str = Field(min_length=2, max_length=200)
    requested_at: datetime
    notes: str | None = None


class AppointmentUpdate(BaseModel):
    starts_at: datetime | None = None
    status: Literal["scheduled", "completed", "no_show", "cancelled"] | None = None


def as_local(value: datetime) -> datetime:
    # Agenda uses the clinic's local wall-clock time, matching the browser date/time controls.
    if value.tzinfo is not None:
        return value.astimezone(CLINIC_TIMEZONE).replace(tzinfo=None)
    return value


def appointment_view(appointment: Appointment, customer: Customer, employee: User) -> dict[str, object]:
    return {
        "id": appointment.id,
        "customer_id": customer.id,
        "customer_name": customer.name,
        "customer_phone": customer.phone,
        "employee_id": employee.id,
        "employee_name": employee.name,
        "service": appointment.service,
        "starts_at": appointment.starts_at.isoformat(timespec="minutes"),
        "status": appointment.status,
        "notes": appointment.notes,
    }


@router.get("/employees")
def agenda_employees(_admin: AdminUser, db: DbSession):
    staff = db.scalars(select(User).where(User.active.is_(True)).order_by(User.name)).all()
    return [{"id": person.id, "name": person.name, "role": person.role} for person in staff]


@router.post("/intakes", status_code=status.HTTP_201_CREATED)
def create_intake(data: IntakeCreate, user: CurrentUser, db: DbSession):
    employee_id = data.employee_id if user.role == "admin" else user.id
    if employee_id is None:
        raise HTTPException(status_code=422, detail="Selecione o funcionário responsável.")
    employee = db.get(User, employee_id)
    if employee is None or not employee.active or employee.role != "employee":
        raise HTTPException(status_code=404, detail="Funcionário ativo não encontrado.")
    customer = Customer(
        name=data.customer_name.strip(), document=data.customer_document or None,
        email=str(data.customer_email).lower() if data.customer_email else None,
        phone=data.customer_phone or None,
    )
    db.add(customer)
    try:
        db.flush()
        intake = Intake(
            customer_id=customer.id, employee_id=employee.id, service=data.service.strip(),
            requested_at=as_local(data.requested_at), notes=data.notes,
        )
        db.add(intake)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Documento já cadastrado; o formulário não foi criado.") from exc
    return {"id": intake.id, "customer_name": customer.name, "employee_id": employee.id, "status": intake.status}


@router.post("/load-day")
def load_day(
    user: CurrentUser,
    db: DbSession,
    requested_day: date = Query(alias="date"),
    employee_id: int | None = Query(default=None, gt=0),
):
    if user.role == "employee":
        employee_id = user.id
    if employee_id is None:
        raise HTTPException(status_code=422, detail="Selecione um funcionário para carregar a agenda.")
    employee = db.get(User, employee_id)
    if employee is None or employee.role != "employee" or not employee.active:
        raise HTTPException(status_code=404, detail="Funcionário ativo não encontrado.")
    begin = datetime.combine(requested_day, time.min)
    finish = begin + timedelta(days=1)
    pending = db.scalars(
        select(Intake).where(
            Intake.employee_id == employee_id,
            Intake.status == "pending",
            Intake.requested_at >= begin,
            Intake.requested_at < finish,
        ).order_by(Intake.requested_at, Intake.id)
    ).all()
    created = 0
    for intake in pending:
        appointment = Appointment(
            customer_id=intake.customer_id, employee_id=intake.employee_id,
            intake_id=intake.id, service=intake.service, starts_at=intake.requested_at,
            notes=intake.notes, status="scheduled",
        )
        db.add(appointment)
        intake.status = "scheduled"
        created += 1
    db.commit()
    return {"created": created, "date": requested_day.isoformat(), "employee_id": employee_id}


@router.get("/appointments")
def list_appointments(
    start: date,
    end: date,
    user: CurrentUser,
    db: DbSession,
    employee_id: int | None = Query(default=None, gt=0),
):
    if end < start or (end - start).days > 45:
        raise HTTPException(status_code=422, detail="O período deve ter no máximo 46 dias.")
    statement = (
        select(Appointment, Customer, User)
        .join(Customer, Customer.id == Appointment.customer_id)
        .join(User, User.id == Appointment.employee_id)
        .where(
            Appointment.starts_at >= datetime.combine(start, time.min),
            Appointment.starts_at < datetime.combine(end + timedelta(days=1), time.min),
        )
        .order_by(Appointment.starts_at, Appointment.id)
    )
    if user.role == "employee":
        statement = statement.where(Appointment.employee_id == user.id)
    elif employee_id is not None:
        statement = statement.where(Appointment.employee_id == employee_id)
    rows = db.execute(statement).all()
    return [appointment_view(appt, customer, employee) for appt, customer, employee in rows]


@router.patch("/appointments/{appointment_id}")
def update_appointment(appointment_id: int, data: AppointmentUpdate, user: CurrentUser, db: DbSession):
    appointment = db.get(Appointment, appointment_id)
    if appointment is None:
        raise HTTPException(status_code=404, detail="Atendimento não encontrado.")
    if user.role == "employee" and appointment.employee_id != user.id:
        raise HTTPException(status_code=404, detail="Atendimento não encontrado.")
    changes = data.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=400, detail="Informe uma data/horário ou um status.")
    if "starts_at" in changes:
        if changes["starts_at"] is None:
            raise HTTPException(status_code=422, detail="Informe uma data e horário válidos.")
        appointment.starts_at = as_local(changes["starts_at"])
        if appointment.status != "completed":
            appointment.status = "scheduled"
    if "status" in changes and changes["status"] is not None:
        appointment.status = changes["status"]
    db.commit()
    customer = db.get(Customer, appointment.customer_id)
    employee = db.get(User, appointment.employee_id)
    return appointment_view(appointment, customer, employee)
