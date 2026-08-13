from __future__ import annotations

from datetime import date, datetime
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


NFE_NS = "http://www.portalfiscal.inf.br/nfe"
SOAP_NFE_AUTORIZACAO_NS = "http://www.portalfiscal.inf.br/nfe/wsdl/NFeAutorizacao4"
ET.register_namespace("", NFE_NS)

CODIGO_UF = {
    "AC": "12",
    "AL": "27",
    "AP": "16",
    "AM": "13",
    "BA": "29",
    "CE": "23",
    "DF": "53",
    "ES": "32",
    "GO": "52",
    "MA": "21",
    "MT": "51",
    "MS": "50",
    "MG": "31",
    "PA": "15",
    "PB": "25",
    "PR": "41",
    "PE": "26",
    "PI": "22",
    "RJ": "33",
    "RN": "24",
    "RS": "43",
    "RO": "11",
    "RR": "14",
    "SC": "42",
    "SP": "35",
    "SE": "28",
    "TO": "17",
}


def _somente_digitos(valor: Any) -> str:
    return "".join(ch for ch in str(valor or "") if ch.isdigit())


def _decimal(valor: Any) -> Decimal:
    try:
        return Decimal(str(valor or "0").replace(",", "."))
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _texto(valor: Any) -> str:
    return str(valor or "").strip()


def _limitar(valor: Any, tamanho: int) -> str:
    return _texto(valor)[:tamanho]


def _tag(pai: ET.Element, nome: str, texto: Any = None, attrs: dict[str, str] | None = None) -> ET.Element:
    node = ET.SubElement(pai, f"{{{NFE_NS}}}{nome}", attrs or {})
    if texto is not None:
        node.text = _texto(texto)
    return node


def _data_iso(valor: Any) -> str:
    if isinstance(valor, datetime):
        return valor.date().isoformat()
    if isinstance(valor, date):
        return valor.isoformat()
    return _texto(valor) or date.today().isoformat()


def _decimal_nfe(valor: Any, casas: int = 2) -> str:
    quant = Decimal("1").scaleb(-casas)
    return str(_decimal(valor).quantize(quant))


def _valor_item(item: dict[str, Any]) -> Decimal:
    quantidade = _decimal(item.get("qtd") or 1)
    valor_unitario = _decimal(item.get("vunit"))
    valor_total = _decimal(item.get("vtotal"))
    return valor_total if valor_total > 0 else quantidade * valor_unitario


def _crt(valor: Any) -> str:
    texto = _texto(valor)
    if texto and texto[0] in {"1", "2", "3"}:
        return texto[0]
    return "1"


def _ambiente(valor: Any) -> str:
    texto = _texto(valor).lower()
    return "1" if texto.startswith("prod") else "2"


def calcular_dv_chave_nfe(chave_sem_dv: str) -> str:
    soma = 0
    peso = 2
    for digito in reversed(_somente_digitos(chave_sem_dv)):
        soma += int(digito) * peso
        peso += 1
        if peso > 9:
            peso = 2
    resto = soma % 11
    dv = 11 - resto
    return "0" if dv >= 10 else str(dv)


def gerar_chave_acesso_nfe(dados: dict[str, Any], data_emissao: datetime, numero: int, c_nf: str) -> tuple[str, str]:
    uf = _texto(dados.get("uf") or "MG").upper()
    c_uf = CODIGO_UF.get(uf, "31")
    aamm = data_emissao.strftime("%y%m")
    cnpj = _somente_digitos(dados.get("emitente_cnpj") or "23524449000154").zfill(14)[-14:]
    modelo = "55"
    serie = str(int(_decimal(dados.get("serie") or 1))).zfill(3)
    numero_nf = str(int(numero)).zfill(9)
    tp_emis = "1"
    codigo = _somente_digitos(c_nf).zfill(8)[-8:]
    chave_sem_dv = f"{c_uf}{aamm}{cnpj}{modelo}{serie}{numero_nf}{tp_emis}{codigo}"
    return chave_sem_dv + calcular_dv_chave_nfe(chave_sem_dv), c_uf


