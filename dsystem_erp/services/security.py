from __future__ import annotations


SENSITIVE_TERMS = ("senha", "password", "secret", "token", "cert", "pfx", "key")


def mascarar_segredo(valor, visiveis: int = 2) -> str:
    texto = "" if valor is None else str(valor)
    if not texto:
        return ""
    if len(texto) <= visiveis * 2:
        return "*" * len(texto)
    return f"{texto[:visiveis]}{'*' * max(4, len(texto) - (visiveis * 2))}{texto[-visiveis:]}"


def chave_parece_segredo(nome: str) -> bool:
    nome_lower = str(nome or "").lower()
    return any(term in nome_lower for term in SENSITIVE_TERMS)


def limpar_segredos_dict(dados: dict) -> dict:
    return {
        chave: mascarar_segredo(valor) if chave_parece_segredo(chave) else valor
        for chave, valor in dict(dados or {}).items()
    }

