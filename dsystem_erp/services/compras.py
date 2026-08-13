"""Regras de comparação de cotações de compras."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation


MEIOS_COMPRA = ("Internet", "Loja física", "WhatsApp")


def valor_decimal(valor) -> Decimal:
    texto = str(valor or "0").strip().replace("R$", "").replace(" ", "")
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    try:
        return Decimal(texto)
    except (InvalidOperation, ValueError):
        return Decimal("0")


def total_cotacao(valor_unitario, quantidade) -> Decimal:
    return (valor_decimal(valor_unitario) * Decimal(str(int(quantidade or 0)))).quantize(Decimal("0.01"))


def id_melhor_cotacao(cotacoes: list[dict]):
    validas = [c for c in cotacoes if valor_decimal(c.get("valor_item")) > 0]
    if not validas:
        return None
    return min(validas, key=lambda c: (valor_decimal(c.get("valor_item")), int(c.get("id") or 0))).get("id")
