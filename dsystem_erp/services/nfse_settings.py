"""Configuracoes centrais para emissao de NFS-e."""

from __future__ import annotations

from dataclasses import dataclass

from dsystem_erp.config import config_val


@dataclass(frozen=True)
class NfseSettings:
    cnpj: str
    inscricao_municipal: str
    ambiente: str
    certificado_pfx: str
    certificado_pfx_path: str
    certificado_password: str
    endpoint_soap: str


def get_nfse_settings() -> NfseSettings:
    return NfseSettings(
        cnpj=str(config_val("NFSE_CNPJ", "23524449000154") or ""),
        inscricao_municipal=str(config_val("NFSE_INSCRICAO_MUNICIPAL", "07395930011") or ""),
        ambiente=str(config_val("NFSE_AMBIENTE", "homologacao") or "homologacao"),
        certificado_pfx=str(config_val("NFSE_CERTIFICADO_PFX", "") or ""),
        certificado_pfx_path=str(config_val("NFSE_CERT_PFX_PATH", "") or ""),
        certificado_password=str(config_val("NFSE_CERT_PASSWORD", "") or ""),
        endpoint_soap=str(config_val("NFSE_ENDPOINT_SOAP", "https://bhisshomologaws.pbh.gov.br/bhiss-ws/nfse") or ""),
    )

