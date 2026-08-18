from __future__ import annotations

import html
import io
import json
import re
from datetime import date
from pathlib import Path
from typing import Any

from dsystem_erp.services.estoque_fiscal import aplicar_regra_fiscal_item
from dsystem_erp.utils.datas import data_para_br


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EMPRESAS_ORCAMENTO = ("Dsystem Tecnologia", "LC Printer", "GT Solutions")


def _moeda_para_float(valor: Any) -> float:
    if isinstance(valor, (int, float)):
        return float(valor)
    texto = str(valor or "").replace("R$", "").strip().replace(".", "").replace(",", ".")
    try:
        return float(texto)
    except (TypeError, ValueError):
        return 0.0


def _formata_moeda(valor: Any) -> str:
    return f"R$ {_moeda_para_float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def multiplicador_orcamento_empresa(empresa: str) -> float:
    if "LC Printer" in str(empresa or ""):
        return 1.30
    if "GT" in str(empresa or ""):
        return 1.45
    return 1.0


def itens_orcamento_normalizados(valor: Any) -> list[dict]:
    if isinstance(valor, list):
        itens = valor
    else:
        try:
            itens = json.loads(valor or "[]")
        except (TypeError, ValueError, json.JSONDecodeError):
            itens = []
    normalizados = []
    for item in itens if isinstance(itens, list) else []:
        if not isinstance(item, dict):
            continue
        descricao = str(item.get("d") or item.get("desc") or item.get("descricao") or "").strip()
        try:
            quantidade = int(float(item.get("q") or item.get("qtd") or 0))
        except (TypeError, ValueError):
            quantidade = 0
        unitario = _moeda_para_float(item.get("v") if item.get("v") is not None else item.get("vunit"))
        total = _moeda_para_float(item.get("t") if item.get("t") is not None else item.get("vtotal"))
        total = total or (unitario * quantidade)
        tipo_item = item.get("tipo_item") or item.get("tipo") or item.get("tipo_nota") or "Serviço"
        if tipo_item not in {"Produto", "Serviço"}:
            tipo_item = "Serviço"
        if descricao or total:
            normalizados.append(
                aplicar_regra_fiscal_item({
                    "d": descricao,
                    "q": quantidade,
                    "v": unitario,
                    "t": total,
                    "tipo_item": tipo_item,
                    "estoque_id": item.get("estoque_id"),
                    "situacao_nota": item.get("situacao_nota") or "",
                    "origem_item": item.get("origem_item") or "",
                    "ajuste_preco_percentual": item.get("ajuste_preco_percentual") or 0,
                })
            )
    return normalizados


def nome_arquivo_orcamento(numero: Any, empresa: str) -> str:
    empresa_limpa = re.sub(r"[^A-Za-z0-9_-]+", "_", empresa or "orcamento").strip("_")
    numero_limpo = re.sub(r"[^A-Za-z0-9_-]+", "_", str(numero or "sem_numero")).strip("_")
    return f"orcamento_{numero_limpo}_{empresa_limpa}.pdf"


def dados_orcamento_base(
    numero,
    cliente,
    cpf_cnpj,
    itens,
    forma_pagamento,
    obs_pag="",
    obs_geral="",
    data_orc=None,
    telefone="",
    email="",
    endereco="",
    data_validade="",
) -> dict:
    return {
        "numero": numero,
        "cliente": cliente,
        "cpf_cnpj": cpf_cnpj,
        "itens": itens,
        "forma_pagamento": forma_pagamento,
        "obs_pag": obs_pag,
        "obs_geral": obs_geral,
        "data_orc": data_orc or date.today().strftime("%d/%m/%Y"),
        "telefone": telefone,
        "email": email,
        "endereco": endereco,
        "data_validade": data_validade,
    }


