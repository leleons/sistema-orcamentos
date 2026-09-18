"""Componentes reutilizáveis de consulta e abertura por seleção."""

from __future__ import annotations


def tabela_selecionavel_id(
    st, dados, key: str, campo_id: str = "ID", titulo_id: str = "ID",
    column_config=None,
):
    """Exibe uma grade selecionável e retorna o ID da linha clicada."""
    linhas = list(dados or [])
    if not linhas:
        return None
    opcoes_grade = dict(
        width="stretch", hide_index=True, key=key,
        on_select="rerun", selection_mode="single-row",
    )
    if column_config is not None:
        opcoes_grade["column_config"] = column_config
    evento = st.dataframe(linhas, **opcoes_grade)
    indices = list(getattr(getattr(evento, "selection", None), "rows", []) or [])
    if not indices:
        return None
    linha = linhas[indices[0]]
    if isinstance(linha, dict):
        return linha.get(campo_id, linha.get(titulo_id, linha.get("id")))
    try:
        return linha[campo_id]
    except Exception:
        return None


def tabela_clicavel_id(st, dados, key: str, campo_id: str = "ID", titulo_id: str = "ID"):
    """Exibe uma grade sem caixas e retorna o ID ao clicar em qualquer célula."""
    linhas = list(dados or [])
    if not linhas:
        return None
    evento = st.dataframe(
        linhas,
        width="stretch",
        hide_index=True,
        key=key,
        on_select="rerun",
        selection_mode="single-cell",
    )
    celulas = list(getattr(getattr(evento, "selection", None), "cells", []) or [])
    if not celulas:
        return None
    indice_linha, _ = celulas[0]
    if indice_linha < 0 or indice_linha >= len(linhas):
        return None
    linha = linhas[indice_linha]
    if isinstance(linha, dict):
        return linha.get(campo_id, linha.get(titulo_id, linha.get("id")))
    try:
        return linha[campo_id]
    except Exception:
        return None


def tabela_clicavel_registro(st, dados, key: str):
    """Exibe uma grade sem botões auxiliares e devolve a linha clicada inteira."""
    linhas = list(dados or [])
    if not linhas:
        return None
    evento = st.dataframe(
        linhas,
        width="stretch",
        hide_index=True,
        key=key,
        on_select="rerun",
        selection_mode="single-cell",
    )
    celulas = list(getattr(getattr(evento, "selection", None), "cells", []) or [])
    if not celulas:
        return None
    indice_linha, _ = celulas[0]
    if indice_linha < 0 or indice_linha >= len(linhas):
        return None
    linha = linhas[indice_linha]
    return dict(linha) if isinstance(linha, dict) else linha
