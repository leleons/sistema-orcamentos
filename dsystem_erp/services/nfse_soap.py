"""Montagem de envelope SOAP e chamadas ao WebService de NFS-e."""

from __future__ import annotations

from contextlib import contextmanager, nullcontext
from pathlib import Path
import ssl
import tempfile
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import re

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs12

from dsystem_erp.services.nfse_xml import gerar_cabecalho_nfse_bh


def _texto_xml(valor: bytes | str) -> str:
    return valor.decode("utf-8") if isinstance(valor, bytes) else str(valor)


def _cdata(valor: bytes | str) -> str:
    texto = _texto_xml(valor)
    return "<![CDATA[" + texto.replace("]]>", "]]]]><![CDATA[>") + "]]>"


def _request_operacao_pbh(operacao: str) -> str:
    operacao_limpa = (operacao or "GerarNfse").strip()
    return operacao_limpa if operacao_limpa.endswith("Request") else f"{operacao_limpa}Request"


def _resumo_bloqueio_gocache(corpo: str) -> str:
    if "gocache" not in corpo.lower() and "Acesso bloqueado" not in corpo and "Erro 552" not in corpo:
        return ""

    req_id = ""
    match_id = re.search(r"ID da requisi[^:<]*(?::?</b>\s*|:\s*)([^<\s]+)", corpo, re.I)
    if not match_id:
        match_id = re.search(r"ID da requisi(?:ç|&ccedil;)ão:\s*([^<\s]+)", corpo, re.I)
    if match_id:
        req_id = f" ID da requisicao: {match_id.group(1)}."

    ip = ""
    match_ip = re.search(r"(?:Seu endere(?:ç|&ccedil;)o IP:</b>\s*|Endere(?:ç|&ccedil;)o de IP:\s*)([^<\s]+)", corpo, re.I)
    if match_ip:
        ip = f" IP bloqueado/testado: {match_ip.group(1)}."

    return (
        " A resposta veio da protecao GoCache/PBH antes do WebService processar a NFS-e. "
        "Isso indica bloqueio de seguranca/rede do acesso, nao erro de XML."
        f"{req_id}{ip} Teste pelo servidor de producao ou solicite liberacao desse acesso junto ao suporte BHISS/PBH."
    )


def montar_envelope_soap_nfse(
    xml_assinado: bytes | str,
    operacao: str = "GerarNfse",
    cabecalho_xml: bytes | str | None = None,
) -> bytes:
    """Monta o envelope SOAP no formato PBH/BHISS.

    O manual da PBH usa operacoes document/literal com dois campos no corpo:
    nfseCabecMsg e nfseDadosMsg. O XML da NFS-e fica dentro de nfseDadosMsg.
    """
    xml_texto = xml_assinado.decode("utf-8") if isinstance(xml_assinado, bytes) else str(xml_assinado)
    cabecalho = cabecalho_xml if cabecalho_xml is not None else gerar_cabecalho_nfse_bh()
    request_tag = _request_operacao_pbh(operacao)
    envelope = f"""<?xml version="1.0" encoding="utf-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ws="http://ws.bhiss.pbh.gov.br">
  <soapenv:Header/>
  <soapenv:Body>
    <ws:{request_tag}>
      <nfseCabecMsg>{_cdata(cabecalho)}</nfseCabecMsg>
      <nfseDadosMsg>{_cdata(xml_texto)}</nfseDadosMsg>
    </ws:{request_tag}>
  </soapenv:Body>
</soapenv:Envelope>"""
    return envelope.encode("utf-8")


@contextmanager
def contexto_ssl_certificado_pfx(cert_path: str | None = None, cert_password: str | None = None):
    """Cria SSLContext com certificado A1/PFX para mTLS.

    Alguns webservices de NFS-e exigem o certificado digital tambem na conexao
    HTTPS, alem da assinatura do XML. O urllib precisa de arquivos PEM
    separados; por isso convertemos o PFX em arquivos temporarios.
    """

    if not cert_path:
        yield None
        return

    caminho = Path(cert_path)
    if not caminho.exists():
        raise FileNotFoundError(f"Certificado PFX nao encontrado: {caminho}")

    senha = cert_password.encode("utf-8") if cert_password else None
    private_key, certificate, additional_certificates = pkcs12.load_key_and_certificates(caminho.read_bytes(), senha)
    if private_key is None or certificate is None:
        raise ValueError("Nao foi possivel extrair chave e certificado do PFX.")

    with tempfile.TemporaryDirectory(prefix="nfse_cert_") as tmp:
        tmp_path = Path(tmp)
        key_file = tmp_path / "key.pem"
        cert_file = tmp_path / "cert.pem"

        key_file.write_bytes(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )
        cert_pem = certificate.public_bytes(serialization.Encoding.PEM)
        for extra in additional_certificates or []:
            cert_pem += extra.public_bytes(serialization.Encoding.PEM)
        cert_file.write_bytes(cert_pem)

        contexto = ssl.create_default_context()
        contexto.load_cert_chain(certfile=str(cert_file), keyfile=str(key_file))
        yield contexto


