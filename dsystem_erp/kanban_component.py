"""Quadro drag-and-drop local, sem o ciclo de renderização do React Sortables."""

import hashlib
import json
from pathlib import Path


def revisao_quadro(colunas: list[dict]) -> str:
    dados = json.dumps(colunas, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(dados).hexdigest()


def resultado_da_revisao(resultado, revisao: str):
    """Descarta eventos antigos após salvar, filtrar ou carregar outro quadro."""
    if not isinstance(resultado, dict) or resultado.get("revisao") != revisao:
        return None
    colunas = resultado.get("colunas")
    return colunas if isinstance(colunas, list) else None


def evento_da_revisao(resultado, revisao: str):
    """Valida movimentos e cliques emitidos pela revisão atual do quadro."""
    if not isinstance(resultado, dict) or resultado.get("revisao") != revisao:
        return None
    acao = resultado.get("acao") or "mover"
    evento_id = resultado.get("evento_id")
    if acao == "abrir" and isinstance(resultado.get("cartao"), str):
        return {"acao": "abrir", "cartao": resultado["cartao"], "evento_id": evento_id}
    if acao == "mover" and isinstance(resultado.get("colunas"), list):
        return {"acao": "mover", "colunas": resultado["colunas"], "evento_id": evento_id}
    return None


def quadro_interativo(
    colunas: list[dict], cores: dict, *, pode_editar: bool, key: str,
    retornar_evento: bool = False,
):
    import streamlit.components.v1 as components

    componente = components.declare_component(
        "dsystem_kanban", path=str(Path(__file__).parent / "components" / "kanban")
    )
    revisao = revisao_quadro(colunas)
    resultado = componente(
        colunas=colunas, cores=cores, revisao=revisao,
        pode_editar=pode_editar, key=key, default=None,
    )
    if retornar_evento:
        return evento_da_revisao(resultado, revisao)
    return resultado_da_revisao(resultado, revisao) if pode_editar else None
