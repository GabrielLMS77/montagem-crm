import os
from pathlib import Path

from fastapi import APIRouter
from dotenv import load_dotenv

from clinicaflow.fiscal.nfse.config import API_BASE_URLS, PROJECT_ROOT

router = APIRouter(prefix="/nfse", tags=["NFS-e"])


@router.get("/readiness")
def nfse_readiness() -> dict[str, object]:
    """Indica o que falta configurar antes de habilitar a emissão fiscal."""
    load_dotenv(PROJECT_ROOT / ".env")
    environment = os.getenv("NFSE_ENV", "restricted").strip().lower()
    certificate = Path(os.getenv("NFSE_PFX_PATH", "")).expanduser()
    schema = Path(os.getenv(
        "NFSE_DPS_SCHEMA_PATH",
        str(PROJECT_ROOT / "schemas/nfse/producao-restrita/DPS_v1.01.xsd"),
    )).expanduser()
    checks = {
        "ambiente_nfse": environment in API_BASE_URLS,
        "certificado_a1": certificate.is_file() and bool(os.getenv("NFSE_PFX_PASSWORD")),
        "esquema_dps": schema.is_file(),
        "cnpj_prestador": bool(os.getenv("NFSE_PROVIDER_CNPJ", "").strip()),
        "inscricao_municipal": bool(os.getenv("NFSE_PROVIDER_MUNICIPAL_REGISTRATION", "").strip()),
        "codigo_municipio": bool(os.getenv("NFSE_PROVIDER_MUNICIPALITY_CODE", "").strip()),
        "regime_tributario": bool(os.getenv("NFSE_PROVIDER_TAX_REGIME", "").strip()),
        "codigo_servico": bool(os.getenv("NFSE_SERVICE_CODE", "").strip()),
    }
    required = {name: ready for name, ready in checks.items() if name != "inscricao_municipal"}
    missing = [name for name, ready in required.items() if not ready]
    return {
        "configuration_ready": not missing,
        "emission_ready": False,
        "checks": checks,
        "optional_missing": [name for name, ready in checks.items() if name == "inscricao_municipal" and not ready],
        "missing": missing,
        "message": (
            "Configuração fiscal básica pronta; a montagem da DPS a partir da venda ainda precisa ser concluída."
            if not missing
            else "Complete os dados fiscais e o certificado antes de emitir."
        ),
    }