def gerar_xml_nfe_produto_400(
    faturamento: dict[str, Any],
    itens: list[dict[str, Any]],
    dados: dict[str, Any],
) -> bytes:
    """Gera XML NF-e 4.00 para produto.

    O XML segue a estrutura nacional da NF-e. A autorizacao real ainda depende
    de certificado A1, inscricao estadual, credenciamento SEFAZ e endpoint do UF.
    """

    emissao = dados.get("data_emissao")
    if not isinstance(emissao, datetime):
        emissao = datetime.now().astimezone()
    numero_nf = int(_decimal(dados.get("numero") or faturamento.get("id") or 1))
    c_nf = _somente_digitos(dados.get("codigo_nf") or faturamento.get("id") or "1").zfill(8)[-8:]
    chave, c_uf = gerar_chave_acesso_nfe(dados, emissao, numero_nf, c_nf)
    uf = _texto(dados.get("uf") or "MG").upper()
    crt = _crt(dados.get("regime_tributario"))
    cpf_cnpj_dest = _somente_digitos(faturamento.get("cnpj") or faturamento.get("cpf_cnpj"))

    raiz = ET.Element(f"{{{NFE_NS}}}NFe")
    inf = _tag(raiz, "infNFe", attrs={"Id": f"NFe{chave}", "versao": "4.00"})

    ide = _tag(inf, "ide")
    _tag(ide, "cUF", c_uf)
    _tag(ide, "cNF", c_nf)
    _tag(ide, "natOp", _limitar(dados.get("natureza_operacao") or "Venda de mercadoria", 60))
    _tag(ide, "mod", "55")
    _tag(ide, "serie", int(_decimal(dados.get("serie") or 1)))
    _tag(ide, "nNF", numero_nf)
    _tag(ide, "dhEmi", emissao.isoformat(timespec="seconds"))
    _tag(ide, "tpNF", "1")
    _tag(ide, "idDest", "1")
    _tag(ide, "cMunFG", _somente_digitos(dados.get("codigo_municipio") or "3156700"))
    _tag(ide, "tpImp", "1")
    _tag(ide, "tpEmis", "1")
    _tag(ide, "cDV", chave[-1])
    _tag(ide, "tpAmb", _ambiente(dados.get("ambiente")))
    _tag(ide, "finNFe", "1")
    _tag(ide, "indFinal", "1")
    _tag(ide, "indPres", "1")
    _tag(ide, "procEmi", "0")
    _tag(ide, "verProc", "Dsystem ERP")

    emit = _tag(inf, "emit")
    _tag(emit, "CNPJ", _somente_digitos(dados.get("emitente_cnpj") or "23524449000154").zfill(14)[-14:])
    _tag(emit, "xNome", _limitar(dados.get("emitente_nome") or "Dsystem Tecnologia", 60))
    _tag(emit, "xFant", _limitar(dados.get("emitente_fantasia") or dados.get("emitente_nome") or "Dsystem Tecnologia", 60))
    ender_emit = _tag(emit, "enderEmit")
    _tag(ender_emit, "xLgr", _limitar(dados.get("emitente_logradouro") or "Rua Gloria", 60))
    _tag(ender_emit, "nro", _limitar(dados.get("emitente_numero") or "25", 60))
    _tag(ender_emit, "xBairro", _limitar(dados.get("emitente_bairro") or "Centro", 60))
    _tag(ender_emit, "cMun", _somente_digitos(dados.get("codigo_municipio") or "3156700"))
    _tag(ender_emit, "xMun", _limitar(dados.get("emitente_municipio") or "Sabara", 60))
    _tag(ender_emit, "UF", uf)
    _tag(ender_emit, "CEP", _somente_digitos(dados.get("emitente_cep") or "34500000")[:8])
    _tag(ender_emit, "cPais", "1058")
    _tag(ender_emit, "xPais", "BRASIL")
    telefone_emit = _somente_digitos(dados.get("emitente_telefone") or "")
    if telefone_emit:
        _tag(ender_emit, "fone", telefone_emit[:14])
    _tag(emit, "IE", _somente_digitos(dados.get("inscricao_estadual") or dados.get("emitente_ie")))
    _tag(emit, "CRT", crt)

    dest = _tag(inf, "dest")
    if len(cpf_cnpj_dest) == 14:
        _tag(dest, "CNPJ", cpf_cnpj_dest)
    elif len(cpf_cnpj_dest) == 11:
        _tag(dest, "CPF", cpf_cnpj_dest)
    _tag(dest, "xNome", _limitar(faturamento.get("cliente") or "Consumidor final", 60))
    _tag(dest, "indIEDest", "9")

    total_produtos = Decimal("0")
    for indice, item in enumerate(itens, start=1):
        quantidade = _decimal(item.get("qtd") or 1)
        valor_unitario = _decimal(item.get("vunit"))
        valor_total = _valor_item(item)
        total_produtos += valor_total
        ncm = _somente_digitos(item.get("ncm") or dados.get("ncm"))[:8]
        det = _tag(inf, "det", attrs={"nItem": str(indice)})
        prod = _tag(det, "prod")
        _tag(prod, "cProd", _limitar(item.get("codigo") or item.get("id") or indice, 60))
        _tag(prod, "cEAN", "SEM GTIN")
        _tag(prod, "xProd", _limitar(item.get("desc") or "Produto", 120))
        _tag(prod, "NCM", ncm)
        _tag(prod, "CFOP", _somente_digitos(item.get("cfop") or dados.get("cfop") or "5102")[:4])
        _tag(prod, "uCom", _limitar(item.get("unidade") or dados.get("unidade") or "UN", 6))
        _tag(prod, "qCom", _decimal_nfe(quantidade, 4))
        _tag(prod, "vUnCom", _decimal_nfe(valor_unitario, 10))
        _tag(prod, "vProd", _decimal_nfe(valor_total, 2))
        _tag(prod, "cEANTrib", "SEM GTIN")
        _tag(prod, "uTrib", _limitar(item.get("unidade") or dados.get("unidade") or "UN", 6))
        _tag(prod, "qTrib", _decimal_nfe(quantidade, 4))
        _tag(prod, "vUnTrib", _decimal_nfe(valor_unitario, 10))
        _tag(prod, "indTot", "1")

        imposto = _tag(det, "imposto")
        _tag(imposto, "vTotTrib", "0.00")
        icms = _tag(imposto, "ICMS")
        if crt in {"1", "2"}:
            icms_sn = _tag(icms, "ICMSSN102")
            _tag(icms_sn, "orig", "0")
            _tag(icms_sn, "CSOSN", "102")
        else:
            icms_00 = _tag(icms, "ICMS00")
            _tag(icms_00, "orig", "0")
            _tag(icms_00, "CST", "00")
            _tag(icms_00, "modBC", "3")
            _tag(icms_00, "vBC", "0.00")
            _tag(icms_00, "pICMS", "0.00")
            _tag(icms_00, "vICMS", "0.00")
        pis = _tag(imposto, "PIS")
        pis_aliq = _tag(pis, "PISAliq")
        _tag(pis_aliq, "CST", "01")
        _tag(pis_aliq, "vBC", "0.00")
        _tag(pis_aliq, "pPIS", "0.00")
        _tag(pis_aliq, "vPIS", "0.00")
        cofins = _tag(imposto, "COFINS")
        cofins_aliq = _tag(cofins, "COFINSAliq")
        _tag(cofins_aliq, "CST", "01")
        _tag(cofins_aliq, "vBC", "0.00")
        _tag(cofins_aliq, "pCOFINS", "0.00")
        _tag(cofins_aliq, "vCOFINS", "0.00")

    total = _tag(inf, "total")
    icms_tot = _tag(total, "ICMSTot")
    for nome, valor in [
        ("vBC", "0.00"),
        ("vICMS", "0.00"),
        ("vICMSDeson", "0.00"),
        ("vFCP", "0.00"),
        ("vBCST", "0.00"),
        ("vST", "0.00"),
        ("vFCPST", "0.00"),
        ("vFCPSTRet", "0.00"),
        ("vProd", _decimal_nfe(total_produtos, 2)),
        ("vFrete", "0.00"),
        ("vSeg", "0.00"),
        ("vDesc", "0.00"),
        ("vII", "0.00"),
        ("vIPI", "0.00"),
        ("vIPIDevol", "0.00"),
        ("vPIS", "0.00"),
        ("vCOFINS", "0.00"),
        ("vOutro", "0.00"),
        ("vNF", _decimal_nfe(total_produtos, 2)),
        ("vTotTrib", "0.00"),
    ]:
        _tag(icms_tot, nome, valor)

    transp = _tag(inf, "transp")
    _tag(transp, "modFrete", "9")
    pag = _tag(inf, "pag")
    det_pag = _tag(pag, "detPag")
    _tag(det_pag, "tPag", "99")
    _tag(det_pag, "vPag", _decimal_nfe(total_produtos, 2))

    obs = _texto(dados.get("observacoes"))
    if obs:
        inf_adic = _tag(inf, "infAdic")
        _tag(inf_adic, "infCpl", _limitar(obs, 5000))

    ET.indent(raiz, space="  ")
    return ET.tostring(raiz, encoding="utf-8", xml_declaration=True)


