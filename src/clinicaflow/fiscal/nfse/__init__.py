"""Integração com o Emissor Público Nacional da NFS-e."""

from clinicaflow.fiscal.nfse.client import NfseClient, NfseIssueResult
from clinicaflow.fiscal.nfse.dps import DpsElement

__all__ = ["DpsElement", "NfseClient", "NfseIssueResult"]
