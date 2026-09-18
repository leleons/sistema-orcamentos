"""Regras e PDF dos certificados de garantia."""

from __future__ import annotations

import io
from datetime import date, datetime
from html import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from dsystem_erp.utils.datas import data_para_br, parse_data_flex


def proximo_numero_garantia(ultimo_id: int, ano: int | None = None) -> str:
    return f"GAR-{ano or date.today().year}-{int(ultimo_id or 0) + 1:05d}"


def validade_item_garantia(data_emissao, prazo_meses: int) -> date:
    emissao = parse_data_flex(data_emissao) or date.today()
    meses_totais = emissao.month - 1 + max(0, int(prazo_meses or 0))
    ano = emissao.year + meses_totais // 12
    mes = meses_totais % 12 + 1
    import calendar

    return date(ano, mes, min(emissao.day, calendar.monthrange(ano, mes)[1]))


def gerar_pdf_garantia(garantia: dict, itens: list[dict]) -> bytes:
    buffer = io.BytesIO()
    documento = SimpleDocTemplate(
        buffer, pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm,
        title=f"Garantia {garantia.get('numero') or ''}",
    )
    estilos = getSampleStyleSheet()
    titulo = ParagraphStyle(
        "GarantiaTitulo", parent=estilos["Title"], fontName="Helvetica-Bold",
        fontSize=19, leading=23, textColor=colors.HexColor("#07559B"),
        alignment=TA_CENTER, spaceAfter=4 * mm,
    )
    subtitulo = ParagraphStyle(
        "GarantiaSubtitulo", parent=estilos["Normal"], fontName="Helvetica-Bold",
        fontSize=10, leading=13, textColor=colors.HexColor("#323A46"),
    )
    corpo = ParagraphStyle(
        "GarantiaCorpo", parent=estilos["BodyText"], fontSize=9.5,
        leading=14, textColor=colors.HexColor("#20252B"),
    )
    pequeno = ParagraphStyle(
        "GarantiaPequeno", parent=corpo, fontSize=8, leading=11,
        textColor=colors.HexColor("#5B6470"),
    )
    cabecalho_tabela = ParagraphStyle(
        "GarantiaCabecalhoTabela", parent=subtitulo, textColor=colors.white,
    )
    elementos = [
        Paragraph("CERTIFICADO DE GARANTIA", titulo),
        Paragraph(
            f"Documento <b>{escape(str(garantia.get('numero') or ''))}</b>",
            ParagraphStyle("NumeroGarantia", parent=corpo, alignment=TA_CENTER),
        ),
        Spacer(1, 6 * mm),
    ]
    dados_cliente = [
        [Paragraph("CLIENTE", subtitulo), Paragraph(escape(str(garantia.get("cliente") or "")), corpo)],
        [Paragraph("CPF/CNPJ", subtitulo), Paragraph(escape(str(garantia.get("cliente_documento") or "Não informado")), corpo)],
        [Paragraph("EMISSÃO", subtitulo), Paragraph(data_para_br(garantia.get("data_emissao")) or "", corpo)],
        [Paragraph("ORIGEM", subtitulo), Paragraph(escape(str(garantia.get("origem") or "Compras / atendimento")), corpo)],
    ]
    tabela_cliente = Table(dados_cliente, colWidths=[35 * mm, 125 * mm])
    tabela_cliente.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EAF2FA")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#B8C3CE")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    elementos.extend([tabela_cliente, Spacer(1, 7 * mm), Paragraph("ITENS COBERTOS", subtitulo), Spacer(1, 2 * mm)])

    linhas_itens = [[
        Paragraph("Tipo", cabecalho_tabela), Paragraph("Produto ou serviço", cabecalho_tabela),
        Paragraph("Prazo", cabecalho_tabela), Paragraph("Válida até", cabecalho_tabela),
    ]]
    for item in itens or []:
        linhas_itens.append([
            Paragraph(escape(str(item.get("tipo") or "")), corpo),
            Paragraph(escape(str(item.get("descricao") or "")), corpo),
            Paragraph(f"{int(item.get('prazo_meses') or 0)} meses", corpo),
            Paragraph(data_para_br(item.get("validade")) or "", corpo),
        ])
    tabela_itens = Table(linhas_itens, colWidths=[27 * mm, 83 * mm, 23 * mm, 27 * mm], repeatRows=1)
    tabela_itens.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#07559B")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#B8C3CE")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F6F8FA")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    elementos.extend([tabela_itens, Spacer(1, 7 * mm)])
    elementos.append(Paragraph("CONDIÇÕES DA GARANTIA", subtitulo))
    elementos.append(Spacer(1, 2 * mm))
    elementos.append(Paragraph(
        escape(str(garantia.get("condicoes") or "Garantia válida para defeitos relacionados ao serviço ou peça descrita, conforme os prazos acima."))
        .replace("\n", "<br/>"), corpo,
    ))
    if garantia.get("historico"):
        elementos.extend([
            Spacer(1, 5 * mm), Paragraph("HISTÓRICO E INFORMAÇÕES", subtitulo),
            Spacer(1, 2 * mm), Paragraph(escape(str(garantia.get("historico"))).replace("\n", "<br/>"), corpo),
        ])
    elementos.extend([
        Spacer(1, 14 * mm),
        KeepTogether([
            Table([
                ["________________________________", "________________________________"],
                [Paragraph("Responsável pela emissão", pequeno), Paragraph("Cliente", pequeno)],
            ], colWidths=[80 * mm, 80 * mm], style=TableStyle([
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ])),
            Spacer(1, 7 * mm),
            Paragraph(
                f"Emitido em {datetime.now().strftime('%d/%m/%Y %H:%M')} por "
                f"{escape(str(garantia.get('criado_por') or 'Sistema Dsystem ERP'))}.",
                ParagraphStyle("RodapeGarantia", parent=pequeno, alignment=TA_CENTER),
            ),
        ]),
    ])
    documento.build(elementos)
    return buffer.getvalue()
