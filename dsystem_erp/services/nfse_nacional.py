"""Emissao de NFS-e pelo Emissor Publico Nacional (DPS 1.01)."""

from __future__ import annotations

import base64
import gzip
import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs12
from lxml import etree
from signxml import XMLSigner, methods

from dsystem_erp.services.nfse_soap import contexto_ssl_certificado_pfx
from dsystem_erp.utils.formatadores import somente_digitos


NS_NFSE = "http://www.sped.fazenda.gov.br/nfse"
NS_DSIG = "http://www.w3.org/2000/09/xmldsig#"
VERSAO_DPS = "1.01"
ENDPOINT_HOMOLOGACAO = "https://sefin.producaorestrita.nfse.gov.br/API/SefinNacional"
ENDPOINT_PRODUCAO = "https://sefin.nfse.gov.br/SefinNacional"


@dataclass
class NfseNacionalResult:
    status: str
    mensagem: str
    xml_dps: bytes
    xml_dps_assinado: bytes
    resposta_json: dict
    xml_nfse: bytes | None = None
    chave_acesso: str = ""
    id_dps: str = ""
    numero_nfse: str = ""

    @property
    def aprovado(self) -> bool:
        return self.status == "Autorizada"


def endpoint_nacional(ambiente: str, endpoint_configurado: str = "") -> str:
    if str(endpoint_configurado or "").strip():
        return str(endpoint_configurado).strip().rstrip("/")
    return ENDPOINT_PRODUCAO if str(ambiente).lower() == "producao" else ENDPOINT_HOMOLOGACAO


def _tag(nome: str) -> str:
    return f"{{{NS_NFSE}}}{nome}"


def _texto(pai, nome: str, valor) -> etree._Element:
    elemento = etree.SubElement(pai, _tag(nome))
    elemento.text = str(valor)
    return elemento


def _data_iso(valor) -> str:
    if isinstance(valor, datetime):
        return valor.date().isoformat()
    if isinstance(valor, date):
        return valor.isoformat()
    texto = str(valor or "").strip()
    for formato in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(texto, formato).date().isoformat()
        except ValueError:
            pass
    raise ValueError("Data de competencia invalida para a DPS Nacional.")


def montar_id_dps(codigo_municipio: str, documento_emitente: str, serie: int | str, numero: int | str) -> str:
    municipio = somente_digitos(codigo_municipio)
    documento = somente_digitos(documento_emitente)
    if len(municipio) != 7:
        raise ValueError("O codigo IBGE do municipio emissor deve ter 7 digitos.")
    if len(documento) not in (11, 14):
        raise ValueError("O CPF/CNPJ do emitente da DPS deve ter 11 ou 14 digitos.")
    serie_num = int(serie)
    numero_num = int(numero)
    if not 1 <= serie_num <= 49999:
        raise ValueError("A serie de aplicativo proprio deve estar entre 1 e 49999.")
    if not 1 <= numero_num <= 999999999999999:
        raise ValueError("O numero da DPS deve estar entre 1 e 999999999999999.")
    tipo_inscricao = "1" if len(documento) == 11 else "2"
    documento_14 = documento.zfill(14)
    return f"DPS{municipio}{tipo_inscricao}{documento_14}{serie_num:05d}{numero_num:015d}"


