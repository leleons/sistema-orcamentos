from __future__ import annotations

from datetime import date, datetime
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from hashlib import sha256
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


NFE_NS = "http://www.portalfiscal.inf.br/nfe"
SOAP_NFE_AUTORIZACAO_NS = "http://www.portalfiscal.inf.br/nfe/wsdl/NFeAutorizacao4"
NOME_HOMOLOGACAO = "NF-E EMITIDA EM AMBIENTE DE HOMOLOGACAO - SEM VALOR FISCAL"


def aliquotas_ibscbs_integral(ano: int) -> dict[str, float]:
    """Alíquotas nominais conhecidas, somente para CST 000/cClassTrib 000001.

    IT 2025.002 v1.50, seção 05. Não infere enquadramento ou base de cálculo.
    Não reutiliza a tabela de 2026 em anos futuros ainda não implementados.
    """
    return {"uf": 0.1, "municipal": 0.0, "cbs": 0.9} if ano == 2026 else {}


def aplicar_aliquotas_ibscbs_integral(item: dict, ano: int) -> dict:
    """Atualiza apenas taxas tabeladas de um enquadramento já selecionado."""
    import copy
    preparado = copy.deepcopy(item)
    rtc = preparado.get('ibscbs')
    if isinstance(rtc, dict) and rtc.get('cst') == '000' and rtc.get('classificacao') == '000001':
        rtc.update(aliquotas_ibscbs_integral(ano))
    return preparado


def validar_aliquotas_ibscbs_xml(xml: bytes) -> list[str]:
    raiz = ET.fromstring(xml)
    emissao = raiz.findtext(f".//{{{NFE_NS}}}ide/{{{NFE_NS}}}dhEmi") or ""
    try:
        ano = datetime.fromisoformat(emissao).year
    except ValueError:
        return ["Data de emissão inválida para conferir as alíquotas IBS/CBS."]
    padrao = aliquotas_ibscbs_integral(ano)
    pendencias = []
    for det in raiz.findall(f".//{{{NFE_NS}}}det"):
        rtc = det.find(f"{{{NFE_NS}}}imposto/{{{NFE_NS}}}IBSCBS")
        if rtc is None or rtc.findtext(f"{{{NFE_NS}}}CST") != "000" or rtc.findtext(f"{{{NFE_NS}}}cClassTrib") != "000001":
            continue
        for campo, tag, nome, rejeicao in (("uf", "pIBSUF", "IBS estadual", "1026"),
                ("municipal", "pIBSMun", "IBS municipal", "1032"), ("cbs", "pCBS", "CBS", "1037")):
            if campo not in padrao:
                continue
            valor = rtc.findtext(f".//{{{NFE_NS}}}{tag}")
            try:
                correto = valor is not None and Decimal(valor) == Decimal(str(padrao[campo]))
            except InvalidOperation:
                correto = False
            if not correto:
                aliquota = str(padrao[campo]).replace('.', ',')
                pendencias.append(f"Item {det.get('nItem')}: {nome} deve ser {aliquota}% em {ano} "
                                  f"para tributação integral 000/000001 (rejeição {rejeicao}).")
    return pendencias


