"""Build a privacy-conscious DPS draft from a sale and confirmed fiscal inputs."""

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import os
import re
from typing import Literal, Mapping

from clinicaflow.customers.models import Customer
from clinicaflow.fiscal.nfse.dps import DpsElement
from clinicaflow.fiscal.nfse.errors import DpsValidationError
from clinicaflow.sales.models import Sale


ServiceKey = Literal[
    "psychology",
    "psychotechnic_detran",
    "psychotechnic_pf",
    "toxicological_analysis",
    "toxicological_collection",
    "psychiatry",
    "forensic_report",
]

SERVICE_ENV_KEYS: dict[ServiceKey, str] = {
    "psychology": "NFSE_SERVICE_CODE_PSYCHOLOGY",
    "psychotechnic_detran": "NFSE_SERVICE_CODE_PSYCHOTECHNIC_DETRAN",
    "psychotechnic_pf": "NFSE_SERVICE_CODE_PSYCHOTECHNIC_PF",
    "toxicological_analysis": "NFSE_SERVICE_CODE_TOXICOLOGICAL_ANALYSIS",
    "toxicological_collection": "NFSE_SERVICE_CODE_TOXICOLOGICAL_COLLECTION",
    "psychiatry": "NFSE_SERVICE_CODE_PSYCHIATRY",
    "forensic_report": "NFSE_SERVICE_CODE_FORENSIC_REPORT",
}

SERVICE_MUNICIPAL_ENV_KEYS: dict[ServiceKey, str] = {
    key: env_key.replace("NFSE_SERVICE_CODE_", "NFSE_SERVICE_MUNICIPAL_CODE_")
    for key, env_key in SERVICE_ENV_KEYS.items()
}


@dataclass(frozen=True, slots=True)
class DpsIssueData:
    service_key: ServiceKey
    service_description: str
    service_municipality_code: str
    iss_taxation: Literal["1", "2", "3", "4"]
    iss_withholding: Literal["1", "2", "3"]
    municipal_tax_code: str | None = None
    competence_date: date | None = None
    issued_at: datetime | None = None


def _required(env: Mapping[str, str], key: str) -> str:
    value = env.get(key, "").strip()
    if not value:
        raise DpsValidationError(f"Configuração fiscal ausente: {key}.")
    return value


def _digits(value: str, expected_length: int, label: str) -> str:
    result = re.sub(r"\D", "", value)
    if len(result) != expected_length:
        raise DpsValidationError(f"{label} deve ter {expected_length} dígitos.")
    return result


def _node(
    name: str,
    text: str | None = None,
    *children: DpsElement,
    attributes: Mapping[str, str] | None = None,
) -> DpsElement:
    return DpsElement(
        name=name,
        text=text,
        attributes=attributes or {},
        children=tuple(children),
    )


