"""Regras para interpretar códigos de localização na importação do estoque."""

from __future__ import annotations

import re


def separar_codigo_localizacao(valor) -> tuple[str, str, str]:
    """Separa ``02.04.07`` em fileira 1, fileira 2 e identificação.

    A identificação recebe tudo o que vier após as duas primeiras partes. Isso
    preserva códigos mais detalhados, como ``02.04.07.03`` -> ``07.03``.
    """
    if valor is None:
        return "", "", ""
    if isinstance(valor, float) and valor.is_integer():
        texto = str(int(valor))
    else:
        texto = str(valor).strip()
    partes = [parte.strip() for parte in re.split(r"\s*[.|/]\s*", texto) if parte.strip()]
    if len(partes) < 3:
        return "", "", ""
    return partes[0], partes[1], ".".join(partes[2:])


def codigo_localizacao_valido(valor) -> bool:
    """Informa se o código possui as três partes mínimas esperadas."""
    return all(separar_codigo_localizacao(valor))
