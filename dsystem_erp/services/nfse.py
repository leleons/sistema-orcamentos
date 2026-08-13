"""Fachada de compatibilidade para os servicos de NFS-e.

Novos codigos devem importar diretamente os modulos especificos:
nfse_xml, nfse_signature, nfse_validacao, nfse_soap, nfse_retorno e nfse_pdf.
"""

from __future__ import annotations

from dsystem_erp.services.nfse_retorno import analisar_retorno_nfse, texto_tag_xml
from dsystem_erp.services.nfse_settings import NfseSettings, get_nfse_settings
from dsystem_erp.services.nfse_soap import consultar_protocolo_nfse, chamar_webservice_nfse, montar_envelope_soap_nfse
from dsystem_erp.services.nfse_validacao import validar_xml_com_xsd, validar_xml_nfse_basico
from dsystem_erp.services.nfse_workflow import (
    NfseWorkflowResult,
    assinar_nfse,
    consultar_nfse_por_protocolo,
    enviar_nfse,
    executar_fluxo_emissao_nfse,
    preparar_xml_nfse,
    validar_nfse,
)

__all__ = [
    "NfseSettings",
    "analisar_retorno_nfse",
    "chamar_webservice_nfse",
    "consultar_protocolo_nfse",
    "get_nfse_settings",
    "montar_envelope_soap_nfse",
    "NfseWorkflowResult",
    "assinar_nfse",
    "consultar_nfse_por_protocolo",
    "enviar_nfse",
    "executar_fluxo_emissao_nfse",
    "preparar_xml_nfse",
    "texto_tag_xml",
    "validar_nfse",
    "validar_xml_com_xsd",
    "validar_xml_nfse_basico",
]
