from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from clinicaflow.core.database import get_db
from clinicaflow.core.security import require_admin
from clinicaflow.customers.models import Customer
from clinicaflow.sales.models import Sale
from clinicaflow.sales.schemas import SaleCreate, SaleResponse, SaleUpdate

router = APIRouter(prefix="/sales", tags=["Vendas"], dependencies=[Depends(require_admin)])
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


@router.patch("/{sale_id}", response_model=SaleResponse)
def update_sale(sale_id: int, data: SaleUpdate, db: DbSession):
    sale = db.get(Sale, sale_id)
    if sale is None:
        raise HTTPException(status_code=404, detail="Venda não encontrada.")
    changes = data.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=400, detail="Informe ao menos um campo para atualizar.")
    required_fields = {"customer_id", "description", "amount", "sale_date", "status"}
    if any(field in changes and changes[field] is None for field in required_fields):
        raise HTTPException(status_code=422, detail="Cliente, serviço, valor, data e status não podem ficar vazios.")
    if "customer_id" in changes and changes["customer_id"] is not None:
        if db.get(Customer, changes["customer_id"]) is None:
            raise HTTPException(status_code=404, detail="Cliente não encontrado.")
    for field, value in changes.items():
        setattr(sale, field, value)
    db.commit()
    db.refresh(sale)
    return sale


@router.delete("/{sale_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_sale(sale_id: int, db: DbSession):
    sale = db.get(Sale, sale_id)
    if sale is None:
        raise HTTPException(status_code=404, detail="Venda não encontrada.")
    db.delete(sale)
    db.commit()
