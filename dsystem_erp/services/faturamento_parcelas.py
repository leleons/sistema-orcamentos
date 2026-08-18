"""Parcelamento aplicado aos lançamentos do módulo de faturamento."""

from __future__ import annotations

import re
from datetime import date, datetime

from dsystem_erp.services.contas_receber import gerar_parcelas


def quantidade_parcelas_faturamento(valor) -> int:
    """Converte valores da tela, como ``Não`` e ``3x``, em quantidade."""
    texto = str(valor or "").strip().casefold()
    if not texto or texto in {"não", "nao", "à vista", "a vista", "1x"}:
        return 1
    encontrado = re.search(r"\d+", texto)
    return max(1, int(encontrado.group())) if encontrado else 1


def data_primeiro_vencimento(valor) -> date:
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    texto = str(valor or "").strip()
    for formato in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(texto[:10], formato).date()
        except ValueError:
            continue
    return date.today()


def gerar_parcelas_faturamento(faturamento: dict) -> list[dict]:
    """Gera o cronograma financeiro completo de um faturamento."""
    quantidade = quantidade_parcelas_faturamento(faturamento.get("parcelas"))
    meio = faturamento.get("forma_pag") or "Não informado"
    faturamento_id = int(faturamento.get("id") or 0)
    parcelas = gerar_parcelas(
        float(faturamento.get("valor_total") or 0),
        quantidade,
        data_primeiro_vencimento(faturamento.get("vencimento")),
        meio,
    )
    for parcela in parcelas:
        numero = int(parcela["numero"])
        parcela["quantidade"] = quantidade
        parcela["rotulo"] = f"{numero}/{quantidade}"
        parcela["documento"] = (
            f"FAT-{faturamento_id}"
            if quantidade == 1
            else f"FAT-{faturamento_id}-P{numero:02d}-{quantidade:02d}"
        )
    return parcelas
