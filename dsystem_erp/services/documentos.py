from __future__ import annotations

import html
import io
from typing import Iterable

import pandas as pd


def gerar_excel_tabela(rows: Iterable[dict], titulo: str) -> bytes:
    df = pd.DataFrame(list(rows or []))
    html_tabela = df.to_html(index=False, escape=True) if not df.empty else "<p>Sem dados.</p>"
    titulo_seguro = html.escape(str(titulo or "Relatorio"))
    return f"<html><head><meta charset='utf-8'></head><body><h2>{titulo_seguro}</h2>{html_tabela}</body></html>".encode("utf-8")


def gerar_pdf_tabela_simples(rows: list[dict], titulo: str) -> bytes:
    buffer = io.BytesIO()
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except Exception as ex:
        raise RuntimeError("Instale reportlab para gerar PDF.") from ex

    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), leftMargin=18, rightMargin=18, topMargin=18, bottomMargin=18)
    estilos = getSampleStyleSheet()
    elementos = [Paragraph(str(titulo or "Relatorio"), estilos["Title"]), Spacer(1, 10)]
    if rows:
        colunas = list(rows[0].keys())
        dados = [colunas]
        for row in rows:
            dados.append([str(row.get(col, ""))[:120] for col in colunas])
        tabela_pdf = Table(dados, repeatRows=1)
        tabela_pdf.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#004488")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ]
            )
        )
        elementos.append(tabela_pdf)
    else:
        elementos.append(Paragraph("Sem dados.", estilos["Normal"]))
    doc.build(elementos)
    buffer.seek(0)
    return buffer.getvalue()