def endpoint_autorizacao_nfe(uf: str, ambiente: str) -> str:
    if uf.upper() != "MG":
        return ""
    host = "nfe" if _ambiente(ambiente) == "1" else "hnfe"
    return f"https://{host}.fazenda.mg.gov.br/nfe2/services/NFeAutorizacao4"
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
    return str(_decimal(valor).quantize(quant, rounding=ROUND_HALF_UP))


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
    endereco_dest = dados.get("destinatario") or {}
    _tag(ide, "idDest", "2" if endereco_dest.get("uf") and endereco_dest["uf"].upper() != uf else "1")
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
    _tag(dest, "xNome", NOME_HOMOLOGACAO if _ambiente(dados.get("ambiente")) == "2" else _limitar(faturamento.get("cliente") or "Consumidor final", 60))
    if endereco_dest:
        ender_dest = _tag(dest, "enderDest")
        for campo, tag in (("logradouro", "xLgr"), ("numero", "nro"), ("bairro", "xBairro"),
                           ("codigo_municipio", "cMun"), ("municipio", "xMun"), ("uf", "UF")):
            _tag(ender_dest, tag, endereco_dest.get(campo))
            if campo == "numero" and endereco_dest.get("complemento"):
                _tag(ender_dest, "xCpl", _limitar(endereco_dest["complemento"], 60))
        if endereco_dest.get("cep"):
            _tag(ender_dest, "CEP", _somente_digitos(endereco_dest["cep"]))
        _tag(ender_dest, "cPais", "1058")
        _tag(ender_dest, "xPais", "BRASIL")
        if endereco_dest.get("telefone"):
            _tag(ender_dest, "fone", _somente_digitos(endereco_dest["telefone"]))
    _tag(dest, "indIEDest", str(endereco_dest.get("indicador_ie") or "9"))
    if endereco_dest.get("indicador_ie") == "1" and endereco_dest.get("ie"):
        _tag(dest, "IE", _somente_digitos(endereco_dest["ie"]))
    if endereco_dest.get("email"):
        _tag(dest, "email", _limitar(endereco_dest["email"], 60))

    total_produtos = Decimal("0")
    totais_rtc = dict(base=Decimal(0), uf=Decimal(0), municipal=Decimal(0), cbs=Decimal(0))
    tem_rtc = False
    totais_impostos = {k: Decimal(0) for k in ("vBC", "vICMS", "vPIS", "vCOFINS")}
    for indice, item in enumerate(itens, start=1):
        quantidade = _decimal(item.get("qtd") or 1)
        valor_unitario = _decimal(item.get("vunit"))
        valor_total = _valor_item(item)
        total_produtos += valor_total
        ncm = _somente_digitos(item.get("ncm") or dados.get("ncm"))
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
        fiscal = item.get("tributos") or {}
        base_icms = _decimal(fiscal.get("base_icms"))
        valor_icms = _decimal(_decimal_nfe(base_icms * _decimal(fiscal.get("icms")) / 100))
        if crt == "1":
            if str(item.get('csosn') or '102') != '102':
                raise ValueError('O gerador atual não implementa este CSOSN. Não é permitido convertê-lo silenciosamente para 102.')
            icms_sn = _tag(icms, "ICMSSN102")
            _tag(icms_sn, "orig", str(item.get("origem") or "0"))
            _tag(icms_sn, "CSOSN", "102")
        else:
            icms_00 = _tag(icms, "ICMS00")
            _tag(icms_00, "orig", str(item.get("origem") or "0"))
            _tag(icms_00, "CST", "00")
            _tag(icms_00, "modBC", "3")
            _tag(icms_00, "vBC", _decimal_nfe(base_icms))
            _tag(icms_00, "pICMS", _decimal_nfe(fiscal.get("icms"), 4))
            _tag(icms_00, "vICMS", _decimal_nfe(valor_icms))
            totais_impostos["vBC"] += _decimal(_decimal_nfe(base_icms))
            totais_impostos["vICMS"] += valor_icms
        pis = _tag(imposto, "PIS")
        pis_aliq = _tag(pis, "PISAliq")
        _tag(pis_aliq, "CST", "01")
        valor_pis = _decimal(_decimal_nfe(_decimal(fiscal.get("base_pis")) * _decimal(fiscal.get("pis")) / 100))
        _tag(pis_aliq, "vBC", _decimal_nfe(fiscal.get("base_pis")))
        _tag(pis_aliq, "pPIS", _decimal_nfe(fiscal.get("pis"), 4))
        _tag(pis_aliq, "vPIS", _decimal_nfe(valor_pis))
        totais_impostos["vPIS"] += valor_pis
        cofins = _tag(imposto, "COFINS")
        cofins_aliq = _tag(cofins, "COFINSAliq")
        _tag(cofins_aliq, "CST", "01")
        valor_cofins = _decimal(_decimal_nfe(_decimal(fiscal.get("base_cofins")) * _decimal(fiscal.get("cofins")) / 100))
        _tag(cofins_aliq, "vBC", _decimal_nfe(fiscal.get("base_cofins")))
        _tag(cofins_aliq, "pCOFINS", _decimal_nfe(fiscal.get("cofins"), 4))
        _tag(cofins_aliq, "vCOFINS", _decimal_nfe(valor_cofins))
        totais_impostos["vCOFINS"] += valor_cofins
        rtc = item.get("ibscbs") or dados.get("ibscbs")
        if rtc:
            if rtc.get("cst") != "000" or rtc.get("classificacao") != "000001":
                raise ValueError("Este fluxo suporta IBS/CBS de tributação integral 000/000001. Configure outro tratamento antes de emitir operações especiais.")
            base = _decimal(rtc.get("base"))
            if base < 0:
                raise ValueError("Base de IBS/CBS não pode ser negativa.")
            tem_rtc = True
            valores_rtc = {campo: _decimal(_decimal_nfe(base * _decimal(rtc.get(campo)) / 100))
                           for campo in ("uf", "municipal", "cbs")}
            totais_rtc["base"] += _decimal(_decimal_nfe(base))
            for campo in valores_rtc:
                totais_rtc[campo] += valores_rtc[campo]
            trib_rtc = _tag(imposto, "IBSCBS")
            _tag(trib_rtc, "CST", rtc["cst"])
            _tag(trib_rtc, "cClassTrib", rtc["classificacao"])
            grupo = _tag(trib_rtc, "gIBSCBS")
            _tag(grupo, "vBC", _decimal_nfe(base))
            for campo, grupo_nome, ptag, vtag in (("uf", "gIBSUF", "pIBSUF", "vIBSUF"), ("municipal", "gIBSMun", "pIBSMun", "vIBSMun")):
                sub = _tag(grupo, grupo_nome)
                _tag(sub, ptag, _decimal_nfe(rtc[campo], 4))
                _tag(sub, vtag, _decimal_nfe(valores_rtc[campo]))
            _tag(grupo, "vIBS", _decimal_nfe(valores_rtc["uf"] + valores_rtc["municipal"]))
            cbs = _tag(grupo, "gCBS")
            _tag(cbs, "pCBS", _decimal_nfe(rtc["cbs"], 4))
            _tag(cbs, "vCBS", _decimal_nfe(valores_rtc["cbs"]))

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
        _tag(icms_tot, nome, _decimal_nfe(totais_impostos[nome]) if nome in totais_impostos else valor)
    if tem_rtc:
        tot = _tag(total, "IBSCBSTot")
        _tag(tot, "vBCIBSCBS", _decimal_nfe(totais_rtc["base"]))
        ibs = _tag(tot, "gIBS")
        for campo, grupo_nome, vtag in (("uf", "gIBSUF", "vIBSUF"), ("municipal", "gIBSMun", "vIBSMun")):
            sub = _tag(ibs, grupo_nome)
            _tag(sub, "vDif", "0.00")
            _tag(sub, "vDevTrib", "0.00")
            _tag(sub, vtag, _decimal_nfe(totais_rtc[campo]))
        _tag(ibs, "vIBS", _decimal_nfe(totais_rtc["uf"] + totais_rtc["municipal"]))
        _tag(ibs, "vCredPres", "0.00")
        _tag(ibs, "vCredPresCondSus", "0.00")
        cbs = _tag(tot, "gCBS")
        _tag(cbs, "vDif", "0.00")
        _tag(cbs, "vDevTrib", "0.00")
        _tag(cbs, "vCBS", _decimal_nfe(totais_rtc["cbs"]))
        _tag(cbs, "vCredPres", "0.00")
        _tag(cbs, "vCredPresCondSus", "0.00")

    transp = _tag(inf, "transp")
    _tag(transp, "modFrete", "9")
    pag = _tag(inf, "pag")
    det_pag = _tag(pag, "detPag")
    _tag(det_pag, "tPag", "99")
    _tag(det_pag, "xPag", "Outros")
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
    endereco = dados.get("destinatario") or {}
    if str(endereco.get("indicador_ie") or "") not in {"1", "2", "9"}:
        pendencias.append("Confirme se o destinatário é contribuinte, isento ou não contribuinte do ICMS.")
    for campo in ("logradouro", "numero", "bairro", "municipio", "uf", "codigo_municipio"):
        if not _texto(endereco.get(campo)):
            pendencias.append(f"Endereço do destinatário: preencha {campo}.")
    if endereco.get("uf") not in CODIGO_UF:
        pendencias.append("UF do destinatário inválida; use duas letras maiúsculas.")
    if len(str(endereco.get("codigo_municipio") or "")) != 7 or not str(endereco.get("codigo_municipio") or "").isdigit():
        pendencias.append("Código IBGE do destinatário deve ter 7 dígitos.")
    if str(endereco.get("indicador_ie")) == "1" and not _somente_digitos(endereco.get("ie")):
        pendencias.append("Destinatário contribuinte: informe a Inscrição Estadual.")
    dest_xml = raiz.find(f".//{{{NFE_NS}}}dest")
    if dest_xml is None or not (dest_xml.findtext(f"{{{NFE_NS}}}CNPJ") or dest_xml.findtext(f"{{{NFE_NS}}}CPF")):
        pendencias.append("CPF/CNPJ do destinatário deve ter 11 ou 14 dígitos.")
    if not 1 <= int(_decimal(dados.get("serie") or 1)) <= 889:
        pendencias.append("Use série entre 1 e 889 para emissão por aplicativo próprio.")
    for idx, item in enumerate(itens, start=1):
        ncm_bruto = str(item.get("ncm") or dados.get("ncm") or "").replace(".", "").strip()
        cfop_bruto = str(item.get("cfop") or dados.get("cfop") or "").strip()
        ncm = _somente_digitos(ncm_bruto)
        cfop = _somente_digitos(cfop_bruto)
        if len(ncm) != 8 or not ncm_bruto.isascii() or not ncm_bruto.isdigit():
            pendencias.append(f"Item {idx}: NCM precisa ter 8 digitos.")
        if len(cfop) != 4 or not cfop_bruto.isascii() or not cfop_bruto.isdigit():
            pendencias.append(f"Item {idx}: CFOP precisa ter 4 digitos.")
        if _valor_item(item) <= 0:
            pendencias.append(f"Item {idx}: valor total precisa ser maior que zero.")
        if _decimal(item.get("qtd")) <= 0 or _decimal(item.get("vunit")) <= 0:
            pendencias.append(f"Item {idx}: quantidade e valor unitário devem ser positivos.")
        if abs(_decimal(_decimal_nfe(_decimal(item.get("qtd")) * _decimal(item.get("vunit")))) - _valor_item(item)) > Decimal("0.01"):
            pendencias.append(f"Item {idx}: total difere da quantidade multiplicada pelo valor unitário.")
        fiscal = item.get("tributos") or {}
        for campo in (("base_icms", "icms") if _crt(dados.get("regime_tributario")) != "1" else ()) + ("base_pis", "pis", "base_cofins", "cofins"):
            if fiscal.get(campo) is None:
                pendencias.append(f"Item {idx}: informe {campo} conforme a tributação da operação.")
            elif _decimal(fiscal[campo]) < 0 or (not campo.startswith("base_") and _decimal(fiscal[campo]) > 100):
                pendencias.append(f"Item {idx}: valor inválido para {campo}.")
        rtc = item.get("ibscbs") or dados.get("ibscbs")
        if rtc:
            for campo in ("base", "uf", "municipal", "cbs"):
                if rtc.get(campo) is None:
                    pendencias.append(f"Item {idx}: informe IBS/CBS {campo}.")
                elif _decimal(rtc[campo]) < 0 or (campo != "base" and _decimal(rtc[campo]) > 100):
                    pendencias.append(f"Item {idx}: IBS/CBS {campo} inválido.")
        if _crt(dados.get("regime_tributario")) in {"2", "3"} and not (item.get("ibscbs") or dados.get("ibscbs")):
            pendencias.append(f"Item {idx}: preencha IBS/CBS para o regime normal.")
    pendencias.extend(validar_aliquotas_ibscbs_xml(xml_bytes))
    return pendencias


