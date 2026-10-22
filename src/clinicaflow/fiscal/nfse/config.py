from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv

from clinicaflow.fiscal.nfse.errors import NfseConfigurationError

PROJECT_ROOT = Path(__file__).resolve().parents[4]
API_BASE_URLS = {
    "restricted": "https://sefin.producaorestrita.nfse.gov.br/SefinNacional",
    "production": "https://sefin.nfse.gov.br/SefinNacional",
}


@dataclass(frozen=True, slots=True)
class NfseSettings:
    environment: str
    base_url: str
    certificate_path: Path
    certificate_password: str
    dps_schema_path: Path
    output_directory: Path
    timeout_seconds: float = 30.0

    @classmethod
    def from_env(cls, project_root: Path = PROJECT_ROOT) -> "NfseSettings":
        load_dotenv(project_root / ".env")
        environment = os.getenv("NFSE_ENV", "restricted").strip().lower()
        if environment not in API_BASE_URLS:
            raise NfseConfigurationError(
                "NFSE_ENV deve ser 'restricted' ou 'production'."
            )
        certificate_path = Path(os.getenv("NFSE_PFX_PATH", "")).expanduser()
        password = os.getenv("NFSE_PFX_PASSWORD")
        schema_path = Path(os.getenv(
            "NFSE_DPS_SCHEMA_PATH",
            str(project_root / "schemas/nfse/producao-restrita/DPS_v1.01.xsd"),
        )).expanduser()
        output_directory = Path(os.getenv(
            "NFSE_OUTPUT_DIR", str(project_root / "var/nfse")
        )).expanduser()
        base_url = os.getenv("NFSE_BASE_URL", API_BASE_URLS[environment]).rstrip("/")
        try:
            timeout = float(os.getenv("NFSE_TIMEOUT_SECONDS", "30"))
        except ValueError as exc:
            raise NfseConfigurationError(
                "NFSE_TIMEOUT_SECONDS precisa ser um número."
            ) from exc
        if not certificate_path.is_file():
            raise NfseConfigurationError(
                "Informe NFSE_PFX_PATH com o caminho de um certificado .pfx existente."
            )
        if password is None:
            raise NfseConfigurationError("Informe NFSE_PFX_PASSWORD no ambiente.")
        if not schema_path.is_file():
            raise NfseConfigurationError(
                f"XSD da DPS não encontrado: {schema_path}. "
                "Configure NFSE_DPS_SCHEMA_PATH."
            )
        if not base_url.startswith("https://"):
            raise NfseConfigurationError("NFSE_BASE_URL deve usar HTTPS.")
        if timeout <= 0:
            raise NfseConfigurationError(
                "NFSE_TIMEOUT_SECONDS deve ser maior que zero."
            )
        return cls(
            environment=environment,
            base_url=base_url,
            certificate_path=certificate_path.resolve(),
            certificate_password=password,
            dps_schema_path=schema_path.resolve(),
            output_directory=output_directory.resolve(),
            timeout_seconds=timeout,
        )
