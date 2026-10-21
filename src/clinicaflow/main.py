from fastapi import FastAPI

from clinicaflow.customers.router import router as customers_router

app = FastAPI(
    title="Clinicaflow API",
    description="API financeira e fiscal para uma clínica.",
    version="0.1.0",
)


@app.get("/health", tags=["Sistema"])
def health_check():
    return {
        "status": "ok",
        "application": "clinicaflow",
    }

app.include_router(customers_router)