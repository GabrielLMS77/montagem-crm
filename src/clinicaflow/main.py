from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from clinicaflow.customers.router import router as customers_router
from clinicaflow.fiscal.nfse.router import router as nfse_router
from clinicaflow.sales.router import router as sales_router

app = FastAPI(
    title="Clinicaflow",
    description="Gestão de clientes e vendas para a clínica.",
    version="0.1.0",
)


@app.get("/health", tags=["Sistema"])
def health_check():
    return {"status": "ok", "application": "clinicaflow"}


@app.get("/", include_in_schema=False)
def crm_home():
    return FileResponse(Path(__file__).parent / "web" / "index.html")


app.include_router(customers_router)
app.include_router(sales_router)
app.include_router(nfse_router)
