import base64
from dataclasses import dataclass
from datetime import datetime, timezone
import gzip
import json
import logging
from pathlib import Path
import re
import ssl
import tempfile
import uuid
import zlib

import httpx
from lxml import etree

from clinicaflow.fiscal.nfse.certificate import CertificateFiles, materialize_pfx
from clinicaflow.fiscal.nfse.config import NfseSettings
from clinicaflow.fiscal.nfse.dps import (
    ElementInput,
    NFS_E_NAMESPACE,
    build_dps_document,
    load_dps_schema,
    sign_dps,
)
from clinicaflow.fiscal.nfse.errors import (
    DpsValidationError,
    NfseApiError,
    NfseCertificateError,
    NfseTransportError,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class NfseIssueResult:
    access_key: str
    signed_xml_path: Path
    authorized_xml_path: Path
    authorized_xml: bytes


def configure_nfse_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def _write_private_artifact(directory: Path, name: str, content: bytes) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    final_path = directory / name
    with tempfile.NamedTemporaryFile(
        dir=directory, prefix=".nfse-", delete=False
    ) as stream:
        temp_path = Path(stream.name)
        stream.write(content)
    try:
        temp_path.chmod(0o600)
    except OSError:
        pass
    temp_path.replace(final_path)
    return final_path


def _decode_xml_response(response: httpx.Response) -> bytes:
    content_type = response.headers.get("content-type", "").lower()
    if "xml" in content_type or response.content.lstrip().startswith(b"<"):
        return response.content
    try:
        payload: Any = response.json()
    except (json.JSONDecodeError, ValueError) as exc:
        raise NfseApiError(
            "A SEFIN retornou uma resposta que não é JSON nem XML."
        ) from exc
    if not isinstance(payload, dict):
        raise NfseApiError("Formato inesperado na resposta da SEFIN.")
    encoded_xml = payload.get("nfseXmlGZipB64")
    if not isinstance(encoded_xml, str) or not encoded_xml:
        detail = (
            payload.get("mensagem")
            or payload.get("message")
            or payload.get("erros")
        )
        raise NfseApiError(
            f"A resposta de sucesso não contém nfseXmlGZipB64: {detail!s}"
        )
    try:
        compressed = base64.b64decode(encoded_xml, validate=True)
        return gzip.decompress(compressed)
    except (ValueError, OSError, EOFError, gzip.BadGzipFile, zlib.error) as exc:
        raise NfseApiError(
            "Falha ao decodificar a NFS-e gzip/base64 da SEFIN."
        ) from exc


def _extract_access_key(xml_bytes: bytes) -> str:
    try:
        root = etree.fromstring(
            xml_bytes, parser=etree.XMLParser(resolve_entities=False, no_network=True)
        )
    except etree.XMLSyntaxError as exc:
        raise NfseApiError(f"A SEFIN retornou XML inválido: {exc}") from exc
    inf_nfse = root.find(f".//{{{NFS_E_NAMESPACE}}}infNFSe")
    if inf_nfse is not None:
        identifier = inf_nfse.get("Id", "")
        if identifier.startswith("NFS"):
            return identifier[3:]
    access_key = root.findtext(f".//{{{NFS_E_NAMESPACE}}}chNFSe")
    if access_key:
        return access_key.strip()
    raise NfseApiError("Não encontrei a chave de acesso no XML autorizado da SEFIN.")


def _is_tls_failure(error: BaseException) -> bool:
    current: BaseException | None = error
    while current is not None:
        if isinstance(current, (ssl.SSLError, ssl.CertificateError)):
            return True
        current = current.__cause__ or current.__context__
    return "ssl" in str(error).lower() or "tls" in str(error).lower()


class NfseClient:
    """Cliente mTLS para emissão síncrona no Emissor Público Nacional."""

    def __init__(self, settings: NfseSettings) -> None:
        self.settings = settings

    def emitir(self, inf_dps: ElementInput) -> NfseIssueResult:
        try:
            schema = load_dps_schema(self.settings.dps_schema_path)
            document = build_dps_document(inf_dps, schema)
        except DpsValidationError as exc:
            logger.error("DPS rejeitada pelo XSD nacional: %s", exc)
            raise

        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        try:
            with materialize_pfx(
                self.settings.certificate_path, self.settings.certificate_password
            ) as certificate:
                try:
                    signed_xml = sign_dps(
                        document,
                        certificate.private_key_pem,
                        certificate.certificate_pem,
                        schema,
                    )
                except DpsValidationError as exc:
                    logger.error(
                        "Falha na assinatura ou validação XMLDSIG da DPS: %s", exc
                    )
                    raise
                signed_path = _write_private_artifact(
                    self.settings.output_directory,
                    f"DPS_{stamp}_assinada.xml",
                    signed_xml,
                )
                response_xml = self._post_dps(signed_xml, certificate)
        except NfseCertificateError as exc:
            logger.error("Falha ao carregar certificado PKCS#12: %s", exc)
            raise

        access_key = _extract_access_key(response_xml)
        safe_key = re.sub(r"[^0-9A-Za-z_-]", "_", access_key)
        if not safe_key:
            raise NfseApiError("A SEFIN retornou uma chave de acesso inválida.")
        keyed_path = self.settings.output_directory / f"NFSe_{safe_key}.xml"
        if keyed_path.exists():
            keyed_path = self.settings.output_directory / f"NFSe_{safe_key}_{uuid.uuid4().hex}.xml"
        authorized_path = _write_private_artifact(
            self.settings.output_directory, keyed_path.name, response_xml
        )
        logger.info("NFS-e autorizada. Chave de acesso: %s", access_key)
        return NfseIssueResult(access_key, signed_path, authorized_path, response_xml)

    def _post_dps(self, signed_xml: bytes, certificate: CertificateFiles) -> bytes:
        body = {
            "dpsXmlGZipB64": base64.b64encode(
                gzip.compress(signed_xml, mtime=0)
            ).decode("ascii")
        }
        try:
            with httpx.Client(
                cert=(
                    str(certificate.certificate_path),
                    str(certificate.private_key_path),
                ),
                verify=True,
                timeout=self.settings.timeout_seconds,
                follow_redirects=False,
            ) as client:
                response = client.post(
                    f"{self.settings.base_url}/nfse",
                    json=body,
                    headers={"Accept": "application/json"},
                )
        except httpx.TimeoutException as exc:
            logger.error("Tempo esgotado ao conectar à SEFIN Nacional.")
            raise NfseTransportError(
                "Tempo esgotado na comunicação com a SEFIN."
            ) from exc
        except httpx.RequestError as exc:
            if _is_tls_failure(exc):
                logger.error("Falha no handshake TLS/mTLS com a SEFIN Nacional.")
                raise NfseTransportError(
                    "Falha no handshake TLS. Confira validade, cadeia "
                    "e uso do certificado A1."
                ) from exc
            logger.error("Falha de conexão com a SEFIN Nacional: %s", exc)
            raise NfseTransportError(
                "Não foi possível conectar à SEFIN Nacional."
            ) from exc

        if response.status_code not in (200, 201):
            detail = response.text[:2000]
            logger.error(
                "Rejeição da SEFIN (HTTP %s): %s", response.status_code, detail
            )
            raise NfseApiError(
                f"A SEFIN rejeitou a DPS (HTTP {response.status_code}): {detail}"
            )
        try:
            return _decode_xml_response(response)
        except NfseApiError:
            logger.exception("Resposta de sucesso da SEFIN sem NFS-e válida.")
            raise
