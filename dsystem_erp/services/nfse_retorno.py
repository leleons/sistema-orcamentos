"""Leitura e classificacao de retornos XML da prefeitura."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET


def texto_tag_xml(xml_texto: str, nomes: list[str]) -> str:
    try:
        raiz = ET.fromstring(xml_texto.encode("utf-8") if isinstance(xml_texto, str) else xml_texto)
        nomes_normalizados = {n.lower() for n in nomes}
        for elem in raiz.iter():
            nome = elem.tag.split("}", 1)[-1].lower()
            if nome in nomes_normalizados and elem.text:
                return elem.text.strip()
    except Exception:
        pass
    for nome in nomes:
        achou = re.search(rf"<(?:\w+:)?{re.escape(nome)}[^>]*>(.*?)</(?:\w+:)?{re.escape(nome)}>", xml_texto, re.I | re.S)
        if achou:
            return re.sub(r"\s+", " ", achou.group(1)).strip()
    return ""


def analisar_retorno_nfse(xml_retorno: bytes | str) -> dict:
    texto = xml_retorno.decode("utf-8", errors="ignore") if isinstance(xml_retorno, bytes) else str(xml_retorno or "")
    codigo_erro = texto_tag_xml(texto, ["Codigo", "CodigoMensagem", "CodigoErro"])
    mensagem = texto_tag_xml(texto, ["Mensagem", "Correcao", "Descricao", "MensagemRetorno"])
    protocolo = texto_tag_xml(texto, ["Protocolo", "NumeroProtocolo"])
    numero_nfse = texto_tag_xml(texto, ["NumeroNfse", "Numero", "NumeroNota"])
    chave = texto_tag_xml(texto, ["CodigoVerificacao", "ChaveAcesso", "ChaveNfse"])
    lote = texto_tag_xml(texto, ["NumeroLote", "Lote"])
    texto_baixo = texto.lower()
    tem_erro = bool(codigo_erro or "mensagemretorno" in texto_baixo or "fault" in texto_baixo or "erro" in texto_baixo)
    aprovado = bool(numero_nfse or chave) and not tem_erro
    status = "Autorizada" if aprovado else ("Rejeitada" if tem_erro else "Recebida")
    if not mensagem:
        mensagem = "NFS-e autorizada." if aprovado else ("Lote recebido. Consulte o protocolo para confirmar a autorizacao." if protocolo else "Retorno recebido.")
    return {
        "status": status,
        "codigo_erro": codigo_erro,
        "mensagem": mensagem,
        "protocolo": protocolo,
        "numero_nfse": numero_nfse,
        "chave_acesso": chave,
        "numero_lote": lote,
        "xml": texto,
    }
