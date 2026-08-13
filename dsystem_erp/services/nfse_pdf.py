"""Geracao do PDF auxiliar da nota autorizada."""

from __future__ import annotations

import io
from typing import Callable


def gerar_pdf_nota_autorizada_simples(nota: dict, retorno_info: dict, formatar_moeda: Callable | None = None) -> bytes:
    buffer = io.BytesIO()
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except Exception as ex:
        raise RuntimeError("Instale reportlab para gerar o PDF da nota.") from ex

    def moeda(valor):
        if formatar_moeda:
            return formatar_moeda(valor)
        try:
            return f"R$ {float(valor or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        except Exception:
            return "R$ 0,00"

    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=28, leftMargin=28, topMargin=28, bottomMargin=28)
    partes = [
        Paragraph("Documento Auxiliar da Nota Fiscal", styles["Title"]),
        Paragraph("Gerado pelo Sistema Dsystem ERP a partir do XML/retorno autorizado.", styles["Normal"]),
        Spacer(1, 12),
    ]
    dados = [
        ["Campo", "Informacao"],
        ["Status", retorno_info.get("status") or nota.get("status") or ""],
        ["Cliente", nota.get("cliente") or ""],
        ["CPF/CNPJ", nota.get("cpf_cnpj") or ""],
        ["Tipo", nota.get("tipo_nota") or ""],
        ["Numero", retorno_info.get("numero_nfse") or nota.get("numero_nota") or ""],
        ["Chave/Codigo", retorno_info.get("chave_acesso") or nota.get("chave_acesso") or ""],
        ["Protocolo", retorno_info.get("protocolo") or nota.get("protocolo") or ""],
        ["Competencia", nota.get("data_competencia") or ""],
        ["Valor", moeda(nota.get("valor_servicos"))],
        ["Mensagem", retorno_info.get("mensagem") or nota.get("mensagem_retorno") or ""],
    ]
    tabela = Table(dados, colWidths=[130, 360])
    tabela.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#004B8D")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BACKGROUND", (0, 1), (0, -1), colors.HexColor("#F2F4F7")),
            ]
        )
    )
    partes.append(tabela)
    partes.append(Spacer(1, 12))
    partes.append(Paragraph("Descricao", styles["Heading2"]))
    partes.append(Paragraph((nota.get("descricao") or "").replace("\n", "<br/>"), styles["Normal"]))
    doc.build(partes)
    return buffer.getvalue()
