from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, MutableMapping


def _aplicar_valores_sem_substituir_funcoes(
    valores: Mapping[str, Any],
    destino: MutableMapping[str, Any],
) -> None:
    """Injeta dependências sem trocar funções definidas pelo módulo de destino.

    Em recarregamentos do Streamlit, o contexto do arquivo principal contém
    wrappers com os mesmos nomes das funções das páginas extraídas. Substituir
    essas funções transforma os aliases importados em wrappers incompatíveis no
    próximo rerun.
    """
    modulo_destino = destino.get("__name__")
    for nome, valor in valores.items():
        if nome.startswith("__"):
            continue
        existente = destino.get(nome)
        funcao_local = (
            callable(existente)
            and callable(valor)
            and modulo_destino
            and getattr(existente, "__module__", None) == modulo_destino
        )
        if funcao_local:
            continue
        destino[nome] = valor


@dataclass
class AppContext:
    """Contexto compartilhado entre o app principal e paginas extraidas."""

    values: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_globals(cls, source: Mapping[str, Any]) -> "AppContext":
        return cls(dict(source))

    def apply_to(self, target: MutableMapping[str, Any]) -> None:
        _aplicar_valores_sem_substituir_funcoes(self.values, target)

    def get(self, name: str, default: Any = None) -> Any:
        return self.values.get(name, default)

    def __contains__(self, name: str) -> bool:
        return name in self.values

    def __getitem__(self, name: str) -> Any:
        return self.values[name]

    def __iter__(self):
        return iter(self.values)

    def items(self):
        return self.values.items()


def criar_app_context(source: Mapping[str, Any]) -> AppContext:
    return AppContext.from_globals(source)


def aplicar_contexto_pagina(ctx: AppContext | Mapping[str, Any], target: MutableMapping[str, Any]) -> None:
    if isinstance(ctx, AppContext) or hasattr(ctx, "apply_to"):
        ctx.apply_to(target)
    elif hasattr(ctx, "values") and isinstance(ctx.values, dict):
        _aplicar_valores_sem_substituir_funcoes(ctx.values, target)
    else:
        _aplicar_valores_sem_substituir_funcoes(ctx, target)
