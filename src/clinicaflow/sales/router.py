from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from clinicaflow.core.database import get_db
from clinicaflow.customers.models import Customer
from clinicaflow.sales.models import Sale
from clinicaflow.sales.schemas import SaleCreate, SaleResponse

router = APIRouter(prefix="/sales", tags=["Vendas"])
DbSession = Annotated[Session, Depends(get_db)]


@router.post("/", response_model=SaleResponse, status_code=status.HTTP_201_CREATED)
def create_sale(data: SaleCreate, db: DbSession):
    if db.get(Customer, data.customer_id) is None:
        raise HTTPException(status_code=404, detail="Cliente não encontrado.")
    sale = Sale(**data.model_dump())
    db.add(sale)
    db.commit()
    db.refresh(sale)
    return sale


@router.get("/", response_model=list[SaleResponse])
def list_sales(
    db: DbSession,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
):
    statement = select(Sale).order_by(Sale.sale_date.desc(), Sale.id.desc()).offset(offset).limit(limit)
    return db.scalars(statement).all()
