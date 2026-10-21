"""Regras para interpretar códigos de localização na importação do estoque."""

from __future__ import annotations

import re


ESTADOS_POR_CODIGO = {
    "01": "1-01 Novo",
    "02": "1-02 Usado",
    "03": "1-03 Equipamentos montados",
    "04": "1-04 Itens internos",
}

AREAS_POR_CODIGO = {
    "01": "2-01 Informática",
    "02": "2-02 CFTV",
    "03": "2-03 Alarme",
    "04": "2-04 Infraestrutura",
}


def normalizar_tem_fonte(valor) -> str:
    """Normaliza valores de planilha e formulário para ``Sim`` ou ``Não``."""
    texto = str(valor or "").strip().casefold()
    return "Sim" if texto in {"1", "s", "sim", "true", "yes", "com fonte"} else "Não"


def _codigo_da_fileira(valor, prefixo: str) -> str:
    """Extrai ``01`` de valores como ``1-01 Novo`` ou ``2-01 Informática``."""
    texto = str(valor or "").strip()
    correspondencia = re.match(rf"^{re.escape(prefixo)}\s*[-_.|/]?\s*(\d{{2}})(?:\D|$)", texto)
    if correspondencia:
        return correspondencia.group(1)
    if re.fullmatch(r"\d{1,2}", texto):
        return texto.zfill(2)
    return ""


def montar_codigo_localizacao(fileira1, fileira2, identificacao) -> str:
    """Monta o código visual ``01.04.10`` a partir das três partes do estoque."""
    estado = _codigo_da_fileira(fileira1, "1")
    area = _codigo_da_fileira(fileira2, "2")
    item = str(identificacao or "").strip().replace("|", ".").strip(". ")
    if not estado or not area or not item:
        return ""
    return ".".join((estado, area, item))


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
