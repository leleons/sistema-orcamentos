"""Formatadores comuns do ERP."""

from __future__ import annotations


def somente_digitos(valor: str | None) -> str:
    return "".join(ch for ch in str(valor or "") if ch.isdigit())


def tamanho_arquivo_legivel(tamanho) -> str:
    try:
        tamanho = int(tamanho or 0)
    except Exception:
        tamanho = 0
    unidades = ["B", "KB", "MB", "GB"]
    valor = float(tamanho)
    for unidade in unidades:
        if valor < 1024 or unidade == unidades[-1]:
            return f"{valor:.1f} {unidade}" if unidade != "B" else f"{int(valor)} {unidade}"
        valor /= 1024
    return "0 B"


def formatar_moeda_br(valor) -> str:
    try:
        return f"R$ {float(valor or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "R$ 0,00"
