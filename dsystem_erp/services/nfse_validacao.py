"""Validacoes locais de XML NFS-e antes do envio."""

from __future__ import annotations

from pathlib import Path


def validar_xml_nfse_basico(xml_bytes: bytes | str) -> list[str]:
    xml_texto = xml_bytes.decode("utf-8") if isinstance(xml_bytes, bytes) else str(xml_bytes)
    erros: list[str] = []
    for termo in ["GerarNfseEnvio", "CpfCnpj", "ValorServicos"]:
        if termo not in xml_texto:
            erros.append(f"Campo/tag obrigatorio ausente: {termo}")
    if "InfDeclaracaoPrestacaoServico" not in xml_texto and "InfRps" not in xml_texto:
        erros.append("Campo/tag obrigatorio ausente: InfRps ou InfDeclaracaoPrestacaoServico")
    return erros


def validar_xml_com_xsd(xml_bytes: bytes | str, xsd_path: str | Path) -> list[str]:
    """Valida XML contra um XSD quando lxml estiver instalado."""
    try:
        from lxml import etree
    except Exception as ex:
        return [f"lxml nao instalado para validacao XSD: {ex}"]

    try:
        xml_data = xml_bytes if isinstance(xml_bytes, bytes) else str(xml_bytes).encode("utf-8")
        schema_doc = etree.parse(str(xsd_path))
        schema = etree.XMLSchema(schema_doc)
        doc = etree.fromstring(xml_data)
        if schema.validate(doc):
            return []
        return [str(erro) for erro in schema.error_log]
    except Exception as ex:
        return [f"Falha na validacao XSD: {ex}"]