def chamar_webservice_nfse(
    endpoint: str,
    xml_assinado: bytes | str,
    timeout: int = 30,
    operacao: str = "GerarNfse",
    cabecalho_xml: bytes | str | None = None,
    cert_path: str | None = None,
    cert_password: str | None = None,
) -> bytes:
    if not endpoint:
        raise ValueError("Endpoint SOAP da NFS-e nao configurado.")
    envelope = montar_envelope_soap_nfse(xml_assinado, operacao=operacao, cabecalho_xml=cabecalho_xml)
    request = Request(
        endpoint,
        data=envelope,
        headers={
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": "",
        },
        method="POST",
    )
    contexto_ssl = contexto_ssl_certificado_pfx(cert_path, cert_password) if cert_path else nullcontext(None)
    try:
        with contexto_ssl as contexto:
            with urlopen(request, timeout=timeout, context=contexto) as resposta:
                return resposta.read()
    except HTTPError as erro:
        corpo_erro = ""
        try:
            corpo_erro = erro.read().decode("utf-8", errors="replace")
        except Exception:
            corpo_erro = ""
        detalhe = ""
        endpoint_normalizado = endpoint.rstrip("/")
        detalhe_gocache = _resumo_bloqueio_gocache(corpo_erro)
        if erro.code == 404:
            detalhe = " Endpoint nao encontrado. Confira se a URL configurada e o endpoint oficial de emissao."
            if "adn." in endpoint and "nfse.gov.br" in endpoint:
                detalhe += (
                    " A URL parece ser da API Nacional REST. "
                    "A API Nacional usa JSON com DPS compactada, nao SOAP/XML ABRASF."
                )
                if endpoint_normalizado.endswith("/contribuintes"):
                    detalhe += f" O recurso REST Nacional costuma ficar abaixo de {endpoint_normalizado}/nfse."
        elif erro.code == 403:
            detalhe = detalhe_gocache or (
                " A PBH recusou a conexao com o WebService. Confira se o certificado A1/PFX esta configurado, "
                "se a senha esta correta, se o CNPJ do certificado e o mesmo do prestador e se a empresa esta "
                "habilitada no ambiente de homologacao/producao do BHISS."
            )
        elif erro.code == 496:
            detalhe = (
                " O servidor exigiu certificado SSL de cliente. Configure o certificado A1/PFX e a senha nas "
                "configuracoes da NFS-e para a chamada usar mTLS."
            )
        elif erro.code == 502:
            detalhe = detalhe_gocache or " O servidor intermediario da PBH fechou a conexao antes de concluir a resposta."
        raise RuntimeError(f"HTTP Error {erro.code}: {erro.reason}.{detalhe}") from erro


def consultar_protocolo_nfse(
    endpoint: str,
    protocolo: str,
    cnpj: str = "",
    inscricao_municipal: str = "",
    timeout: int = 30,
    cert_path: str | None = None,
    cert_password: str | None = None,
) -> bytes:
    if not protocolo:
        raise ValueError("Informe o protocolo para consulta.")
    xml_consulta = f"""<ConsultarLoteRpsEnvio xmlns="http://www.abrasf.org.br/nfse.xsd">
<Prestador>
  <CpfCnpj><Cnpj>{cnpj}</Cnpj></CpfCnpj>
  <InscricaoMunicipal>{inscricao_municipal}</InscricaoMunicipal>
</Prestador>
<Protocolo>{protocolo}</Protocolo>
</ConsultarLoteRpsEnvio>"""
    return chamar_webservice_nfse(
        endpoint,
        xml_consulta,
        timeout=timeout,
        operacao="ConsultarLoteRps",
        cert_path=cert_path,
        cert_password=cert_password,
    )
