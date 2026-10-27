from pathlib import Path

from fastapi.exceptions import RequestValidationError
from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from clinicaflow.customers.router import router as customers_router
from clinicaflow.auth.router import router as auth_router
from clinicaflow.agenda.router import router as agenda_router
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
    page = (Path(__file__).parent / "web" / "index.html").read_text(encoding="utf-8")
    guard = '<script>window.crmAdminReady=false;window.__crmRealFetch=window.fetch.bind(window);window.fetch=(input,init)=>{const url=typeof input==="string"?input:input.url;if(!window.crmAdminReady&&(url.startsWith("/customers/")||url.startsWith("/sales/")))return Promise.resolve(new Response("[]",{status:200,headers:{"Content-Type":"application/json"}}));return window.__crmRealFetch(input,init)}</script></head>'
    page = page.replace("</head>", guard)
    scripts = '<script src="/crm.js?v=agenda-20261026"></script><script src="/agenda-app.js?v=agenda-20261026"></script></body>'
    return HTMLResponse(page.replace("</body>", scripts), headers={"Cache-Control": "no-store"})


@app.get("/crm.js", include_in_schema=False)
def crm_script():
    return FileResponse(Path(__file__).parent / "web" / "crm.js", media_type="text/javascript", headers={"Cache-Control": "no-store"})


@app.get("/agenda-app.js", include_in_schema=False)
def agenda_script():
    return FileResponse(Path(__file__).parent / "web" / "agenda-app.js", media_type="text/javascript", headers={"Cache-Control": "no-store"})


app.include_router(customers_router)
app.include_router(sales_router)
app.include_router(nfse_router)
app.include_router(auth_router)
app.include_router(agenda_router)


@app.exception_handler(RequestValidationError)
async def private_validation_error_handler(request, exc: RequestValidationError):
    """Do not echo request values, which may contain fiscal or customer data."""
    return JSONResponse(
        status_code=422,
        content={
            "detail": [
                {"loc": error.get("loc"), "msg": error.get("msg"), "type": error.get("type")}
                for error in exc.errors()
            ]
        },
    )