def canonicalizar_elemento_nfe(elemento) -> bytes:
    """C14N 1.0 do subconjunto, preservando o contexto herdado.

    libxml2 pode inserir xmlns="" espúrios ao canonicalizar diretamente um
    descendente cujo namespace padrão difere de um ancestral (SignedInfo ds
    dentro de NFe). Uma cópia independente materializa os namespaces em escopo
    antes de aplicar C14N. Só os bytes usados no cálculo são derivados dela:
    nunca substitui, limpa nem reserializa a NFe assinada de transporte.
    """
    from lxml import etree

    copia = etree.fromstring(etree.tostring(elemento, with_tail=False),
                            etree.XMLParser(resolve_entities=False, no_network=True))
    # C14N inclusivo também herda atributos xml:* dos ancestrais omitidos.
    # tostring materializa namespaces, mas não esses atributos. O mais próximo
    # prevalece, e atributos do próprio elemento nunca são sobrescritos.
    for ancestral in elemento.iterancestors():
        for nome, valor in ancestral.attrib.items():
            if nome.startswith("{http://www.w3.org/XML/1998/namespace}") and nome not in copia.attrib:
                copia.set(nome, valor)
    return etree.tostring(copia, method="c14n", exclusive=False, with_comments=False)


def assinar_xml_nfe_produto(
    xml_bytes: bytes,
    cert_path: str,
    cert_password: str,
    *,
    signature_algorithm: str = "rsa-sha1",
    digest_algorithm: str = "sha1",
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
    # Algoritmos legados exigidos pelo MOC da NF-e, restritos a este assinador.
    class NFeSigner(XMLSigner):
        def check_deprecated_methods(self):
            pass

    signer = NFeSigner(
        method=methods.enveloped,
        signature_algorithm=signature_algorithm,
        digest_algorithm=digest_algorithm,
        c14n_algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315",
    )
    signer.namespaces = {None: "http://www.w3.org/2000/09/xmldsig#"}
    signed_root = signer.sign(root, key=key_pem, cert=cert_pem, reference_uri=reference_uri)
    # Consolida o namespace padrão ds antes da canonicalização final. Algumas
    # versões do signxml canonicalizam a árvore em memória diferentemente do
    # XML serializado quando Signature usa namespace padrão (exigência SEFAZ).
    import base64
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    signed_root = etree.fromstring(etree.tostring(signed_root))
    ds = "http://www.w3.org/2000/09/xmldsig#"
    signature = signed_root.find(f"{{{ds}}}Signature")
    signed_info = signature.find(f"{{{ds}}}SignedInfo")
    hash_types = {"sha1": hashes.SHA1, "sha256": hashes.SHA256}
    if digest_algorithm not in hash_types or signature_algorithm not in {"rsa-sha1", "rsa-sha256"}:
        raise ValueError("Algoritmo de assinatura NF-e não suportado.")
    digest = hashes.Hash(hash_types[digest_algorithm]())
    digest.update(canonicalizar_elemento_nfe(signed_root.find(f"{{{NFE_NS}}}infNFe")))
    signed_info.find(f".//{{{ds}}}DigestValue").text = base64.b64encode(digest.finalize()).decode("ascii")
    assinatura = key.sign(canonicalizar_elemento_nfe(signed_info), padding.PKCS1v15(), hash_types[signature_algorithm.removeprefix("rsa-")]())
    signature.find(f"{{{ds}}}SignatureValue").text = base64.b64encode(assinatura).decode("ascii")
    xml_assinado = etree.tostring(signed_root, encoding="utf-8", xml_declaration=True)
    registrar_integridade_nfe("apos_assinar", xml_assinado)
    # Verifica também o contexto efetivamente transmitido antes de registrar envio.
    validar_assinatura_nfe_produto(montar_envelope_nfe_autorizacao(xml_assinado))
    return xml_assinado


def extrair_nfe_assinada_bytes(xml: bytes) -> bytes:
    """Recorta a NFe original por offsets, sem tostring, decode ou normalização.

    Expat identifica as tags reais (não texto de comentários/CDATA) e informa
    offsets em bytes. A mesma extração serve para a NFe isolada e para o SOAP.
    A declaração XML e o BOM não pertencem ao elemento NFe comparado.
    """
    from xml.parsers import expat

    if not isinstance(xml, bytes):
        raise ValueError("O XML assinado deve ser fornecido em bytes UTF-8.")
    # Não converte encodings: o transporte fiscal usa exclusivamente UTF-8.
    parser = expat.ParserCreate(encoding="UTF-8", namespace_separator="}")
    inicio = fim = None
    profundidade = 0
    nivel_nfe = None
    quantidade = 0

    def iniciar(nome, attrs):
        nonlocal inicio, profundidade, nivel_nfe, quantidade
        profundidade += 1
        if nome == NFE_NS + "}NFe":
            quantidade += 1
            if quantidade > 1:
                raise ValueError("Esperada exatamente uma NF-e no documento.")
            inicio, nivel_nfe = parser.CurrentByteIndex, profundidade

    def terminar(nome):
        nonlocal fim, profundidade
        if nome == NFE_NS + "}NFe" and profundidade == nivel_nfe:
            posicao = parser.CurrentByteIndex
            if xml[posicao:posicao + 2] != b"</":
                raise ValueError("NF-e vazia não pode ser transmitida.")
            fim = xml.index(b">", posicao) + 1
        profundidade -= 1

    def declarar(versao, encoding, standalone):
        if encoding and encoding.upper().replace("-", "") != "UTF8":
            raise ValueError("O XML assinado deve permanecer em UTF-8.")

    def bloquear_dtd(*args):
        raise ValueError("DTD não permitida na NF-e.")

    parser.StartElementHandler = iniciar
    parser.EndElementHandler = terminar
    parser.XmlDeclHandler = declarar
    parser.StartDoctypeDeclHandler = bloquear_dtd
    try:
        parser.Parse(xml, True)
    except expat.ExpatError as erro:
        raise ValueError("XML da NF-e malformado; envio bloqueado.") from erro
    if inicio is None or fim is None:
        raise ValueError("Esperada exatamente uma NF-e no documento.")
    return xml[inicio:fim]


def sha256_nfe_assinada(xml: bytes) -> str:
    return sha256(extrair_nfe_assinada_bytes(xml)).hexdigest()


def registrar_integridade_nfe(etapa: str, xml: bytes, esperado: str | None = None) -> str:
    """Registra apenas hashes/metadados, nunca o XML, senha ou chave privada."""
    from lxml import etree
    from dsystem_erp.technical_logs import registrar_log_tecnico

    nfe = extrair_nfe_assinada_bytes(xml)
    atual = sha256(nfe).hexdigest()
    raiz = etree.fromstring(xml, etree.XMLParser(resolve_entities=False, no_network=True))
    nota = next(raiz.iter(f"{{{NFE_NS}}}NFe"))
    inf = nota.find(f"{{{NFE_NS}}}infNFe")
    si = nota.find("{http://www.w3.org/2000/09/xmldsig#}Signature/"
                   "{http://www.w3.org/2000/09/xmldsig#}SignedInfo")
    detalhes = dict(etapa=etapa, sha256_nfe=atual, sha256_documento=sha256(xml).hexdigest(),
                    bytes_nfe=len(nfe), sha256_esperado=esperado,
                    referencia=inf.get("Id") if inf is not None else "")
    # Bytes iguais não bastam: C14N inclusivo também considera os ancestrais.
    for campo, elemento in (("infNFe", inf), ("SignedInfo", si)):
        if elemento is not None:
            detalhes[f"sha256_{campo}_c14n"] = sha256(
                canonicalizar_elemento_nfe(elemento)).hexdigest()
    divergente = esperado is not None and atual != esperado
    registrar_log_tecnico("ERROR" if divergente else "INFO", "nfe_integridade",
                          "Comparação do XML assinado", detalhes)
    if divergente:
        raise ValueError(f"NF-e alterada após assinatura ({etapa}): SHA-256 divergente; envio bloqueado.")
    return atual


def montar_envelope_nfe_autorizacao(xml_assinado: bytes, c_uf: str = "31") -> bytes:
    from xml.sax.saxutils import escape

    from lxml import etree
    nfe_bytes = extrair_nfe_assinada_bytes(xml_assinado)
    root = etree.fromstring(xml_assinado, etree.XMLParser(resolve_entities=False, no_network=True))
    if root.tag != f"{{{NFE_NS}}}NFe":
        raise ValueError("O lote deve conter uma NFe assinada.")
    lote = root.findtext(f"{{{NFE_NS}}}infNFe/{{{NFE_NS}}}ide/{{{NFE_NS}}}nNF") or "1"
    # Nunca inserir a árvore assinada em outra árvore nem serializá-la de novo.
    # O SOAP usa somente namespaces padrão para não alterar o C14N inclusivo.
    prefixo = f"""<?xml version="1.0" encoding="utf-8"?>
<Envelope xmlns="http://www.w3.org/2003/05/soap-envelope">
  <Body>
    <nfeDadosMsg xmlns="{SOAP_NFE_AUTORIZACAO_NS}"><enviNFe xmlns="{NFE_NS}" versao="4.00"><idLote>{escape(lote)}</idLote><indSinc>1</indSinc>""".encode("utf-8")
    sufixo = b"""</enviNFe></nfeDadosMsg>
  </Body>
</Envelope>"""
    return prefixo + nfe_bytes + sufixo


def validar_assinatura_nfe_produto(xml: bytes) -> None:
    """Confere integridade XMLDSig no contexto recebido (NFe ou SOAP completo).

    Não substitui validação de validade/cadeia/CNPJ do A1 nem autorização SEFAZ.
    C14N inclusivo herda namespaces ancestrais: prefixos no SOAP alterariam
    tanto infNFe quanto SignedInfo, mesmo preservando o texto da NFe.
    """
    import base64
    import hmac
    from cryptography import x509
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    from lxml import etree

    ds = "http://www.w3.org/2000/09/xmldsig#"
    c14n = "http://www.w3.org/TR/2001/REC-xml-c14n-20010315"
    parser = etree.XMLParser(resolve_entities=False, no_network=True)
    try:
        raiz = etree.fromstring(xml, parser)
        if raiz.getroottree().docinfo.doctype:
            raise ValueError("DTD não permitida na NF-e.")
        notas = list(raiz.iter(f"{{{NFE_NS}}}NFe"))
        if len(notas) != 1:
            raise ValueError("Esperada exatamente uma NF-e assinada.")
        nota = notas[0]
        infos = nota.findall(f"{{{NFE_NS}}}infNFe")
        assinaturas = list(raiz.iter(f"{{{ds}}}Signature"))
        if len(infos) != 1 or len(assinaturas) != 1 or assinaturas[0].getparent() is not nota:
            raise ValueError("Estrutura de assinatura NF-e inválida ou ausente.")
        inf, assinatura = infos[0], assinaturas[0]
        identificador = inf.get("Id") or ""
        if not identificador.startswith("NFe") or len(raiz.xpath('//*[@Id=$id]', id=identificador)) != 1:
            raise ValueError("Identificador da NF-e inválido ou duplicado.")
        si = assinatura.find(f"{{{ds}}}SignedInfo")
        referencias = si.findall(f"{{{ds}}}Reference") if si is not None else []
        if len(referencias) != 1 or referencias[0].get("URI") != "#" + identificador:
            raise ValueError("A assinatura não referencia esta NF-e.")
        ref = referencias[0]
        if si.find(f"{{{ds}}}CanonicalizationMethod").get("Algorithm") != c14n:
            raise ValueError("Canonicalização NF-e não suportada.")
        transforms = [t.get("Algorithm") for t in ref.findall(f"{{{ds}}}Transforms/{{{ds}}}Transform")]
        if transforms != [ds + "enveloped-signature", c14n]:
            raise ValueError("Transformações de assinatura NF-e não suportadas.")
        digests = {ds + "sha1": hashes.SHA1, "http://www.w3.org/2001/04/xmlenc#sha256": hashes.SHA256}
        signatures = {ds + "rsa-sha1": hashes.SHA1, "http://www.w3.org/2001/04/xmldsig-more#rsa-sha256": hashes.SHA256}
        digest_type = digests[ref.find(f"{{{ds}}}DigestMethod").get("Algorithm")]
        signature_type = signatures[si.find(f"{{{ds}}}SignatureMethod").get("Algorithm")]
        digest = hashes.Hash(digest_type())
        digest.update(canonicalizar_elemento_nfe(inf))
        esperado = base64.b64decode(ref.findtext(f"{{{ds}}}DigestValue") or "", validate=True)
        if not hmac.compare_digest(digest.finalize(), esperado):
            raise ValueError("Conteúdo da NF-e difere do assinado (digest inválido).")
        certificado = x509.load_der_x509_certificate(base64.b64decode(
            assinatura.findtext(f"{{{ds}}}KeyInfo/{{{ds}}}X509Data/{{{ds}}}X509Certificate") or ""))
        chave = certificado.public_key()
        if not isinstance(chave, rsa.RSAPublicKey):
            raise ValueError("A assinatura NF-e exige chave RSA.")
        chave.verify(base64.b64decode(assinatura.findtext(f"{{{ds}}}SignatureValue") or "", validate=True),
                     canonicalizar_elemento_nfe(si), padding.PKCS1v15(), signature_type())
    except (ValueError, KeyError, AttributeError, InvalidSignature, etree.LxmlError) as erro:
        raise ValueError("Assinatura NF-e inválida; envio bloqueado antes de acessar a SEFAZ. " +
                         (str(erro) or "Assinatura difere do calculado.")) from erro


def enviar_xml_nfe_produto(
    endpoint: str,
    xml_assinado: bytes,
    cert_path: str,
    cert_password: str,
    *,
    c_uf: str = "31",
    timeout: int = 30,
    sha256_assinado: str | None = None,
) -> bytes:
    from urllib.error import HTTPError
    from urllib.request import Request, urlopen
    from urllib.parse import urlparse

    from dsystem_erp.services.nfse_soap import contexto_ssl_certificado_pfx

    hash_nfe = registrar_integridade_nfe("antes_lote", xml_assinado, sha256_assinado)
    root = ET.fromstring(xml_assinado)
    ambiente = root.findtext(f".//{{{NFE_NS}}}tpAmb")
    host = urlparse(endpoint).hostname
    if host in {"nfe.fazenda.mg.gov.br", "hnfe.fazenda.mg.gov.br"}:
        if (host.startswith("hnfe.") and ambiente != "2") or (host.startswith("nfe.") and ambiente != "1"):
            raise ValueError("Ambiente do XML não corresponde ao endpoint SEFAZ selecionado.")
    envelope = montar_envelope_nfe_autorizacao(xml_assinado, c_uf=c_uf)
    req = Request(
        endpoint,
        data=envelope,
        headers={
            "Content-Type": f'application/soap+xml; charset=utf-8; action="{SOAP_NFE_AUTORIZACAO_NS}/nfeAutorizacaoLote"',
        },
        method="POST",
    )
    # Confere o próprio Request.data, não uma cópia reserializada do XML.
    registrar_integridade_nfe("antes_envio", req.data, hash_nfe)
    validar_assinatura_nfe_produto(req.data)
    pendencias_rtc = validar_aliquotas_ibscbs_xml(req.data)
    if pendencias_rtc:
        raise ValueError("Envio bloqueado: " + " ".join(pendencias_rtc))
    try:
        with contexto_ssl_certificado_pfx(cert_path, cert_password) as ssl_context:
            with urlopen(req, timeout=timeout, context=ssl_context) as resp:
                return resp.read()
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        detalhe = f"HTTP Error {exc.code}: {exc.reason}"
        if body:
            detalhe = f"{detalhe}. {body[:1000]}"
        raise RuntimeError(detalhe) from exc


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

    protocolo = root.find(f".//{{{NFE_NS}}}infProt")
    cstat = protocolo.findtext(f"{{{NFE_NS}}}cStat", "") if protocolo is not None else first_text("cStat")
    motivo = protocolo.findtext(f"{{{NFE_NS}}}xMotivo", "") if protocolo is not None else first_text("xMotivo")
    info["cstat"] = cstat
    info["recibo"] = first_text("nRec")
    info["mensagem"] = f"{cstat} - {motivo}".strip(" -")
    info["protocolo"] = first_text("nProt")
    info["chave_acesso"] = first_text("chNFe")
    if cstat == "100":
        info["status"] = "Autorizada"
        if len(info["chave_acesso"]) == 44:
            info["numero_nota"] = str(int(info["chave_acesso"][25:34]))
    elif cstat in {"103", "105"}:
        info["status"] = "Processando"
    elif cstat:
        info["status"] = "Rejeitada"
    else:
        info["status"] = "Erro"
        info["mensagem"] = first_text("Text") or first_text("faultstring") or "Resposta sem código de situação da SEFAZ; consulte antes de reenviar."
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
