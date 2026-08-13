"""Helpers de diagnostico do sistema."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class HealthCheck:
    area: str
    status: str
    mensagem: str
    detalhe: str = ""

    @property
    def ok(self) -> bool:
        return self.status.upper() == "OK"


def status_path(path: str | Path, area: str, mensagem_ok: str, mensagem_erro: str) -> HealthCheck:
    caminho = Path(path)
    if caminho.exists():
        return HealthCheck(area, "OK", mensagem_ok, str(caminho))
    return HealthCheck(area, "ERRO", mensagem_erro, str(caminho))


def health_to_row(check: HealthCheck) -> dict:
    return {
        "Área": check.area,
        "Status": check.status,
        "Mensagem": check.mensagem,
        "Detalhe": check.detalhe,
    }


def resumo_checks(checks: list[HealthCheck]) -> dict[str, int]:
    total = len(checks)
    ok = sum(1 for check in checks if check.status.upper() == "OK")
    erros = sum(1 for check in checks if check.status.upper() == "ERRO")
    avisos = total - ok - erros
    return {"total": total, "ok": ok, "avisos": avisos, "erros": erros}