def gerar_xml_dps_nacional(faturamento: dict, dados: dict) -> bytes:
    cnpj = somente_digitos(dados.get("cnpj_prestador"))
    if len(cnpj) != 14:
        raise ValueError("Configure o CNPJ do prestador com 14 digitos.")
    municipio = somente_digitos(dados.get("codigo_municipio"))
    serie = int(dados.get("serie_dps") or 1)
    numero = int(dados.get("numero_dps") or faturamento.get("id") or 0)
    id_dps = montar_id_dps(municipio, cnpj, serie, numero)
    codigo_tributacao = somente_digitos(dados.get("codigo_tributacao_nacional"))
    if len(codigo_tributacao) != 6:
        raise ValueError("O codigo de tributacao nacional deve ter exatamente 6 digitos (ex.: 010701).")
    documento_tomador = somente_digitos(
        faturamento.get("cnpj") or faturamento.get("cpf_cnpj")
    )
    if len(documento_tomador) not in (11, 14):
        raise ValueError("Informe um CPF ou CNPJ valido para o tomador.")
    nome_tomador = str(faturamento.get("cliente") or "").strip()
    if not nome_tomador:
        raise ValueError("Informe o nome do tomador.")
    descricao = str(dados.get("descricao") or "").strip()
    if not descricao:
        raise ValueError("Informe a descricao do servico.")
    valor = float(dados.get("valor") or 0)
    if valor <= 0:
        raise ValueError("O valor do servico deve ser maior que zero.")
    opcao_simples = str(dados.get("opcao_simples_nacional") or "").strip()
    if opcao_simples not in {"1", "2", "3"}:
        raise ValueError("Selecione a situacao do prestador perante o Simples Nacional.")

    root = etree.Element(_tag("DPS"), nsmap={None: NS_NFSE}, versao=VERSAO_DPS)
    inf = etree.SubElement(root, _tag("infDPS"), Id=id_dps)
    _texto(inf, "tpAmb", 1 if str(dados.get("ambiente")).lower() == "producao" else 2)
    emissao = dados.get("data_hora_emissao") or datetime.now().astimezone()
    if isinstance(emissao, datetime):
        emissao = emissao.isoformat(timespec="seconds")
    _texto(inf, "dhEmi", emissao)
    _texto(inf, "verAplic", str(dados.get("versao_aplicativo") or "DsystemERP_1.0")[:20])
    _texto(inf, "serie", serie)
    _texto(inf, "nDPS", numero)
    _texto(inf, "dCompet", _data_iso(dados.get("competencia") or date.today()))
    _texto(inf, "tpEmit", 1)
    _texto(inf, "cLocEmi", municipio)

    prestador = etree.SubElement(inf, _tag("prest"))
    _texto(prestador, "CNPJ", cnpj)
    inscricao = str(dados.get("inscricao_municipal") or "").strip()
    if inscricao:
        _texto(prestador, "IM", inscricao[:15])
    reg_trib = etree.SubElement(prestador, _tag("regTrib"))
    _texto(reg_trib, "opSimpNac", opcao_simples)
    if opcao_simples == "3" and str(dados.get("regime_apuracao_simples") or "").strip():
        _texto(reg_trib, "regApTribSN", dados["regime_apuracao_simples"])
    _texto(reg_trib, "regEspTrib", str(dados.get("regime_especial_tributacao") or "0"))

    tomador = etree.SubElement(inf, _tag("toma"))
    _texto(tomador, "CNPJ" if len(documento_tomador) == 14 else "CPF", documento_tomador)
    _texto(tomador, "xNome", nome_tomador[:150])
    telefone = somente_digitos(faturamento.get("telefone"))
    if 6 <= len(telefone) <= 20:
        _texto(tomador, "fone", telefone)
    email = str(faturamento.get("email") or "").strip()
    if email:
        _texto(tomador, "email", email[:80])

    servico = etree.SubElement(inf, _tag("serv"))
    local = etree.SubElement(servico, _tag("locPrest"))
    _texto(local, "cLocPrestacao", somente_digitos(dados.get("codigo_municipio_prestacao")) or municipio)
    codigo_servico = etree.SubElement(servico, _tag("cServ"))
    _texto(codigo_servico, "cTribNac", codigo_tributacao)
    codigo_municipal = somente_digitos(dados.get("codigo_tributacao_municipal"))
    if codigo_municipal:
        _texto(codigo_servico, "cTribMun", codigo_municipal[:3])
    _texto(codigo_servico, "xDescServ", descricao[:1000])
    observacoes = str(dados.get("observacoes") or "").strip()
    if observacoes:
        info_complementar = etree.SubElement(servico, _tag("infoCompl"))
        _texto(info_complementar, "xInfComp", observacoes[:2000])

    valores = etree.SubElement(inf, _tag("valores"))
    valor_servico = etree.SubElement(valores, _tag("vServPrest"))
    _texto(valor_servico, "vServ", f"{valor:.2f}")
    trib = etree.SubElement(valores, _tag("trib"))
    trib_municipal = etree.SubElement(trib, _tag("tribMun"))
    _texto(trib_municipal, "tribISSQN", str(dados.get("tributacao_issqn") or "1"))
    _texto(trib_municipal, "tpRetISSQN", str(dados.get("tipo_retencao_issqn") or "1"))
    aliquota = float(dados.get("aliquota_iss") or 0)
    if aliquota > 0 and dados.get("informar_aliquota", False):
        _texto(trib_municipal, "pAliq", f"{aliquota:.2f}")
    total_tributos = etree.SubElement(trib, _tag("totTrib"))
    _texto(total_tributos, "indTotTrib", 0)

    return etree.tostring(root, encoding="UTF-8", xml_declaration=True, pretty_print=False)


def assinar_xml_dps_nacional(xml_dps: bytes, cert_path: str, cert_password: str) -> bytes:
    caminho = Path(cert_path or "")
    if not caminho.exists():
        raise FileNotFoundError(f"Certificado PFX nao encontrado: {caminho}")
    chave, certificado, _ = pkcs12.load_key_and_certificates(
        caminho.read_bytes(), str(cert_password or "").encode("utf-8") or None
    )
    if chave is None or certificado is None:
        raise ValueError("Nao foi possivel extrair a chave e o certificado do PFX.")
    chave_pem = chave.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    cert_pem = certificado.public_bytes(serialization.Encoding.PEM)
    root = etree.fromstring(xml_dps, parser=etree.XMLParser(remove_blank_text=True))
    inf = root.find(_tag("infDPS"))
    if inf is None or not inf.get("Id"):
        raise ValueError("A DPS nao possui infDPS/Id para assinatura.")

    class LegacyXMLSigner(XMLSigner):
        def check_deprecated_methods(self):
            return None

    signer = LegacyXMLSigner(
        method=methods.enveloped,
        signature_algorithm="rsa-sha1",
        digest_algorithm="sha1",
        c14n_algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315",
    )
    signer.namespaces = {None: NS_DSIG}
    assinado = signer.sign(
        root,
        key=chave_pem,
        cert=cert_pem,
        reference_uri=f"#{inf.get('Id')}",
        id_attribute="Id",
    )
    return etree.tostring(assinado, encoding="UTF-8", xml_declaration=True, pretty_print=False)


