from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, TypeAlias

from lxml import etree
from signxml import XMLSigner, methods

from clinicaflow.fiscal.nfse.errors import DpsValidationError

NFS_E_NAMESPACE = "http://www.sped.fazenda.gov.br/nfse"
DSIG_NAMESPACE = "http://www.w3.org/2000/09/xmldsig#"


@dataclass(frozen=True, slots=True)
class DpsElement:
    """Nó XML tipado; a ordem de children precisa seguir o XSD nacional."""

    name: str
    text: str | None = None
    attributes: Mapping[str, str] = field(default_factory=dict)
    children: tuple["DpsElement", ...] = ()


ElementInput: TypeAlias = DpsElement | etree._Element | bytes | str


def _to_lxml(element: DpsElement) -> etree._Element:
    if ":" in element.name:
        raise DpsValidationError(
            "Use nomes locais sem prefixo; a DPS usa namespace padrão."
        )
    node = etree.Element(f"{{{NFS_E_NAMESPACE}}}{element.name}")
    for name, value in element.attributes.items():
        node.set(name, value)
    node.text = element.text
    for child in element.children:
        node.append(_to_lxml(child))
    return node


def secure_xml_parser() -> etree.XMLParser:
    return etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        remove_comments=True,
    )


def load_dps_schema(schema_path: Path) -> etree.XMLSchema:
    try:
        schema_document = etree.parse(str(schema_path), parser=secure_xml_parser())
        return etree.XMLSchema(schema_document)
    except (OSError, etree.XMLSyntaxError, etree.XMLSchemaParseError) as exc:
        raise DpsValidationError(
            f"Não foi possível carregar o XSD da DPS: {exc}"
        ) from exc


def _as_element(value: ElementInput) -> etree._Element:
    if isinstance(value, DpsElement):
        return _to_lxml(value)
    if isinstance(value, etree._Element):
        return value
    try:
        xml = value.encode("utf-8") if isinstance(value, str) else value
        return etree.fromstring(xml, parser=secure_xml_parser())
    except etree.XMLSyntaxError as exc:
        raise DpsValidationError(f"XML de entrada inválido: {exc}") from exc


def validate_dps(document: etree._ElementTree, schema: etree.XMLSchema) -> None:
    try:
        schema.assertValid(document)
    except etree.DocumentInvalid as exc:
        errors = "; ".join(str(item) for item in schema.error_log)
        raise DpsValidationError(f"A DPS não passou no XSD oficial: {errors}") from exc


def build_dps_document(
    inf_dps: ElementInput, schema: etree.XMLSchema, version: str = "1.01"
) -> etree._ElementTree:
    """Envolve infDPS no envelope nacional e valida a estrutura completa."""
    info = _as_element(inf_dps)
    if info.tag != f"{{{NFS_E_NAMESPACE}}}infDPS":
        raise DpsValidationError(
            f"O elemento informado deve ser infDPS no namespace {NFS_E_NAMESPACE}."
        )
    root = etree.Element(
        f"{{{NFS_E_NAMESPACE}}}DPS", nsmap={None: NFS_E_NAMESPACE}, versao=version
    )
    root.append(deepcopy(info))
    document = etree.ElementTree(root)
    validate_dps(document, schema)
    return document


def sign_dps(
    document: etree._ElementTree,
    private_key_pem: bytes,
    certificate_pem: bytes,
    schema: etree.XMLSchema,
) -> bytes:
    """Assina a referência a infDPS e posiciona Signature no nível de DPS."""
    root = document.getroot()
    inf_dps = root.find(f"{{{NFS_E_NAMESPACE}}}infDPS")
    if inf_dps is None or not inf_dps.get("Id"):
        raise DpsValidationError("O infDPS precisa ter o atributo Id para assinatura.")
    dps_id = inf_dps.get("Id")
    matching_ids = root.xpath(".//*[@Id=$value]", value=dps_id)
    if len(matching_ids) != 1:
        raise DpsValidationError("O Id da DPS deve ser único no documento.")
    try:
        signer = XMLSigner(
            method=methods.enveloped,
            signature_algorithm="rsa-sha256",
            digest_algorithm="sha256",
            c14n_algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315",
        )
        signer.namespaces = {None: DSIG_NAMESPACE}
        signed_root = signer.sign(
            root,
            key=private_key_pem,
            cert=certificate_pem.decode("ascii"),
            reference_uri=f"#{dps_id}",
            id_attribute="Id",
            always_add_key_value=False,
        )
    except Exception as exc:
        raise DpsValidationError(f"Falha ao assinar a DPS com XMLDSIG: {exc}") from exc
    signed_document = etree.ElementTree(signed_root)
    validate_dps(signed_document, schema)
    return etree.tostring(
        signed_document, encoding="UTF-8", xml_declaration=True, pretty_print=False
    )
