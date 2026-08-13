from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from datetime import date, datetime

from dsystem_erp.config import config_val
from dsystem_erp.utils.formatadores import somente_digitos


def xml_texto(parent, tag, valor):
    elem = ET.SubElement(parent, tag)
    elem.text = "" if valor is None else str(valor)
    return elem


def formatar_decimal_xml(valor):
    try:
        return f"{float(valor or 0):.2f}"
    except Exception:
        return "0.00"


def gerar_cabecalho_nfse_bh(versao: str = "1.00") -> bytes:
    versao_limpa = str(versao or "1.00").strip() or "1.00"
    root = ET.Element("cabecalho", versao=versao_limpa)
    xml_texto(root, "versaoDados", versao_limpa)
    return ET.tostring(root, encoding="utf-8", xml_declaration=False)


def gerar_xml_nfse_bh_rps(faturamento, tipo_item, dados_nota):
    hoje = date.today()
    competencia = dados_nota.get("competencia") or hoje
    if isinstance(competencia, str):
        try:
            competencia_iso = datetime.strptime(competencia, "%d/%m/%Y").date().isoformat()
        except Exception:
            competencia_iso = hoje.isoformat()
    else:
        competencia_iso = competencia.isoformat()

    numero_faturamento = int(faturamento.get("id") or 0)
    numero_lote = dados_nota.get("numero_lote") or numero_faturamento or int(time.time())
    numero_rps = dados_nota.get("numero_rps") or numero_faturamento or int(time.time())
    serie_rps = dados_nota.get("serie_rps") or "DS"

    prestador_cnpj = somente_digitos(config_val("NFSE_PRESTADOR_CNPJ", "23524449000154"))
    prestador_im = somente_digitos(config_val("NFSE_PRESTADOR_INSCRICAO_MUNICIPAL", "07395930011"))
    codigo_municipio = somente_digitos(config_val("NFSE_CODIGO_MUNICIPIO", "3106200")) or "3106200"
    codigo_servico = dados_nota.get("codigo_servico") or config_val("NFSE_CODIGO_SERVICO_PADRAO", "")
    item_lista = dados_nota.get("item_lista_servico") or config_val("NFSE_ITEM_LISTA_SERVICO_PADRAO", "")
    aliquota = float(dados_nota.get("aliquota_iss") or 0) / 100
    valor_servicos = float(dados_nota.get("valor") or 0)
    valor_iss = valor_servicos * aliquota

    root = ET.Element("GerarNfseEnvio", xmlns="http://www.abrasf.org.br/nfse.xsd")
    lote = ET.SubElement(root, "LoteRps", Id=f"L{numero_lote}")
    xml_texto(lote, "NumeroLote", numero_lote)
    prestador = ET.SubElement(lote, "Prestador")
    xml_texto(prestador, "Cnpj", prestador_cnpj)
    xml_texto(prestador, "InscricaoMunicipal", prestador_im)
    xml_texto(lote, "QuantidadeRps", 1)

    lista_rps = ET.SubElement(lote, "ListaRps")
    rps = ET.SubElement(lista_rps, "Rps")
    inf_rps = ET.SubElement(rps, "InfRps", Id=f"RPS{numero_rps}")
    identificacao_rps = ET.SubElement(inf_rps, "IdentificacaoRps")
    xml_texto(identificacao_rps, "Numero", numero_rps)
    xml_texto(identificacao_rps, "Serie", serie_rps)
    xml_texto(identificacao_rps, "Tipo", 1)
    xml_texto(inf_rps, "DataEmissao", competencia_iso)
    xml_texto(inf_rps, "NaturezaOperacao", config_val("NFSE_NATUREZA_OPERACAO", "1"))
    regime_especial = config_val("NFSE_REGIME_ESPECIAL_TRIBUTACAO", "")
    if regime_especial:
        xml_texto(inf_rps, "RegimeEspecialTributacao", regime_especial)
    xml_texto(inf_rps, "OptanteSimplesNacional", config_val("NFSE_OPTANTE_SIMPLES", "2"))
    xml_texto(inf_rps, "IncentivadorCultural", config_val("NFSE_INCENTIVADOR_CULTURAL", "2"))
    xml_texto(inf_rps, "Status", 1)

    servico = ET.SubElement(inf_rps, "Servico")
    valores = ET.SubElement(servico, "Valores")
    xml_texto(valores, "ValorServicos", formatar_decimal_xml(valor_servicos))
    xml_texto(valores, "ValorDeducoes", "0.00")
    xml_texto(valores, "ValorPis", "0.00")
    xml_texto(valores, "ValorCofins", "0.00")
    xml_texto(valores, "ValorInss", "0.00")
    xml_texto(valores, "ValorIr", "0.00")
    xml_texto(valores, "ValorCsll", "0.00")
    xml_texto(valores, "IssRetido", 2)
    xml_texto(valores, "ValorIss", formatar_decimal_xml(valor_iss))
    xml_texto(valores, "Aliquota", f"{aliquota:.4f}")
    if item_lista:
        xml_texto(servico, "ItemListaServico", item_lista)
    xml_texto(servico, "CodigoTributacaoMunicipio", codigo_servico)
    xml_texto(servico, "Discriminacao", dados_nota.get("descricao") or "")
    xml_texto(servico, "CodigoMunicipio", codigo_municipio)

    tomador = ET.SubElement(inf_rps, "Tomador")
    identificacao_tomador = ET.SubElement(tomador, "IdentificacaoTomador")
    cpf_cnpj = ET.SubElement(identificacao_tomador, "CpfCnpj")
    doc_tomador = somente_digitos(faturamento.get("cnpj") or faturamento.get("cpf_cnpj"))
    if not doc_tomador:
        raise ValueError("CPF/CNPJ do tomador nao informado para gerar a NFS-e.")
    xml_texto(cpf_cnpj, "Cnpj" if len(doc_tomador) > 11 else "Cpf", doc_tomador)
    xml_texto(tomador, "RazaoSocial", faturamento.get("cliente") or "")

    if dados_nota.get("observacoes"):
        xml_texto(inf_rps, "OutrasInformacoes", dados_nota.get("observacoes"))

    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)