def validar_xml_nfe_produto_minimo(xml_bytes: bytes, dados: dict[str, Any], itens: list[dict[str, Any]]) -> list[str]:
    pendencias: list[str] = []
    try:
        raiz = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        return [f"XML NF-e invalido: {exc}"]
    if not raiz.tag.endswith("NFe"):
        pendencias.append("XML de produto precisa ter raiz NFe.")
    inf = raiz.find(f"{{{NFE_NS}}}infNFe")
    if inf is None:
        pendencias.append("XML de produto precisa conter infNFe.")
    elif len((inf.attrib.get("Id") or "").replace("NFe", "")) != 44:
        pendencias.append("Chave de acesso NF-e precisa ter 44 digitos.")
    if len(_somente_digitos(dados.get("emitente_cnpj"))) != 14:
        pendencias.append("CNPJ do emitente precisa ter 14 digitos.")
    if not _somente_digitos(dados.get("inscricao_estadual") or dados.get("emitente_ie")):
        pendencias.append("Inscricao Estadual do emitente e obrigatoria para NF-e de produto.")
    if not itens:
        pendencias.append("A NF-e de produto precisa ter ao menos um item.")
    for idx, item in enumerate(itens, start=1):
        ncm = _somente_digitos(item.get("ncm") or dados.get("ncm"))
        cfop = _somente_digitos(item.get("cfop") or dados.get("cfop"))
        if len(ncm) != 8:
            pendencias.append(f"Item {idx}: NCM precisa ter 8 digitos.")
        if len(cfop) != 4:
            pendencias.append(f"Item {idx}: CFOP precisa ter 4 digitos.")
        if _valor_item(item) <= 0:
            pendencias.append(f"Item {idx}: valor total precisa ser maior que zero.")
    return pendencias


