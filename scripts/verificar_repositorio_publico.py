"""Falha quando arquivos privados ou segredos conhecidos aparecem no projeto."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


RAIZ = Path(__file__).resolve().parents[1]

DIRETORIOS_IGNORADOS = {
    ".git",
    ".idea",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    ".vscode",
    "__pycache__",
    "backups",
    "htmlcov",
    "logs",
    "output",
    "tmp",
    "venv",
}

NOMES_PROIBIDOS = {
    ".env",
    "secrets.toml",
    "mysql_dados_exportados.sql",
    "banco_dsystem.db",
}

EXTENSOES_PROIBIDAS = {
    ".bak",
    ".cer",
    ".crt",
    ".db",
    ".key",
    ".log",
    ".p12",
    ".pem",
    ".pfx",
    ".pyc",
    ".sqlite",
    ".sqlite3",
    ".tgz",
}

PADROES_SECRETOS = {
    "chave privada": re.compile(rb"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----"),
    "token AWS": re.compile(rb"\bAKIA[0-9A-Z]{16}\b"),
    "token GitHub": re.compile(rb"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
    "token Slack": re.compile(rb"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
    "URL com senha": re.compile(rb"[a-z][a-z0-9+.-]*://[^\s/:@]+:[^\s/@]+@", re.I),
    "IP antigo de producao": re.compile(rb"\b2\.25\.130\.92\b"),
}


def ignorado(caminho: Path) -> bool:
    partes = set(caminho.relative_to(RAIZ).parts)
    return bool(partes & DIRETORIOS_IGNORADOS)


def main() -> int:
    problemas: list[str] = []

    resultado = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=RAIZ,
        check=True,
        capture_output=True,
    )
    caminhos = [RAIZ / item.decode("utf-8") for item in resultado.stdout.split(b"\0") if item]

    for caminho in caminhos:
        if not caminho.is_file() or ignorado(caminho):
            continue

        relativo = caminho.relative_to(RAIZ).as_posix()
        nome = caminho.name.lower()
        sufixos = {sufixo.lower() for sufixo in caminho.suffixes}

        if nome in NOMES_PROIBIDOS or sufixos & EXTENSOES_PROIBIDAS:
            problemas.append(f"arquivo privado/gerado: {relativo}")
            continue

        try:
            conteudo = caminho.read_bytes()
        except OSError as erro:
            problemas.append(f"nao foi possivel ler {relativo}: {erro}")
            continue

        for descricao, padrao in PADROES_SECRETOS.items():
            if padrao.search(conteudo):
                problemas.append(f"{descricao}: {relativo}")

    if problemas:
        print("Repositorio nao esta pronto para publicacao:")
        for problema in sorted(set(problemas)):
            print(f"- {problema}")
        return 1

    print("Repositorio aprovado para publicacao: nenhum artefato privado conhecido encontrado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