def build_inf_dps(
    sale: Sale,
    customer: Customer,
    data: DpsIssueData,
    env: Mapping[str, str] | None = None,
) -> DpsElement:
    """Create an unsigned infDPS. The caller must validate it against the official XSD."""
    env = os.environ if env is None else env
    cnpj = _digits(_required(env, "NFSE_PROVIDER_CNPJ"), 14, "CNPJ do prestador")
    provider_city = _digits(
        _required(env, "NFSE_PROVIDER_MUNICIPALITY_CODE"), 7, "Município do prestador"
    )
    dps_series = _required(env, "NFSE_DPS_SERIES")
    if not re.fullmatch(r"(?:[0-9]{1,4}|[0-8][0-9]{4})", dps_series):
        raise DpsValidationError("NFSE_DPS_SERIES não atende ao formato do XSD.")
    dps_number = str(sale.id)
    if not dps_number.isdigit() or int(dps_number) <= 0 or len(dps_number) > 15:
        raise DpsValidationError("A venda precisa ter um identificador positivo válido.")

    national_code = _required(env, SERVICE_ENV_KEYS[data.service_key])
    if not re.fullmatch(r"[0-9]{6}", national_code):
        raise DpsValidationError(
            "O código cTribNac do serviço deve ter seis dígitos numéricos; "
            "confira a tabela nacional antes de emitir."
        )
    municipal_code = data.municipal_tax_code or env.get(
        SERVICE_MUNICIPAL_ENV_KEYS[data.service_key], ""
    ).strip()
    if municipal_code and not re.fullmatch(r"[0-9]{3}", municipal_code):
        raise DpsValidationError("O código cTribMun deve ter três dígitos numéricos.")
    if not re.fullmatch(r"[0-9]{7}", data.service_municipality_code):
        raise DpsValidationError(
            "O município da prestação deve ser o código IBGE de sete dígitos."
        )
    description = data.service_description.strip()
    if not description or len(description) > 2000:
        raise DpsValidationError("Informe uma descrição fiscal de até 2.000 caracteres.")

    try:
        amount = Decimal(str(sale.amount)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    except (InvalidOperation, ValueError) as exc:
        raise DpsValidationError("O valor da venda não é válido.") from exc
    if amount <= 0:
        raise DpsValidationError("O valor do serviço deve ser maior que zero.")

    simple_national = _required(env, "NFSE_PROVIDER_SIMPLE_NATIONAL")
    if simple_national not in {"1", "2", "3"}:
        raise DpsValidationError("NFSE_PROVIDER_SIMPLE_NATIONAL deve ser 1, 2 ou 3.")
    special_regime = _required(env, "NFSE_PROVIDER_SPECIAL_TAX_REGIME")
    if special_regime not in {"0", "1", "2", "3", "4", "5", "6", "9"}:
        raise DpsValidationError("Regime especial do prestador inválido.")
    simple_tax_regime = env.get("NFSE_PROVIDER_SIMPLE_TAX_REGIME", "").strip()
    if simple_tax_regime and (
        simple_national != "3" or simple_tax_regime not in {"1", "2", "3"}
    ):
        raise DpsValidationError(
            "Regime de apuração do Simples inválido para este enquadramento."
        )

    provider_name = _required(env, "NFSE_PROVIDER_LEGAL_NAME")
    street = _required(env, "NFSE_PROVIDER_STREET")
    number = _required(env, "NFSE_PROVIDER_NUMBER")
    district = _required(env, "NFSE_PROVIDER_DISTRICT")
    postal_code = _digits(
        _required(env, "NFSE_PROVIDER_POSTAL_CODE"), 8, "CEP do prestador"
    )
    competence = data.competence_date or sale.sale_date
    issued_at = data.issued_at or datetime.now(timezone.utc)
    if issued_at.tzinfo is None or issued_at.utcoffset() is None:
        raise DpsValidationError("A data e hora de emissão precisa ter fuso horário.")

    series_in_id = dps_series.zfill(5)
    number_in_id = dps_number.zfill(15)
    dps_id = f"DPS{provider_city}1{cnpj}{series_in_id}{number_in_id}"
    service_children = [_node("cTribNac", national_code)]
    if municipal_code:
        service_children.append(_node("cTribMun", municipal_code))
    service_children.append(_node("xDescServ", description))

    provider_children = [
        _node("CNPJ", cnpj),
    ]
    registration = env.get("NFSE_PROVIDER_MUNICIPAL_REGISTRATION", "").strip()
    if registration:
        provider_children.append(_node("IM", registration))
    provider_children.extend([
        _node("xNome", provider_name),
        _node(
            "end",
            None,
            _node(
                "endNac",
                None,
                _node("cMun", provider_city),
                _node("CEP", postal_code),
            ),
            _node("xLgr", street),
            _node("nro", number),
            *(
                (_node("xCpl", env["NFSE_PROVIDER_COMPLEMENT"].strip()),)
                if env.get("NFSE_PROVIDER_COMPLEMENT", "").strip()
                else ()
            ),
            _node("xBairro", district),
        ),
        _node(
            "regTrib",
            None,
            _node("opSimpNac", simple_national),
                *(
                    (_node("regApTribSN", simple_tax_regime),)
                if simple_tax_regime
                else ()
            ),
            _node("regEspTrib", special_regime),
        ),
    ])

    person_children: list[DpsElement] = []
    document = re.sub(r"\D", "", customer.document or "")
    if document:
        if len(document) == 11:
            person_children.append(_node("CPF", document))
        elif len(document) == 14:
            person_children.append(_node("CNPJ", document))
        else:
            raise DpsValidationError("O documento do tomador deve ser CPF ou CNPJ.")
        person_children.append(_node("xNome", customer.name))

    issue_time = issued_at.astimezone(timezone.utc).isoformat(timespec="seconds")
    amount_text = format(amount, ".2f")
    children = [
        _node("tpAmb", "2" if env.get("NFSE_ENV", "restricted").lower() == "restricted" else "1"),
        _node("dhEmi", issue_time),
        _node("verAplic", "Clinicaflow-0.1.0"),
        _node("serie", dps_series),
        _node("nDPS", dps_number),
        _node("dCompet", competence.isoformat()),
        _node("tpEmit", "1"),
        _node("finNFSe", "0"),
        _node("cLocEmi", provider_city),
        _node("prest", None, *provider_children),
    ]
    if person_children:
        children.append(_node("toma", None, *person_children))
    children.extend([
        _node(
            "serv",
            None,
            _node("locPrest", None, _node("cLocPrestacao", data.service_municipality_code)),
            _node("cServ", None, *service_children),
        ),
        _node(
            "valores",
            None,
            _node("vServPrest", None, _node("vServ", amount_text)),
            _node(
                "trib",
                None,
                _node(
                    "tribMun",
                    None,
                    _node("tribISSQN", data.iss_taxation),
                    _node("tpRetISSQN", data.iss_withholding),
                ),
                _node("totTrib", None, _node("indTotTrib", "0")),
            ),
        ),
    ])
    return _node("infDPS", None, *children, attributes={"Id": dps_id})
