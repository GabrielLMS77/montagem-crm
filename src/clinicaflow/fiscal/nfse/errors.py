class NfseError(Exception):
    """Erro-base da integração NFS-e."""


class NfseConfigurationError(NfseError):
    """Configuração ou arquivo necessário ausente."""


class NfseCertificateError(NfseError):
    """Falha ao abrir o certificado PKCS#12."""


class DpsValidationError(NfseError):
    """A DPS não atende ao XSD oficial."""


class NfseTransportError(NfseError):
    """Falha de rede ou do handshake TLS."""


class NfseApiError(NfseError):
    """A SEFIN rejeitou a solicitação ou retornou resposta inválida."""
