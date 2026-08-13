"""Registro de erros tecnicos do ERP.

Esse log e separado do log de auditoria do Daniel. Ele serve para diagnostico:
falha de banco, backup, integracao fiscal, importacao, envio de e-mail etc.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = PROJECT_ROOT / "logs"
LOG_FILE = LOG_DIR / "tecnico.log"


def _logger() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("dsystem_erp.tecnico")
    if not logger.handlers:
        handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


def registrar_log_tecnico(
    nivel: str,
    origem: str,
    mensagem: str,
    detalhes: Any | None = None,
    cursor=None,
) -> None:
    nivel = (nivel or "INFO").upper()
    detalhes_json = json.dumps(detalhes or {}, ensure_ascii=False, default=str)
    _logger().log(getattr(logging, nivel, logging.INFO), "%s | %s | %s", origem, mensagem, detalhes_json)
    if cursor is None:
        return
    try:
        cursor.execute(
            """INSERT INTO logs_tecnicos (criado_em, nivel, origem, mensagem, detalhes)
               VALUES (%s, %s, %s, %s, %s)""",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), nivel, origem, mensagem, detalhes_json),
        )
    except Exception:
        pass