def assinar_xml_nfe_produto(
    xml_bytes: bytes,
    cert_path: str,
    cert_password: str,
    *,
    signature_algorithm: str = "rsa-sha256",
    digest_algorithm: str = "sha256",
) -> bytes:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.serialization import pkcs12
    from lxml import etree
    from signxml import XMLSigner, methods

    with open(cert_path, "rb") as arquivo:
        key, cert, _chain = pkcs12.load_key_and_certificates(
            arquivo.read(),
            cert_password.encode("utf-8") if cert_password else None,
        )
    if key is None or cert is None:
        raise ValueError("Certificado PFX sem chave privada ou certificado.")

    key_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)

    parser = etree.XMLParser(remove_blank_text=True)
    root = etree.fromstring(xml_bytes, parser)
    inf = root.find(f".//{{{NFE_NS}}}infNFe")
    if inf is None:
        raise ValueError("infNFe nao encontrado para assinatura.")
    reference_uri = f"#{inf.get('Id')}"
    signer = XMLSigner(
        method=methods.enveloped,
        signature_algorithm=signature_algorithm,
        digest_algorithm=digest_algorithm,
        c14n_algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315",
    )
    signed_root = signer.sign(root, key=key_pem, cert=cert_pem, reference_uri=reference_uri)
    return etree.tostring(signed_root, encoding="utf-8", xml_declaration=True)


def montar_envelope_nfe_autorizacao(xml_assinado: bytes, c_uf: str = "31") -> bytes:
    from xml.sax.saxutils import escape

    xml_texto = xml_assinado.decode("utf-8", errors="ignore")
    return f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
  <soap:Header>
    <nfeCabecMsg xmlns="{SOAP_NFE_AUTORIZACAO_NS}">
      <cUF>{escape(c_uf)}</cUF>
      <versaoDados>4.00</versaoDados>
    </nfeCabecMsg>
  </soap:Header>
  <soap:Body>
    <nfeDadosMsg xmlns="{SOAP_NFE_AUTORIZACAO_NS}">{xml_texto}</nfeDadosMsg>
  </soap:Body>
