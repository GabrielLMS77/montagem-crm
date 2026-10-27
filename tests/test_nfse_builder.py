from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from clinicaflow.customers.models import Customer
from clinicaflow.fiscal.nfse.builder import DpsIssueData, build_inf_dps
from clinicaflow.fiscal.nfse.dps import NFS_E_NAMESPACE, build_dps_document, load_dps_schema
from clinicaflow.fiscal.nfse.errors import DpsValidationError
from clinicaflow.sales.models import Sale


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = PROJECT_ROOT / "schemas/nfse/producao-restrita/DPS_v1.01.xsd"


def _fixture_env() -> dict[str, str]:
    return {
        "NFSE_ENV": "restricted",
        "NFSE_PROVIDER_CNPJ": "00000000000000",
        "NFSE_PROVIDER_LEGAL_NAME": "Clinica de Teste",
        "NFSE_PROVIDER_MUNICIPAL_REGISTRATION": "",
        "NFSE_PROVIDER_STREET": "Rua de Teste",
        "NFSE_PROVIDER_NUMBER": "10",
        "NFSE_PROVIDER_COMPLEMENT": "",
        "NFSE_PROVIDER_DISTRICT": "Centro",
        "NFSE_PROVIDER_POSTAL_CODE": "01001000",
        "NFSE_PROVIDER_MUNICIPALITY_CODE": "1234567",
        "NFSE_PROVIDER_SIMPLE_NATIONAL": "3",
        "NFSE_PROVIDER_SIMPLE_TAX_REGIME": "",
        "NFSE_PROVIDER_SPECIAL_TAX_REGIME": "0",
        "NFSE_DPS_SERIES": "900",
        "NFSE_SERVICE_CODE_PSYCHIATRY": "040101",
    }


def _fixture_sale() -> tuple[Sale, Customer]:
    sale = Sale(
        id=21,
        customer_id=7,
        description="Descricao interna nao usada no XML",
        amount=Decimal("250.00"),
        sale_date=date(2026, 10, 26),
        status="paid",
    )
    customer = Customer(id=7, name="Pessoa de Teste", document=None)
    return sale, customer


def test_builds_unsigned_dps_and_validates_against_local_xsd() -> None:
    sale, customer = _fixture_sale()
    inf_dps = build_inf_dps(
        sale,
        customer,
        DpsIssueData(
            service_key="psychiatry",
            service_description="Consulta médica de teste",
            service_municipality_code="1234567",
            iss_taxation="1",
            iss_withholding="1",
        ),
        env=_fixture_env(),
    )

    document = build_dps_document(inf_dps, load_dps_schema(SCHEMA_PATH))
    info = document.getroot().find(f"{{{NFS_E_NAMESPACE}}}infDPS")

    assert info is not None
    assert info.get("Id", "").startswith("DPS12345671")
    assert len(info.get("Id", "")) == 45
    assert info.findtext(f"{{{NFS_E_NAMESPACE}}}tpAmb") == "2"
    assert info.findtext(f".//{{{NFS_E_NAMESPACE}}}cTribNac") == "040101"
    assert info.findtext(f".//{{{NFS_E_NAMESPACE}}}vServ") == "250.00"


def test_rejects_service_code_outside_national_six_digit_format() -> None:
    sale, customer = _fixture_sale()
    env = _fixture_env()
    env["NFSE_SERVICE_CODE_PSYCHIATRY"] = "04030"

    with pytest.raises(DpsValidationError, match="seis dígitos"):
        build_inf_dps(
            sale,
            customer,
            DpsIssueData(
                service_key="psychiatry",
                service_description="Consulta médica de teste",
                service_municipality_code="1234567",
                iss_taxation="1",
                iss_withholding="1",
            ),
            env=env,
        )
