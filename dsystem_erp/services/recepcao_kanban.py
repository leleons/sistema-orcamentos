"""Fluxo de recepção e etiquetas dos equipamentos de O.S."""

from __future__ import annotations

import io
from urllib.parse import urlencode


STATUS_KANBAN_OS = (
    "Recebido", "Triagem / Diagnóstico", "Aguardando aprovação",
    "Em execução", "Aguardando peça", "Pronto", "Entregue",
)

CORES_KANBAN_OS = {
    "Recebido": "#3b82f6",
    "Triagem / Diagnóstico": "#8b5cf6",
    "Aguardando aprovação": "#f59e0b",
    "Em execução": "#06b6d4",
    "Aguardando peça": "#f97316",
    "Pronto": "#22c55e",
    "Entregue": "#64748b",
}


def texto_cartao_equipamento(item: dict) -> str:
    """Monta um cartão legível e com identificador único para o quadro."""
    equipamento_id = int(item.get("id") or 0)
    os_id = int(item.get("os_id") or 0)
    numero_item = str(item.get("numero_item") or f"ITEM-{equipamento_id}")
    cliente = str(item.get("cliente") or "Cliente não informado").strip()
    equipamento = " · ".join(
        parte for parte in (
            str(item.get("tipo_equipamento") or "").strip(),
            str(item.get("equipamento") or "").strip(),
        )
        if parte
    ) or "Equipamento não informado"
    serie = str(item.get("numero_serie") or "").strip()
    complemento = f" · Série {serie}" if serie else ""
    return f"OS #{os_id:05d} · {numero_item}\n{cliente}\n{equipamento}{complemento}\nEQ-{equipamento_id}"


def montar_quadro_equipamentos(equipamentos: list[dict]) -> tuple[list[dict], dict[str, int]]:
    """Converte os equipamentos do banco para as colunas do componente."""
    por_status = {status: [] for status in STATUS_KANBAN_OS}
    cartao_para_id = {}
    ordenados = sorted(
        (dict(item) for item in equipamentos),
        key=lambda item: (int(item.get("kanban_ordem") or 0), -int(item.get("id") or 0)),
    )
    for item in ordenados:
        status = item.get("kanban_status") or STATUS_KANBAN_OS[0]
        if status not in por_status:
            status = STATUS_KANBAN_OS[0]
        texto = texto_cartao_equipamento(item)
        por_status[status].append(texto)
        cartao_para_id[texto] = int(item.get("id") or 0)
    return (
        [{"header": status, "items": por_status[status]} for status in STATUS_KANBAN_OS],
        cartao_para_id,
    )


def alteracoes_do_quadro(
    quadro_resultado: list[dict] | None,
    equipamentos: list[dict],
    cartao_para_id: dict[str, int],
) -> list[dict]:
    """Calcula somente mudanças válidas de coluna ou ordem feitas no quadro."""
    atuais = {int(item.get("id") or 0): dict(item) for item in equipamentos}
    alteracoes = []
    ids_processados = set()
    for coluna in quadro_resultado or []:
        status = coluna.get("header")
        if status not in STATUS_KANBAN_OS:
            continue
        for ordem, cartao in enumerate(coluna.get("items") or []):
            equipamento_id = cartao_para_id.get(cartao)
            if not equipamento_id or equipamento_id in ids_processados or equipamento_id not in atuais:
                continue
            ids_processados.add(equipamento_id)
            item = atuais[equipamento_id]
            status_anterior = item.get("kanban_status") or STATUS_KANBAN_OS[0]
            ordem_anterior = int(item.get("kanban_ordem") or 0)
            if status != status_anterior or ordem != ordem_anterior:
                alteracoes.append({
                    "id": equipamento_id,
                    "status": status,
                    "ordem": ordem,
                    "status_anterior": status_anterior,
                })
    return alteracoes


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
