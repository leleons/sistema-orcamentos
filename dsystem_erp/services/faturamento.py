"""Regras puras para faturamento."""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from typing import Iterable


def decimal_brl(valor) -> Decimal:
    if isinstance(valor, Decimal):
        return valor
    if isinstance(valor, (int, float)):
        return Decimal(str(valor))
    texto = str(valor or "0").strip().replace("R$", "").replace(" ", "")
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    try:
        return Decimal(texto)
    except (InvalidOperation, ValueError):
        return Decimal("0")


def total_itens_faturamento(itens: Iterable[dict]) -> Decimal:
    total = Decimal("0")
    for item in itens:
        quantidade = decimal_brl(item.get("quantidade", item.get("qtd", 1)))
        unitario = decimal_brl(item.get("valor_unitario", item.get("unitario", 0)))
        total += quantidade * unitario
    return total


def itens_faturamento_lista(valor) -> list[dict]:
    if isinstance(valor, list):
        itens = valor
    else:
        try:
            itens = json.loads(valor or "[]")
        except Exception:
            itens = []
    if not isinstance(itens, list):
        return []
    normalizados = []
    for item in itens:
        if not isinstance(item, dict):
            continue
        desc = str(item.get("desc") or item.get("descricao") or item.get("Descrição") or "").strip()
        try:
            qtd = int(float(item.get("qtd") or item.get("quantidade") or 0))
        except Exception:
            qtd = 0
        try:
            vunit = float(item.get("vunit") or item.get("valor_unitario") or 0)
        except Exception:
            vunit = 0.0
        try:
            vtotal = float(item.get("vtotal") or item.get("valor_total") or (vunit * qtd) or 0)
        except Exception:
            vtotal = vunit * qtd
        tipo_item = item.get("tipo_item") or item.get("tipo") or item.get("tipo_nota") or "Serviço"
        if tipo_item not in ["Produto", "Serviço"]:
            tipo_item = "Serviço"
        if desc or vtotal:
            normalizados.append({
                "desc": desc, "qtd": qtd, "vunit": vunit, "vtotal": vtotal, "tipo_item": tipo_item,
                "estoque_id": item.get("estoque_id"), "situacao_nota": item.get("situacao_nota") or "",
                "origem_item": item.get("origem_item") or "",
                "ajuste_preco_percentual": item.get("ajuste_preco_percentual") or 0,
            })
    return normalizados


def resumo_itens_faturamento(valor, limite=90) -> str:
    itens = itens_faturamento_lista(valor)
    texto = "; ".join([f"{i.get('qtd') or 0}x {i.get('desc') or ''}" for i in itens if i.get("desc")])
    if not texto:
        return "Sem itens"
    return texto[:limite] + ("..." if len(texto) > limite else "")
