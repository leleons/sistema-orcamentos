"""Cálculos fiscais e parcelamento de contas a receber."""

from __future__ import annotations

from calendar import monthrange
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


IMPOSTOS_PADRAO = ("IR", "PIS", "COFINS", "IPI", "IRPJ", "CSLL", "IRRF", "ICMS", "ISS")


def _decimal(valor) -> Decimal:
    try:
        return Decimal(str(valor or 0))
    except (InvalidOperation, ValueError):
        return Decimal("0")


def calcular_margem_lucro(valor_venda, valor_impostos, custo_unitario, quantidade=1) -> dict:
    """Calcula lucro após impostos e margem sobre a receita líquida."""
    bruto = max(Decimal("0"), _decimal(valor_venda))
    impostos = max(Decimal("0"), _decimal(valor_impostos))
    custo = max(Decimal("0"), _decimal(custo_unitario)) * max(Decimal("0"), _decimal(quantidade))
    liquido = max(Decimal("0"), bruto - impostos)
    lucro = liquido - custo
    margem = (lucro / liquido * Decimal("100")) if liquido else Decimal("0")
    q = Decimal("0.01")
    return {
        "receita_liquida": liquido.quantize(q, rounding=ROUND_HALF_UP),
        "custo_total": custo.quantize(q, rounding=ROUND_HALF_UP),
        "lucro_estimado": lucro.quantize(q, rounding=ROUND_HALF_UP),
        "margem_percentual": margem.quantize(q, rounding=ROUND_HALF_UP),
    }


def calcular_impostos(base: float, aliquotas: dict[str, float]) -> tuple[list[dict], float]:
    itens = []
    total = 0.0
    for nome, aliquota in aliquotas.items():
        percentual = max(0.0, float(aliquota or 0))
        valor = round(float(base or 0) * percentual / 100, 2)
        itens.append({"nome": nome, "aliquota": percentual, "valor": valor})
        total += valor
    return itens, round(total, 2)


def adicionar_meses(data_base: date, meses: int) -> date:
    indice = data_base.month - 1 + meses
    ano = data_base.year + indice // 12
    mes = indice % 12 + 1
    return date(ano, mes, min(data_base.day, monthrange(ano, mes)[1]))


def gerar_parcelas(valor_total: float, quantidade: int, primeiro_vencimento: date, meio: str) -> list[dict]:
    quantidade = max(1, int(quantidade or 1))
    total_centavos = round(float(valor_total or 0) * 100)
    base = total_centavos // quantidade
    resto = total_centavos - (base * quantidade)
    parcelas = []
    for indice in range(quantidade):
        centavos = base + (1 if indice < resto else 0)
        parcelas.append({
            "numero": indice + 1,
            "vencimento": adicionar_meses(primeiro_vencimento, indice).strftime("%d/%m/%Y"),
            "valor": centavos / 100,
            "meio": meio,
            "status": "Aberto",
        })
    return parcelas
