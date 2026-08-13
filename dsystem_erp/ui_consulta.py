"""Componentes reutilizáveis de consulta e abertura por seleção."""

from __future__ import annotations


def tabela_selecionavel_id(st, dados, key: str, campo_id: str = "ID", titulo_id: str = "ID"):
    """Exibe uma grade selecionável e retorna o ID da linha clicada."""
    linhas = list(dados or [])
    if not linhas:
        return None
    evento = st.dataframe(
        linhas, width="stretch", hide_index=True, key=key,
        on_select="rerun", selection_mode="single-row",
    )
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
