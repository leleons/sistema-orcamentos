from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, MutableMapping


@dataclass
class AppContext:
    """Contexto compartilhado entre o app principal e paginas extraidas."""

    values: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_globals(cls, source: Mapping[str, Any]) -> "AppContext":
        return cls(dict(source))

    def apply_to(self, target: MutableMapping[str, Any]) -> None:
        target.update(self.values)

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
        target.update(ctx.values)
    else:
        target.update(ctx)
