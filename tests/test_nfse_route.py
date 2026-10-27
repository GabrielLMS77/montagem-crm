import asyncio
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError
from starlette.requests import Request

from clinicaflow.customers.models import Customer
from clinicaflow.fiscal.nfse import router as nfse_router_module
from clinicaflow.fiscal.nfse.router import NfseEmissionRequest, emit_sale_nfse
from clinicaflow.main import private_validation_error_handler
from clinicaflow.sales.models import Sale


def _loopback_request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/nfse/sales/21/emit",
            "headers": [],
            "client": ("127.0.0.1", 50000),
        }
    )


@pytest.fixture
def private_emission_config(monkeypatch, tmp_path: Path) -> None:
    fake_certificate = tmp_path / "synthetic.pfx"
    fake_certificate.write_bytes(b"synthetic-only")
    values = {
        "NFSE_ENV": "restricted",
        "NFSE_BASE_URL": "https://sefin.producaorestrita.nfse.gov.br/SefinNacional",
        "NFSE_PFX_PATH": str(fake_certificate),
        "NFSE_PFX_PASSWORD": "synthetic-test-password",
        "NFSE_DPS_SCHEMA_PATH": str(
            Path(__file__).resolve().parents[1]
            / "schemas/nfse/producao-restrita/DPS_v1.01.xsd"
        ),
        "NFSE_OUTPUT_DIR": str(tmp_path / "private-output"),
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
        "NFSE_EMISSION_TOKEN": "synthetic-token-" + ("x" * 40),
        "NFSE_SERVICE_CODE_PSYCHIATRY": "040101",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)


def test_emission_route_uses_mock_client_and_returns_no_xml(
    private_emission_config, monkeypatch
) -> None:
    sale = Sale(
        id=21,
        customer_id=7,
        description="Internal sale text is not used in fiscal description",
        amount=Decimal("250.00"),
        sale_date=date(2026, 10, 26),
        status="paid",
    )
    customer = Customer(id=7, name="Pessoa de Teste", document=None)

    class FakeSession:
        def get(self, model, record_id):
            if model is Sale:
                return sale if record_id == 21 else None
            if model is Customer:
                return customer if record_id == 7 else None
            return None

    calls = []

    class FakeNfseClient:
        def __init__(self, settings):
            self.settings = settings

        def emitir(self, inf_dps):
            calls.append(inf_dps)
            return SimpleNamespace(access_key="synthetic-access-key")

    monkeypatch.setattr(nfse_router_module, "NfseClient", FakeNfseClient)
    body = NfseEmissionRequest(
        service_key="psychiatry",
        competence_date=date(2026, 10, 26),
        service_municipality_code="1234567",
        fiscal_description="Consulta medica de teste",
        iss_taxation="1",
        iss_withholding="1",
    )

    response = emit_sale_nfse(
        21,
        body,
        _loopback_request(),
        FakeSession(),
        "synthetic-token-" + ("x" * 40),
    )

    assert response.status == "authorized"
    assert response.access_key == "synthetic-access-key"
    assert len(calls) == 1
    assert not hasattr(response, "authorized_xml")


def test_emission_route_rejects_missing_or_wrong_token(
    private_emission_config,
) -> None:
    with pytest.raises(HTTPException) as error:
        emit_sale_nfse(
            21,
            NfseEmissionRequest(
                service_key="psychiatry",
                competence_date=date(2026, 10, 26),
                service_municipality_code="1234567",
                fiscal_description="Consulta medica de teste",
                iss_taxation="1",
                iss_withholding="1",
            ),
            _loopback_request(),
            object(),
            "wrong-token",
        )

    assert error.value.status_code == 401


def test_request_validation_response_does_not_echo_sensitive_input() -> None:
    request = Request(
        {"type": "http", "method": "POST", "path": "/nfse", "headers": []}
    )
    error = RequestValidationError(
        [
            {
                "loc": ("body", "fiscal_description"),
                "msg": "String should match pattern",
                "type": "string_pattern_mismatch",
                "input": "sensitive patient detail",
            }
        ]
    )

    response = asyncio.run(private_validation_error_handler(request, error))

    assert b"sensitive patient detail" not in response.body
    assert b"fiscal_description" in response.body
