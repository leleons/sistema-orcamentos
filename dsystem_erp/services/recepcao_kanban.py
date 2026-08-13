"""Fluxo de recepção e etiquetas dos equipamentos de O.S."""

from __future__ import annotations

import io
from urllib.parse import urlencode


STATUS_KANBAN_OS = (
    "Recebido", "Triagem / Diagnóstico", "Aguardando aprovação",
    "Em execução", "Aguardando peça", "Pronto", "Entregue",
)


def proximo_status(status: str, direcao: int = 1) -> str:
    atual = status if status in STATUS_KANBAN_OS else STATUS_KANBAN_OS[0]
    indice = max(0, min(len(STATUS_KANBAN_OS) - 1, STATUS_KANBAN_OS.index(atual) + direcao))
    return STATUS_KANBAN_OS[indice]


def dados_qr_equipamento(registro: dict, base_url: str = "") -> str:
    dados = {
        "os": registro.get("os_id") or "",
        "item": registro.get("numero_item") or "",
        "cliente": registro.get("cliente") or "",
        "equipamento": registro.get("equipamento") or "",
        "serie": registro.get("numero_serie") or "",
        "chamado": registro.get("chamado_id") or "",
    }
    if base_url:
        return f"{base_url.rstrip('/')}/?{urlencode({'pagina': 'Recepção e Kanban', **dados})}"
    return " | ".join(f"{chave.upper()}: {valor}" for chave, valor in dados.items() if valor not in (None, ""))


def gerar_etiqueta_equipamento(registro: dict, base_url: str = "") -> bytes:
    from reportlab.graphics.barcode import code128
    from reportlab.graphics.barcode.qr import QrCodeWidget
    from reportlab.graphics.shapes import Drawing
    from reportlab.graphics import renderPDF
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    saida = io.BytesIO()
    largura, altura = 100 * mm, 50 * mm
    pdf = canvas.Canvas(saida, pagesize=(largura, altura))
    pdf.setTitle(f"Etiqueta {registro.get('numero_item') or registro.get('os_id')}")
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(5 * mm, 44 * mm, f"OS #{int(registro.get('os_id') or 0):05d}  |  ITEM {registro.get('numero_item') or ''}")
    pdf.setFont("Helvetica-Bold", 8)
    pdf.drawString(5 * mm, 38 * mm, str(registro.get("cliente") or "")[:48])
    pdf.setFont("Helvetica", 7.5)
    pdf.drawString(5 * mm, 33 * mm, f"Equip.: {str(registro.get('equipamento') or '')[:40]}")
    pdf.drawString(5 * mm, 29 * mm, f"Marca: {str(registro.get('marca') or '')[:28]}")
    pdf.drawString(5 * mm, 25 * mm, f"Série/Patrimônio: {str(registro.get('numero_serie') or '')[:26]}")
    if registro.get("chamado_id"):
        pdf.drawString(5 * mm, 21 * mm, f"Chamado vinculado: #{registro.get('chamado_id')}")

    codigo = str(registro.get("numero_item") or f"OS{registro.get('os_id') or 0}")
    barras = code128.Code128(codigo, barHeight=10 * mm, barWidth=0.32 * mm)
    barras.drawOn(pdf, 5 * mm, 5 * mm)
    pdf.setFont("Helvetica-Bold", 6.5)
    pdf.drawString(5 * mm, 2.5 * mm, codigo)
    qr = QrCodeWidget(dados_qr_equipamento(registro, base_url))
    limites = qr.getBounds(); tamanho = 27 * mm
    desenho = Drawing(tamanho, tamanho, transform=[tamanho / (limites[2] - limites[0]), 0, 0, tamanho / (limites[3] - limites[1]), 0, 0])
    desenho.add(qr)
    renderPDF.draw(desenho, pdf, 70 * mm, 5 * mm)
    pdf.showPage(); pdf.save()
    return saida.getvalue()
