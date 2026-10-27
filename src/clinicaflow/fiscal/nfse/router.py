import os
from ipaddress import ip_address
from pathlib import Path
import secrets
from datetime import date
from typing import Annotated, Literal

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from clinicaflow.core.database import get_db
from clinicaflow.core.security import require_admin
from clinicaflow.customers.models import Customer
from clinicaflow.fiscal.nfse.config import API_BASE_URLS, NfseSettings, PROJECT_ROOT
from clinicaflow.fiscal.nfse.builder import DpsIssueData, ServiceKey, build_inf_dps
from clinicaflow.fiscal.nfse.client import NfseClient
from clinicaflow.fiscal.nfse.dps import build_dps_document, load_dps_schema
from clinicaflow.fiscal.nfse.errors import (
    DpsValidationError,
    NfseApiError,
    NfseCertificateError,
    NfseConfigurationError,
    NfseTransportError,
)
from clinicaflow.sales.models import Sale

router = APIRouter(prefix="/nfse", tags=["NFS-e"], dependencies=[Depends(require_admin)])
DbSession = Annotated[Session, Depends(get_db)]


class NfseEmissionRequest(BaseModel):
    service_key: ServiceKey
    competence_date: date
    service_municipality_code: str = Field(pattern=r"^[0-9]{7}$")
    fiscal_description: str = Field(min_length=3, max_length=2000)
    iss_taxation: Literal["1", "2", "3", "4"]
    iss_withholding: Literal["1", "2", "3"]
    municipal_tax_code: str | None = Field(default=None, pattern=r"^[0-9]{3}$")

    model_config = ConfigDict(extra="forbid")


class NfseEmissionResponse(BaseModel):
    status: Literal["authorized"]
    access_key: str

SERVICE_CODE_SETTINGS = {
    "codigo_psicologia": "NFSE_SERVICE_CODE_PSYCHOLOGY",
    "codigo_psicotecnico_detran": "NFSE_SERVICE_CODE_PSYCHOTECHNIC_DETRAN",
    "codigo_psicotecnico_pf": "NFSE_SERVICE_CODE_PSYCHOTECHNIC_PF",
    "codigo_toxicologico_analise": "NFSE_SERVICE_CODE_TOXICOLOGICAL_ANALYSIS",
    "codigo_toxicologico_coleta": "NFSE_SERVICE_CODE_TOXICOLOGICAL_COLLECTION",
    "codigo_psiquiatria": "NFSE_SERVICE_CODE_PSYCHIATRY",
    "codigo_pericia_laudo": "NFSE_SERVICE_CODE_FORENSIC_REPORT",
}


@router.get("/readiness")
def nfse_readiness() -> dict[str, object]:
    """Indica dados de configuração pendentes; não habilita transmissão."""
    load_dotenv(PROJECT_ROOT / ".env")
    environment = os.getenv("NFSE_ENV", "restricted").strip().lower()
    certificate = Path(os.getenv("NFSE_PFX_PATH", "")).expanduser()
    schema = Path(os.getenv(
        "NFSE_DPS_SCHEMA_PATH",
        str(PROJECT_ROOT / "schemas/nfse/producao-restrita/DPS_v1.01.xsd"),
    )).expanduser()
    configured_base = os.getenv("NFSE_BASE_URL", API_BASE_URLS.get(environment, "")).rstrip("/")
    dps_series = os.getenv("NFSE_DPS_SERIES", "").strip()
    emission_token = os.getenv("NFSE_EMISSION_TOKEN", "")
    checks = {
        "ambiente_nfse": environment == "restricted" and configured_base == API_BASE_URLS["restricted"],
        "certificado_a1": certificate.is_file() and bool(os.getenv("NFSE_PFX_PASSWORD")),
        "esquema_dps": schema.is_file(),
        "cnpj_prestador": bool(os.getenv("NFSE_PROVIDER_CNPJ", "").strip()),
        "nome_legal_prestador": bool(os.getenv("NFSE_PROVIDER_LEGAL_NAME", "").strip()),
        "endereco_prestador": all(os.getenv(key, "").strip() for key in (
            "NFSE_PROVIDER_STREET", "NFSE_PROVIDER_NUMBER", "NFSE_PROVIDER_DISTRICT",
            "NFSE_PROVIDER_POSTAL_CODE", "NFSE_PROVIDER_CITY", "NFSE_PROVIDER_STATE",
            "NFSE_PROVIDER_MUNICIPALITY_CODE",
        )),
        "simples_nacional": os.getenv("NFSE_PROVIDER_SIMPLE_NATIONAL", "").strip() in {"1", "2", "3"},
        "regime_especial": os.getenv("NFSE_PROVIDER_SPECIAL_TAX_REGIME", "").strip() in {"0", "1", "2", "3", "4", "5", "6", "9"},
        "serie_dps": dps_series.isdigit() and 1 <= len(dps_series) <= 5 and (len(dps_series) < 5 or dps_series[0] <= "8"),
        "token_emissao": len(emission_token) >= 32,
        "inscricao_municipal": bool(os.getenv("NFSE_PROVIDER_MUNICIPAL_REGISTRATION", "").strip()),
        **{
            name: len(os.getenv(env_name, "").strip()) == 6 and os.getenv(env_name, "").strip().isdigit()
            for name, env_name in SERVICE_CODE_SETTINGS.items()
        },
    }
    required = {name: ready for name, ready in checks.items() if name != "inscricao_municipal"}
    missing = [name for name, ready in required.items() if not ready]
    return {
        "configuration_ready": not missing,
        "emission_ready": not missing,
        "checks": checks,
        "optional_missing": ["inscricao_municipal"] if not checks["inscricao_municipal"] else [],
        "missing": missing,
        "message": (
            "Emissao em Producao Restrita pronta; cada DPS sera validada antes do envio."
            if not missing
            else "Complete os dados fiscais, codigos nacionais, serie DPS e token local."
        ),
    }


