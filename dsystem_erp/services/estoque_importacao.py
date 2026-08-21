"""Regras para interpretar códigos de localização na importação do estoque."""

from __future__ import annotations

import re


ESTADOS_POR_CODIGO = {
    "01": "1-01 Novo",
    "02": "1-02 Usado",
}

AREAS_POR_CODIGO = {
    "01": "2-01 Informática",
    "02": "2-02 CFTV",
    "03": "2-03 Alarme",
    "04": "2-04 Infraestrutura",
}


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
    """Informa se estado, área e identificação são reconhecidos."""
    return all(interpretar_codigo_localizacao(valor))


def interpretar_codigo_localizacao(valor) -> tuple[str, str, str]:
    """Converte as partes numéricas nos nomes usados pelo cadastro manual."""
    estado_codigo, area_codigo, identificacao = separar_codigo_localizacao(valor)
    return (
        ESTADOS_POR_CODIGO.get(estado_codigo, ""),
        AREAS_POR_CODIGO.get(area_codigo, ""),
        identificacao,
    )
