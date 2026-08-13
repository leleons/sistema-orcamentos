"""Regras de validacao para configuracoes do sistema."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse


def somente_digitos_config(valor: str | None) -> str:
    return "".join(ch for ch in str(valor or "") if ch.isdigit())


def normalizar_whatsapp_config(valor: str | None) -> str:
    digitos = somente_digitos_config(valor)
    if len(digitos) in (10, 11):
        return f"55{digitos}"
    return digitos


def url_parece_valida(valor: str | None) -> bool:
    if not valor:
        return True
    parsed = urlparse(str(valor).strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def endpoint_nfse_nacional_rest(valor: str | None) -> bool:
    endpoint = str(valor or "").strip().lower().rstrip("/")
    return (
        ("adn." in endpoint and "nfse.gov.br" in endpoint)
        or ("sefin." in endpoint and "nfse.gov.br" in endpoint)
        or "/contribuintes" in endpoint
        or "/sefinnacional" in endpoint
    )


@dataclass(frozen=True)
class ValidacaoConfig:
    ok: bool
    mensagens: list[str]


def validar_nfse_config(config: dict[str, str]) -> ValidacaoConfig:
    mensagens: list[str] = []
    cnpj = somente_digitos_config(config.get("NFSE_CNPJ"))
    inscricao = somente_digitos_config(config.get("NFSE_INSCRICAO_MUNICIPAL"))
    endpoint = str(config.get("NFSE_ENDPOINT_SOAP") or "").strip()

    if cnpj and len(cnpj) != 14:
        mensagens.append("CNPJ deve ter 14 digitos.")
    if not inscricao:
        mensagens.append("Inscricao municipal e obrigatoria para NFS-e.")
    if endpoint and not url_parece_valida(endpoint):
        mensagens.append("Endpoint/API deve comecar com http:// ou https://.")

    return ValidacaoConfig(ok=not mensagens, mensagens=mensagens)
