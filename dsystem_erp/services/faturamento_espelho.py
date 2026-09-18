"""Espelho completo dos dados enviados para faturamento e emissão de nota."""

from __future__ import annotations

import io
from html import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from dsystem_erp.services.faturamento import itens_faturamento_lista
from dsystem_erp.utils.datas import data_para_br
from dsystem_erp.utils.formatadores import formatar_moeda_br


def gerar_pdf_espelho_faturamento(faturamento: dict) -> bytes:
    buffer = io.BytesIO()
    documento = SimpleDocTemplate(
        buffer, pagesize=A4, rightMargin=16 * mm, leftMargin=16 * mm,
        topMargin=16 * mm, bottomMargin=16 * mm,
        title=f"Espelho de nota - Faturamento {faturamento.get('id') or ''}",
    )
    estilos = getSampleStyleSheet()
    titulo = ParagraphStyle(
        "EspelhoTitulo", parent=estilos["Title"], fontName="Helvetica-Bold",
        fontSize=18, leading=22, alignment=TA_CENTER, textColor=colors.HexColor("#07559B"),
    )
    corpo = ParagraphStyle(
        "EspelhoCorpo", parent=estilos["BodyText"], fontSize=8.5,
        leading=12, textColor=colors.HexColor("#20252B"),
    )
    rotulo = ParagraphStyle(
        "EspelhoRotulo", parent=corpo, fontName="Helvetica-Bold",
        textColor=colors.HexColor("#36404A"),
    )
    cabecalho_tabela = ParagraphStyle(
        "EspelhoCabecalhoTabela", parent=rotulo, textColor=colors.white,
    )
    direita = ParagraphStyle("EspelhoDireita", parent=corpo, alignment=TA_RIGHT)
    elementos = [
        Paragraph("ESPELHO DE NOTA / FATURAMENTO", titulo),
        Spacer(1, 5 * mm),
    ]
    modalidade = faturamento.get("modalidade_faturamento") or "Por item"
    cabecalho = [
        [Paragraph("LANÇAMENTO", rotulo), Paragraph(f"#{faturamento.get('id') or ''}", corpo),
         Paragraph("STATUS", rotulo), Paragraph(escape(str(faturamento.get("status") or "Aberto")), corpo)],
        [Paragraph("CLIENTE", rotulo), Paragraph(escape(str(faturamento.get("cliente") or "")), corpo),
         Paragraph("CPF/CNPJ", rotulo), Paragraph(escape(str(faturamento.get("cnpj") or "")), corpo)],
        [Paragraph("DATA", rotulo), Paragraph(data_para_br(faturamento.get("data_lanc")) or "", corpo),
         Paragraph("VENCIMENTO", rotulo), Paragraph(data_para_br(faturamento.get("vencimento")) or "", corpo)],
        [Paragraph("MODALIDADE", rotulo), Paragraph(escape(str(modalidade)), corpo),
         Paragraph("TIPO DE NOTA", rotulo), Paragraph(escape(str(faturamento.get("tipo_nota") or "")), corpo)],
        [Paragraph("PAGAMENTO", rotulo), Paragraph(escape(str(faturamento.get("forma_pag") or "")), corpo),
         Paragraph("PARCELAS", rotulo), Paragraph(escape(str(faturamento.get("parcelas") or "Não")), corpo)],
    ]
    tabela_cabecalho = Table(cabecalho, colWidths=[25 * mm, 67 * mm, 27 * mm, 59 * mm])
    tabela_cabecalho.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EAF2FA")),
        ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#EAF2FA")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#B8C3CE")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    elementos.extend([tabela_cabecalho, Spacer(1, 6 * mm)])
    if modalidade == "Por medição":
        elementos.extend([
            Paragraph("DADOS DA MEDIÇÃO", rotulo), Spacer(1, 2 * mm),
            Table([
                [Paragraph("Número", rotulo), Paragraph(escape(str(faturamento.get("medicao_numero") or "")), corpo),
                 Paragraph("Período", rotulo), Paragraph(
                     f"{data_para_br(faturamento.get('medicao_inicio')) or ''} a "
                     f"{data_para_br(faturamento.get('medicao_fim')) or ''}", corpo)],
                [Paragraph("Percentual", rotulo), Paragraph(
                    f"{float(faturamento.get('medicao_percentual') or 0):.2f}%".replace(".", ","), corpo),
                 Paragraph("Referência", rotulo), Paragraph(escape(str(faturamento.get("medicao_referencia") or "")), corpo)],
            ], colWidths=[25 * mm, 45 * mm, 25 * mm, 83 * mm], style=TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#B8C3CE")),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F4F6F8")),
                ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#F4F6F8")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ])), Spacer(1, 6 * mm),
        ])

    linhas = [[
        Paragraph("Tipo", cabecalho_tabela), Paragraph("Descrição", cabecalho_tabela),
        Paragraph("Qtd.", cabecalho_tabela), Paragraph("Unitário", cabecalho_tabela),
        Paragraph("Total", cabecalho_tabela),
    ]]
    for item in itens_faturamento_lista(faturamento.get("itens")):
        linhas.append([
            Paragraph(escape(str(item.get("tipo_item") or "")), corpo),
            Paragraph(escape(str(item.get("desc") or "")), corpo),
            Paragraph(str(item.get("qtd") or 0), direita),
            Paragraph(formatar_moeda_br(item.get("vunit") or 0), direita),
            Paragraph(formatar_moeda_br(item.get("vtotal") or 0), direita),
        ])
    linhas.append([
        "", Paragraph("TOTAL DO FATURAMENTO", rotulo), "", "",
        Paragraph(formatar_moeda_br(faturamento.get("valor_total") or 0), direita),
    ])
    tabela_itens = Table(linhas, colWidths=[25 * mm, 83 * mm, 17 * mm, 25 * mm, 28 * mm], repeatRows=1)
    tabela_itens.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#07559B")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#EAF2FA")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#B8C3CE")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    elementos.extend([Paragraph("PRODUTOS E SERVIÇOS", rotulo), Spacer(1, 2 * mm), tabela_itens])
    historicos = [
        ("Histórico / informações para a nota", faturamento.get("obs_nota")),
        ("Observação interna", faturamento.get("obs_interna")),
        ("Histórico da medição", faturamento.get("medicao_historico")),
        ("Orçamento de referência", faturamento.get("orc_ref")),
    ]
    for nome, valor in historicos:
        if valor:
            elementos.extend([
                Spacer(1, 5 * mm), Paragraph(nome.upper(), rotulo), Spacer(1, 1.5 * mm),
                Paragraph(escape(str(valor)).replace("\n", "<br/>"), corpo),
            ])
    documento.build(elementos)
    return buffer.getvalue()