def compactar_xml_base64(xml_bytes: bytes) -> str:
    return base64.b64encode(gzip.compress(xml_bytes, mtime=0)).decode("ascii")


def descompactar_xml_base64(valor: str) -> bytes:
    return gzip.decompress(base64.b64decode(valor))


def _mensagens_retorno(resposta: dict) -> str:
    itens = resposta.get("erros") or resposta.get("alertas") or []
    mensagens = []
    for item in itens if isinstance(itens, list) else [itens]:
        if isinstance(item, dict):
            codigo = item.get("Codigo") or item.get("codigo") or ""
            descricao = item.get("Descricao") or item.get("descricao") or item.get("mensagem") or ""
            complemento = item.get("Complemento") or item.get("complemento") or ""
            mensagens.append(" - ".join(v for v in (str(codigo), str(descricao), str(complemento)) if v))
        else:
            mensagens.append(str(item))
    return "; ".join(mensagens)


def enviar_dps_nacional(
    endpoint: str,
    xml_assinado: bytes,
    cert_path: str,
    cert_password: str,
    timeout: int = 60,
) -> dict:
    url = endpoint.rstrip("/") + "/nfse"
    corpo = json.dumps({"dpsXmlGZipB64": compactar_xml_base64(xml_assinado)}).encode("utf-8")
    requisicao = Request(
        url,
        data=corpo,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with contexto_ssl_certificado_pfx(cert_path, cert_password) as contexto:
            with urlopen(requisicao, timeout=timeout, context=contexto) as resposta:
                bruto = resposta.read().decode("utf-8", errors="replace")
    except HTTPError as erro:
        bruto = erro.read().decode("utf-8", errors="replace")
        try:
            detalhe = _mensagens_retorno(json.loads(bruto)) or bruto[:1000]
        except json.JSONDecodeError:
            detalhe = bruto[:1000]
        raise RuntimeError(f"API Nacional retornou HTTP {erro.code}: {detalhe}") from erro
    except URLError as erro:
        raise RuntimeError(f"Falha de conexao com a API Nacional: {erro.reason}") from erro
    try:
        return json.loads(bruto)
    except json.JSONDecodeError as erro:
        raise RuntimeError(f"A API Nacional retornou resposta invalida: {bruto[:500]}") from erro


def executar_fluxo_nfse_nacional(
    faturamento: dict,
    dados: dict,
    *,
    endpoint: str,
    cert_path: str,
    cert_password: str,
    timeout: int = 60,
) -> NfseNacionalResult:
    xml = gerar_xml_dps_nacional(faturamento, dados)
    assinado = assinar_xml_dps_nacional(xml, cert_path, cert_password)
    resposta = enviar_dps_nacional(endpoint, assinado, cert_path, cert_password, timeout)
    erros = resposta.get("erros") or []
    xml_b64 = resposta.get("nfseXmlGZipB64") or resposta.get("xmlNfseGZipB64") or ""
    xml_nfse = descompactar_xml_base64(xml_b64) if xml_b64 else None
    chave = str(resposta.get("chaveAcesso") or resposta.get("chave") or "")
    id_dps = str(resposta.get("idDPS") or etree.fromstring(xml).find(_tag("infDPS")).get("Id"))
    numero_nfse = str(resposta.get("numeroNfse") or resposta.get("numeroNFSe") or "")
    if xml_nfse:
        try:
            raiz_nfse = etree.fromstring(xml_nfse)
            inf_nfse = raiz_nfse.find(_tag("infNFSe"))
            chave = chave or (inf_nfse.get("Id", "").removeprefix("NFS") if inf_nfse is not None else "")
            numero_elem = raiz_nfse.find(f".//{_tag('nNFSe')}")
            numero_nfse = numero_nfse or (numero_elem.text if numero_elem is not None else "")
        except etree.XMLSyntaxError:
            pass
    status = "Rejeitada" if erros else ("Autorizada" if xml_nfse or chave else "Processando")
    mensagem = _mensagens_retorno(resposta) or (
        "NFS-e Nacional autorizada." if status == "Autorizada" else "DPS recebida pela API Nacional."
    )
    return NfseNacionalResult(status, mensagem, xml, assinado, resposta, xml_nfse, chave, id_dps, numero_nfse)
