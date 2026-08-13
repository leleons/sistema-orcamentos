"""Configuracao central do ERP.

Ordem de leitura:
1. Variaveis de ambiente do sistema.
2. Arquivo .env na raiz do projeto.
3. st.secrets, quando o app esta rodando no Streamlit.
4. Valor padrao informado no codigo.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"


def _load_env_manual(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


@lru_cache(maxsize=1)
def load_environment() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv(ENV_FILE)
    except Exception:
        _load_env_manual(ENV_FILE)


def config_val(nome: str, padrao: Any = None) -> Any:
    load_environment()
    valor = os.getenv(nome)
    if valor not in (None, ""):
        return valor
    try:
        import streamlit as st

        valor = st.secrets.get(nome, None)
        if valor not in (None, ""):
            return str(valor)
    except Exception:
        pass
    return padrao


def config_int(nome: str, padrao: int) -> int:
    valor = config_val(nome, str(padrao))
    try:
        return int(valor)
    except (TypeError, ValueError):
        return padrao


@dataclass(frozen=True)
class DatabaseSettings:
    host: str
    port: int
    user: str
    password: str
    database: str


@dataclass(frozen=True)
class AppSettings:
    database: DatabaseSettings
    app_base_url: str
    whatsapp_oficial: str
    whatsapp_api_numero: str
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    smtp_from: str
    max_upload_banco_bytes: int
    dsystem_upload_max_bytes: int


def get_settings() -> AppSettings:
    whatsapp_oficial = "".join(ch for ch in str(config_val("WHATSAPP_OFICIAL", "31935023241")) if ch.isdigit())
    whatsapp_api = "".join(ch for ch in str(config_val("WHATSAPP_API_NUMERO", whatsapp_oficial)) if ch.isdigit())
    smtp_user = str(config_val("SMTP_USER", "") or "")
    return AppSettings(
        database=DatabaseSettings(
            host=str(config_val("MYSQL_HOST", "localhost") or "localhost"),
            port=config_int("MYSQL_PORT", 3306),
            user=str(config_val("MYSQL_USER", "root") or "root"),
            password=str(config_val("MYSQL_PASSWORD", "") or ""),
            database=str(config_val("MYSQL_DATABASE", "banco_dsystem") or "banco_dsystem"),
        ),
        app_base_url=str(config_val("APP_BASE_URL", "") or "").rstrip("/"),
        whatsapp_oficial=whatsapp_oficial,
        whatsapp_api_numero=whatsapp_api,
        smtp_host=str(config_val("SMTP_HOST", "") or ""),
        smtp_port=config_int("SMTP_PORT", 587),
        smtp_user=smtp_user,
        smtp_password=str(config_val("SMTP_PASSWORD", "") or ""),
        smtp_from=str(config_val("SMTP_FROM", smtp_user) or smtp_user),
        max_upload_banco_bytes=config_int("MAX_UPLOAD_BANCO_BYTES", 8 * 1024 * 1024),
        dsystem_upload_max_bytes=config_int("DSYSTEM_UPLOAD_MAX_BYTES", 7 * 1024 * 1024 * 1024),
    )
