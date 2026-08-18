"""Classificação fiscal de produtos conforme o documento da compra."""

from __future__ import annotations

from collections.abc import Mapping


COMPRADO_COM_NOTA = "Comprado com nota"
COMPRADO_SEM_NOTA = "Comprado sem nota"
SITUACOES_DOCUMENTO_COMPRA = (COMPRADO_COM_NOTA, COMPRADO_SEM_NOTA)


def normalizar_situacao_compra(valor: object) -> str:
    texto = str(valor or "").strip().casefold()
    if texto in {"comprado sem nota", "sem nota", "sem documento"}:
        return COMPRADO_SEM_NOTA
    return COMPRADO_COM_NOTA


def tipo_fiscal_produto_estoque(produto: Mapping | None) -> str:
    """Retorna como o produto deve sair fiscalmente na venda."""
    situacao = normalizar_situacao_compra((produto or {}).get("situacao_nota"))
    return "Serviço" if situacao == COMPRADO_SEM_NOTA else "Produto"


def aplicar_regra_fiscal_item(item: Mapping) -> dict:
    """Normaliza um item salvo sem perder seu vínculo com o estoque."""
    normalizado = dict(item)
    if normalizado.get("estoque_id"):
        situacao = normalizar_situacao_compra(normalizado.get("situacao_nota"))
        normalizado["situacao_nota"] = situacao
        normalizado["tipo_item"] = (
            "Serviço" if situacao == COMPRADO_SEM_NOTA else "Produto"
        )
    return normalizado
