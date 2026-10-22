from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
import tempfile
from typing import Iterator

from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.types import PrivateKeyTypes
from cryptography.hazmat.primitives.serialization import pkcs12

from clinicaflow.fiscal.nfse.errors import NfseCertificateError


@dataclass(frozen=True, slots=True)
class CertificateFiles:
    certificate_path: Path
    private_key_path: Path
    private_key_pem: bytes
    certificate_pem: bytes


def _load_pfx(
    pfx_path: Path, password: str
) -> tuple[PrivateKeyTypes, x509.Certificate, tuple[x509.Certificate, ...]]:
    try:
        private_key, certificate, additional_certificates = (
            pkcs12.load_key_and_certificates(
                pfx_path.read_bytes(), password.encode("utf-8")
            )
        )
    except (OSError, ValueError, TypeError) as exc:
        raise NfseCertificateError(
            "Não foi possível abrir o .pfx. Confira o arquivo e a senha."
        ) from exc
    if private_key is None or certificate is None:
        raise NfseCertificateError(
            "O .pfx precisa conter uma chave privada e um certificado X.509."
        )
    return private_key, certificate, additional_certificates or ()


@contextmanager
def materialize_pfx(pfx_path: Path, password: str) -> Iterator[CertificateFiles]:
    """Abre PKCS#12 em memória e cria PEMs temporários para o cliente TLS."""
    private_key, certificate, chain = _load_pfx(pfx_path, password)
    private_key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    certificate_pem = certificate.public_bytes(serialization.Encoding.PEM)
    client_chain_pem = certificate_pem + b"".join(
        item.public_bytes(serialization.Encoding.PEM) for item in chain
    )
    with tempfile.TemporaryDirectory(prefix="clinicaflow-nfse-") as temp_dir:
        directory = Path(temp_dir)
        key_path = directory / "client-key.pem"
        certificate_path = directory / "client-chain.pem"
        key_path.write_bytes(private_key_pem)
        certificate_path.write_bytes(client_chain_pem)
        try:
            key_path.chmod(0o600)
            certificate_path.chmod(0o600)
        except OSError:
            # No Windows, o diretório temporário herda a ACL do usuário atual.
            pass
        yield CertificateFiles(
            certificate_path=certificate_path,
            private_key_path=key_path,
            private_key_pem=private_key_pem,
            certificate_pem=certificate_pem,
        )