@router.post(
    "/sales/{sale_id}/emit",
    response_model=NfseEmissionResponse,
    status_code=status.HTTP_201_CREATED,
)
def emit_sale_nfse(
    sale_id: int,
    data: NfseEmissionRequest,
    request: Request,
    db: DbSession,
    emission_token: Annotated[str | None, Header(alias="X-NFSE-Emission-Token")] = None,
) -> NfseEmissionResponse:
    """Validate, sign and submit one sale's DPS; never returns XML or customer data."""
    peer = request.client.host if request.client else ""
    try:
        is_local_request = ip_address(peer).is_loopback
    except ValueError:
        is_local_request = False
    if not is_local_request:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="A emissao esta limitada ao computador local.",
        )

    load_dotenv(PROJECT_ROOT / ".env")
    configured_token = os.getenv("NFSE_EMISSION_TOKEN", "")
    if len(configured_token) < 32 or not emission_token or not secrets.compare_digest(
        configured_token, emission_token
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Acesso não autorizado.")

    sale = db.get(Sale, sale_id)
    if sale is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Venda não encontrada.")
    if sale.status == "cancelled":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Venda cancelada não pode ser emitida.")
    customer = db.get(Customer, sale.customer_id)
    if customer is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Tomador da venda não encontrado.")

    reservation: Path | None = None
    try:
        settings = NfseSettings.from_env()
        if settings.environment != "restricted" or settings.base_url != API_BASE_URLS["restricted"]:
            raise NfseConfigurationError(
                "A rota de emissão aceita somente o endpoint de Produção Restrita."
            )
        if not settings.dps_schema_path.is_file():
            raise NfseConfigurationError("O XSD da DPS não está disponível.")

        inf_dps = build_inf_dps(
            sale,
            customer,
            DpsIssueData(
                service_key=data.service_key,
                service_description=data.fiscal_description,
                service_municipality_code=data.service_municipality_code,
                iss_taxation=data.iss_taxation,
                iss_withholding=data.iss_withholding,
                municipal_tax_code=data.municipal_tax_code,
                competence_date=data.competence_date,
            ),
        )
        schema = load_dps_schema(settings.dps_schema_path)
        build_dps_document(inf_dps, schema)

        series = os.getenv("NFSE_DPS_SERIES", "").strip()
        reservation = settings.output_directory / f".dps-{series}-{sale.id}.reserved"
        settings.output_directory.mkdir(parents=True, exist_ok=True)
        try:
            with reservation.open("x", encoding="ascii") as stream:
                stream.write("submission started")
        except FileExistsError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Esta venda já tem uma tentativa de emissão registrada. "
                    "Confira a situação na SEFIN antes de tentar novamente."
                ),
            ) from exc

        result = NfseClient(settings).emitir(inf_dps)
        return NfseEmissionResponse(status="authorized", access_key=result.access_key)
    except HTTPException:
        raise
    except DpsValidationError as exc:
        if reservation is not None:
            reservation.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A DPS não passou no XSD. Revise códigos, tributação e dados da prestação.",
        ) from exc
    except NfseCertificateError as exc:
        if reservation is not None:
            reservation.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Não foi possível carregar o certificado. Confira o arquivo e a senha.",
        ) from exc
    except NfseConfigurationError as exc:
        if reservation is not None:
            reservation.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="A configuração fiscal de homologação está incompleta ou inválida.",
        ) from exc
    except NfseTransportError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Falha de comunicação com a SEFIN em Produção Restrita.",
        ) from exc
    except NfseApiError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="A SEFIN rejeitou ou não confirmou a DPS. Consulte a SEFIN antes de reenviar.",
        ) from exc
