"""Fluxo completo de emissao NFS-e: XML, assinatura, validacao, SOAP e retorno."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from dsystem_erp.services.nfse_retorno import analisar_retorno_nfse
from dsystem_erp.services.nfse_signature import assinar_xml_nfse_bh
from dsystem_erp.services.nfse_soap import chamar_webservice_nfse, consultar_protocolo_nfse
from dsystem_erp.services.nfse_validacao import validar_xml_com_xsd, validar_xml_nfse_basico
from dsystem_erp.services.nfse_xml import gerar_cabecalho_nfse_bh, gerar_xml_nfse_bh_rps


@dataclass
class NfseWorkflowResult:
    status: str
    mensagem: str
    xml_gerado: bytes
    xml_assinado: bytes | None = None
    xml_retorno: bytes | None = None
    retorno_info: dict | None = None
    erros_validacao: list[str] | None = None

    @property
    def aprovado(self) -> bool:
        return (self.retorno_info or {}).get("status") == "Autorizada"


def preparar_xml_nfse(faturamento: dict, tipo_item: str, dados_nota: dict) -> bytes:
    return gerar_xml_nfse_bh_rps(faturamento, tipo_item, dados_nota)


def assinar_nfse(xml_bytes: bytes, cert_path: str, cert_password: str) -> bytes:
    return assinar_xml_nfse_bh(xml_bytes, cert_path=cert_path, cert_password=cert_password)


def validar_nfse(xml_bytes: bytes, xsd_path: str | None = None) -> list[str]:
    erros = validar_xml_nfse_basico(xml_bytes)
    if xsd_path:
        caminho = Path(xsd_path)
        if caminho.exists():
            erros.extend(validar_xml_com_xsd(xml_bytes, caminho))
        else:
            erros.append(f"Arquivo XSD nao encontrado: {caminho}")
    return erros


def enviar_nfse(
    endpoint: str,
    xml_assinado: bytes,
    timeout: int = 30,
    cert_path: str | None = None,
    cert_password: str | None = None,
) -> tuple[bytes, dict]:
    xml_retorno = chamar_webservice_nfse(
        endpoint,
        xml_assinado,
        timeout=timeout,
        operacao="GerarNfse",
        cabecalho_xml=gerar_cabecalho_nfse_bh(),
        cert_path=cert_path,
        cert_password=cert_password,
    )
    return xml_retorno, analisar_retorno_nfse(xml_retorno)


def consultar_nfse_por_protocolo(
    endpoint: str,
    protocolo: str,
    cnpj: str,
    inscricao_municipal: str,
    timeout: int = 30,
    cert_path: str | None = None,
    cert_password: str | None = None,
) -> tuple[bytes, dict]:
    xml_retorno = consultar_protocolo_nfse(
        endpoint,
        protocolo,
        cnpj,
        inscricao_municipal,
        timeout=timeout,
        cert_path=cert_path,
        cert_password=cert_password,
    )
    return xml_retorno, analisar_retorno_nfse(xml_retorno)


def executar_fluxo_emissao_nfse(
    faturamento: dict,
    tipo_item: str,
    dados_nota: dict,
    *,
    endpoint: str,
    cert_path: str,
    cert_password: str,
    xsd_path: str | None = None,
    timeout: int = 30,
    bloquear_com_erro_validacao: bool = False,
) -> NfseWorkflowResult:
    xml_gerado = preparar_xml_nfse(faturamento, tipo_item, dados_nota)
    xml_assinado = assinar_nfse(xml_gerado, cert_path, cert_password)
    erros = validar_nfse(xml_assinado, xsd_path)
    if erros and bloquear_com_erro_validacao:
        return NfseWorkflowResult(
            status="Validacao",
            mensagem="XML assinado, mas a validacao encontrou pendencias.",
            xml_gerado=xml_gerado,
            xml_assinado=xml_assinado,
            erros_validacao=erros,
        )

    xml_retorno, retorno_info = enviar_nfse(
        endpoint,
        xml_assinado,
        timeout=timeout,
        cert_path=cert_path,
        cert_password=cert_password,
    )
    return NfseWorkflowResult(
        status=retorno_info.get("status") or "Recebida",
        mensagem=retorno_info.get("mensagem") or "Retorno recebido.",
        xml_gerado=xml_gerado,
        xml_assinado=xml_assinado,
        xml_retorno=xml_retorno,
        retorno_info=retorno_info,
        erros_validacao=erros,
    )