</soap:Envelope>""".encode("utf-8")


def enviar_xml_nfe_produto(
    endpoint: str,
    xml_assinado: bytes,
    cert_path: str,
    cert_password: str,
    *,
    c_uf: str = "31",
    timeout: int = 30,
) -> bytes:
    from urllib.error import HTTPError
    from urllib.request import Request, urlopen

    from dsystem_erp.services.nfse_soap import contexto_ssl_certificado_pfx

    envelope = montar_envelope_nfe_autorizacao(xml_assinado, c_uf=c_uf)
    req = Request(
        endpoint,
        data=envelope,
        headers={
            "Content-Type": "application/soap+xml; charset=utf-8",
            "SOAPAction": "",
        },
        method="POST",
    )
    ssl_context, temp_paths = contexto_ssl_certificado_pfx(cert_path, cert_password)
    try:
        with urlopen(req, timeout=timeout, context=ssl_context) as resp:
            return resp.read()
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        detalhe = f"HTTP Error {exc.code}: {exc.reason}"
        if body:
            detalhe = f"{detalhe}. {body[:1000]}"
        raise RuntimeError(detalhe) from exc
    finally:
        for temp_path in temp_paths:
            try:
                temp_path.unlink(missing_ok=True)
            except Exception:
                pass


def analisar_retorno_nfe_produto(xml_retorno: bytes | str) -> dict[str, Any]:
    texto = xml_retorno.decode("utf-8", errors="ignore") if isinstance(xml_retorno, bytes) else str(xml_retorno or "")
    info: dict[str, Any] = {
        "status": "Recebida",
        "mensagem": "",
        "numero_nota": "",
        "chave_acesso": "",
        "protocolo": "",
    }
    try:
        root = ET.fromstring(texto.encode("utf-8"))
    except ET.ParseError:
        info["status"] = "Erro"
        info["mensagem"] = texto[:500]
        return info

    def first_text(sufixo: str) -> str:
        for node in root.iter():
            if node.tag.endswith(sufixo) and node.text:
                return node.text.strip()
        return ""

    cstat = first_text("cStat")
    motivo = first_text("xMotivo")
    info["mensagem"] = f"{cstat} - {motivo}".strip(" -")
    info["protocolo"] = first_text("nProt")
    info["chave_acesso"] = first_text("chNFe")
    if cstat == "100":
        info["status"] = "Autorizada"
    elif cstat:
        info["status"] = "Rejeitada"
    return info


def gerar_xml_nfe_produto_rascunho(
    faturamento: dict[str, Any],
    itens: list[dict[str, Any]],
    dados: dict[str, Any],
) -> bytes:
    """Gera um XML interno de produto para preparar a futura emissao NF-e/NFC-e.

    Este XML nao substitui o layout oficial da SEFAZ. Ele organiza os dados do
    faturamento de produto para conferencia e para o proximo passo fiscal.
    """

    raiz = ET.Element("NFeProdutoRascunho", {"versao": "0.1"})

    identificacao = ET.SubElement(raiz, "Identificacao")
    ET.SubElement(identificacao, "FaturamentoId").text = _texto(faturamento.get("id"))
    ET.SubElement(identificacao, "OrcamentoReferencia").text = _texto(faturamento.get("orcamento_ref"))
    ET.SubElement(identificacao, "Ambiente").text = _texto(dados.get("ambiente") or "homologacao")
    ET.SubElement(identificacao, "DataEmissao").text = _data_iso(dados.get("competencia"))
    ET.SubElement(identificacao, "NaturezaOperacao").text = _texto(dados.get("natureza_operacao") or "Venda de mercadoria")
    ET.SubElement(identificacao, "Finalidade").text = _texto(dados.get("finalidade") or "Normal")

    emitente = ET.SubElement(raiz, "Emitente")
    ET.SubElement(emitente, "Nome").text = _texto(dados.get("emitente_nome") or "Dsystem Tecnologia")
    ET.SubElement(emitente, "CNPJ").text = _somente_digitos(dados.get("emitente_cnpj") or "23524449000154")
    ET.SubElement(emitente, "Endereco").text = _texto(dados.get("emitente_endereco") or "Rua Gloria, 25 - Sabara/MG")

    destinatario = ET.SubElement(raiz, "Destinatario")
    ET.SubElement(destinatario, "Nome").text = _texto(faturamento.get("cliente"))
    ET.SubElement(destinatario, "CPFCNPJ").text = _somente_digitos(faturamento.get("cnpj") or faturamento.get("cpf_cnpj"))

    itens_node = ET.SubElement(raiz, "Itens")
    total_produtos = Decimal("0")
    for indice, item in enumerate(itens, start=1):
        quantidade = _decimal(item.get("qtd") or 1)
        valor_unitario = _decimal(item.get("vunit"))
        valor_total = _decimal(item.get("vtotal")) or (quantidade * valor_unitario)
        total_produtos += valor_total

        item_node = ET.SubElement(itens_node, "Item", {"numero": str(indice)})
        ET.SubElement(item_node, "Descricao").text = _texto(item.get("desc"))
        ET.SubElement(item_node, "NCM").text = _texto(dados.get("ncm") or item.get("ncm"))
        ET.SubElement(item_node, "CFOP").text = _texto(dados.get("cfop") or item.get("cfop") or "5102")
        ET.SubElement(item_node, "Unidade").text = _texto(item.get("unidade") or dados.get("unidade") or "UN")
        ET.SubElement(item_node, "Quantidade").text = f"{quantidade:.4f}"
        ET.SubElement(item_node, "ValorUnitario").text = f"{valor_unitario:.2f}"
        ET.SubElement(item_node, "ValorTotal").text = f"{valor_total:.2f}"
        ET.SubElement(item_node, "Observacoes").text = _texto(item.get("observacoes"))

    totais = ET.SubElement(raiz, "Totais")
    ET.SubElement(totais, "ValorProdutos").text = f"{total_produtos:.2f}"
    ET.SubElement(totais, "ValorNota").text = f"{total_produtos:.2f}"

    observacoes = ET.SubElement(raiz, "Observacoes")
    observacoes.text = _texto(dados.get("observacoes"))

    ET.indent(raiz, space="  ")
    return ET.tostring(raiz, encoding="utf-8", xml_declaration=True)


@dataclass
class NfeProdutoProntidao:
    pronto: bool
    pendencias: list[str]


def validar_prontidao_envio_nfe_produto(
    *,
    endpoint: str,
    cert_path: str,
    cert_password: str,
    ncm: str,
    cfop: str,
    inscricao_estadual: str,
    regime_tributario: str,
    itens: list[dict[str, Any]],
) -> NfeProdutoProntidao:
    """Valida se o faturamento tem o minimo para seguir para NF-e/SEFAZ.

    Produto nao usa NFS-e municipal. Para emitir NF-e oficial e necessario gerar
    o XML no leiaute nacional NF-e 4.00, assinar e transmitir para a SEFAZ.
    """

    pendencias: list[str] = []
    if not endpoint:
        pendencias.append("Configure o endpoint NFeAutorizacao4 da SEFAZ do estado.")
    if not cert_path:
        pendencias.append("Configure o caminho do certificado A1/PFX.")
    elif not Path(cert_path).exists():
        pendencias.append(f"Certificado A1/PFX nao encontrado: {cert_path}")
    if not cert_password:
        pendencias.append("Configure a senha do certificado A1/PFX.")
    if not inscricao_estadual:
        pendencias.append("Informe a Inscricao Estadual do emitente.")
    if not regime_tributario:
        pendencias.append("Informe o regime tributario/CRT do emitente.")
    if not ncm:
        pendencias.append("Informe o NCM dos produtos.")
    if not cfop:
        pendencias.append("Informe o CFOP da operacao.")
    if not itens:
        pendencias.append("Inclua ao menos um item de produto.")
    for idx, item in enumerate(itens, start=1):
        if not _texto(item.get("desc")):
            pendencias.append(f"Item {idx}: descricao obrigatoria.")
        if _decimal(item.get("qtd")) <= 0:
            pendencias.append(f"Item {idx}: quantidade precisa ser maior que zero.")
        if _decimal(item.get("vunit")) <= 0:
            pendencias.append(f"Item {idx}: valor unitario precisa ser maior que zero.")

    return NfeProdutoProntidao(pronto=not pendencias, pendencias=pendencias)
