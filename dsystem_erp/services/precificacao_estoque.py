"""Regras de precificacao dos produtos mantidos no estoque."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def decimal_valor(valor) -> Decimal:
    if valor in (None, ""):
        return Decimal("0")
    texto = str(valor).strip().replace("R$", "").replace(" ", "")
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    try:
        return Decimal(texto)
    except (InvalidOperation, ValueError):
        return Decimal("0")


def calcular_preco_revenda(
    valor_compra,
    deslocamento=0,
    imposto_percentual=0,
    lucro_percentual=0,
    ajuste_percentual=0,
) -> Decimal:
    """Calcula preço final usando percentuais sucessivos sobre custo + deslocamento."""
    base = decimal_valor(valor_compra) + decimal_valor(deslocamento)
    com_imposto = base * (Decimal("1") + decimal_valor(imposto_percentual) / Decimal("100"))
    com_lucro = com_imposto * (Decimal("1") + decimal_valor(lucro_percentual) / Decimal("100"))
    final = com_lucro * (Decimal("1") + decimal_valor(ajuste_percentual) / Decimal("100"))
    return max(final, Decimal("0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def preco_revenda_produto(produto: dict, ajuste_percentual=0) -> Decimal:
    """Retorna o preço calculado; produtos antigos continuam usando valor_venda."""
    automatico = str(produto.get("preco_revenda_automatico") or "Não").casefold() in {"sim", "1", "true"}
    if automatico:
        ajuste = ajuste_percentual if produto.get("permitir_ajuste_preco") else 0
        return calcular_preco_revenda(
            produto.get("valor_custo"), produto.get("custo_deslocamento"),
            produto.get("imposto_percentual"), produto.get("lucro_percentual"), ajuste,
        )
    return decimal_valor(produto.get("valor_venda")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