def gerar_pdf_orcamento_empresa(dados: dict, empresa: str) -> bytes:
    try:
        import reportlab
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import Image as RLImage
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError as ex:
        raise RuntimeError("Instale reportlab para gerar PDF.") from ex

    buffer = io.BytesIO()
    multiplicador = multiplicador_orcamento_empresa(empresa)
    cor = colors.HexColor("#004488") if "Dsystem" in empresa else colors.HexColor("#1c1762") if "LC Printer" in empresa else colors.HexColor("#4ba3d5")
    documento = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=14 * mm, rightMargin=14 * mm, topMargin=12 * mm, bottomMargin=12 * mm)
    pasta_fontes = Path(reportlab.__file__).resolve().parent / "fonts"
    if "OrcamentoSans" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("OrcamentoSans", str(pasta_fontes / "Vera.ttf")))
        pdfmetrics.registerFont(TTFont("OrcamentoSans-Bold", str(pasta_fontes / "VeraBd.ttf")))
    estilos = getSampleStyleSheet()
    estilos["Normal"].fontName = "OrcamentoSans"
    estilos["Title"].fontName = "OrcamentoSans-Bold"
    estilos.add(ParagraphStyle(name="Small", parent=estilos["Normal"], fontSize=8, leading=10))
    estilos.add(ParagraphStyle(name="Cell", parent=estilos["Normal"], fontSize=8, leading=9))
    elementos = []
    titulo = {"Dsystem Tecnologia": "Dsystem Tecnologia", "LC Printer": "LC Printer - Luiz Cláudio da Silveira-ME", "GT Solutions": "GT Solutions"}.get(empresa, empresa)
    endereco_empresa = {"Dsystem Tecnologia": "Rua Glória, 25 - Sabará/MG - CEP 34.700-150", "LC Printer": "CNPJ 11.024.413/0001-22 - R. Geralda Martins de Miranda, 244 - Maria Goretti - Belo Horizonte/MG - CEP 31.930-450 - (31) 3432-3593 / 9 8500-2691 - lc_printer@hotmail.com"}.get(empresa, "")
    estilo_titulo = ParagraphStyle(name="TituloOrc", parent=estilos["Title"], textColor=cor, fontSize=20, leading=24)
    caminho_logo = PROJECT_ROOT / "logo_lc_printer.jpg"
    if empresa == "LC Printer" and caminho_logo.exists():
        cabecalho = Table([[RLImage(str(caminho_logo), width=42 * mm, height=28.3 * mm), Paragraph(f"<b>{titulo}</b><br/><font size='8'>{endereco_empresa}</font>", estilo_titulo)]], colWidths=[48 * mm, 132 * mm])
        cabecalho.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 4), ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
        elementos.append(cabecalho)
    else:
        elementos.append(Paragraph(f"<b>{titulo}</b>", estilo_titulo))
        if endereco_empresa:
            elementos.append(Paragraph(endereco_empresa, estilos["Small"]))
    emissao = html.escape(str(dados.get("data_orc") or data_para_br(date.today())))
    texto_cabecalho = f"Orçamento Nº {html.escape(str(dados.get('numero') or ''))} - emissão {emissao}"
    if dados.get("data_validade"):
        texto_cabecalho += f" - válido até {html.escape(str(dados['data_validade']))}"
    elementos.extend([Paragraph(texto_cabecalho, estilos["Small"]), Spacer(1, 8)])
    cliente = [["Cliente", dados.get("cliente") or ""], ["CPF/CNPJ", dados.get("cpf_cnpj") or ""], ["Telefone", dados.get("telefone") or ""], ["E-mail", dados.get("email") or ""], ["Endereço", dados.get("endereco") or ""]]
    tabela_cliente = Table(cliente, colWidths=[28 * mm, 150 * mm])
    tabela_cliente.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.25, colors.grey), ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f2f4f7")), ("FONTNAME", (0, 0), (-1, -1), "OrcamentoSans"), ("FONTNAME", (0, 0), (0, -1), "OrcamentoSans-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 8), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    elementos.extend([tabela_cliente, Spacer(1, 10)])
    linhas = [["Item", "Descrição", "Qtd", "Unitário", "Total"]]
    total = 0.0
    for indice, item in enumerate(itens_orcamento_normalizados(dados.get("itens")), start=1):
        unitario = float(item.get("v") or 0) * multiplicador
        subtotal = float(item.get("t") or 0) * multiplicador
        total += subtotal
        linhas.append([indice, Paragraph(html.escape(str(item.get("d") or "")), estilos["Cell"]), int(item.get("q") or 0), _formata_moeda(unitario), _formata_moeda(subtotal)])
    if len(linhas) == 1:
        linhas.append(["", "Sem itens", "", "", _formata_moeda(0)])
    tabela_itens = Table(linhas, colWidths=[12 * mm, 92 * mm, 16 * mm, 30 * mm, 30 * mm], repeatRows=1)
    tabela_itens.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), cor), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONTNAME", (0, 0), (-1, -1), "OrcamentoSans"), ("FONTNAME", (0, 0), (-1, 0), "OrcamentoSans-Bold"), ("GRID", (0, 0), (-1, -1), 0.25, colors.grey), ("FONTSIZE", (0, 0), (-1, -1), 8), ("ALIGN", (2, 1), (-1, -1), "RIGHT"), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    elementos.extend([tabela_itens, Spacer(1, 8), Paragraph(f"<b>Total: {_formata_moeda(total)}</b>", ParagraphStyle(name="TotalOrc", parent=estilos["Normal"], fontSize=13, leading=16, alignment=2, textColor=cor)), Spacer(1, 10)])
    elementos.append(Paragraph(f"<b>Forma de pagamento:</b> {html.escape(str(dados.get('forma_pagamento') or ''))}", estilos["Small"]))
    if dados.get("obs_pag"):
        elementos.append(Paragraph(f"<b>Obs. pagamento:</b> {html.escape(str(dados['obs_pag']))}", estilos["Small"]))
    if dados.get("obs_geral"):
        elementos.append(Paragraph(f"<b>Observações:</b> {html.escape(str(dados['obs_geral']))}", estilos["Small"]))
    documento.build(elementos)
    return buffer.getvalue()


def gerar_pdfs_tres_orcamentos(dados: dict) -> dict[str, dict[str, Any]]:
    return {
        empresa: {"nome": nome_arquivo_orcamento(dados.get("numero"), empresa), "dados": gerar_pdf_orcamento_empresa(dados, empresa)}
        for empresa in EMPRESAS_ORCAMENTO
    }


def salvar_pdfs_orcamento(cursor, orc_id: int, dados: dict, criado_por: str, criado_em: str) -> None:
    cursor.execute("DELETE FROM orcamento_pdfs WHERE orc_id=?", (orc_id,))
    for empresa, pdf in gerar_pdfs_tres_orcamentos(dados).items():
        cursor.execute(
            """INSERT INTO orcamento_pdfs
               (orc_id, empresa, nome_arquivo, mime_type, arquivo, criado_por, criado_em)
               VALUES (?,?,?,?,?,?,?)""",
            (orc_id, empresa, pdf["nome"], "application/pdf", pdf["dados"], criado_por, criado_em),
        )
