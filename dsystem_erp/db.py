"""Utilitarios de banco de dados.

O arquivo principal ainda mantem a camada CompatConnection/CompatCursor porque
ela tambem registra logs automaticos. Aqui ficam as partes puras de
configuracao para a conexao MySQL.
"""

from __future__ import annotations

from typing import Any

from .config import config_int, config_val


def mysql_connection_config(database: str | None = None, usar_database: bool = True) -> dict[str, Any]:
    config: dict[str, Any] = {
        "host": config_val("MYSQL_HOST", "localhost"),
        "port": config_int("MYSQL_PORT", 3306),
        "user": config_val("MYSQL_USER", "root"),
        "password": config_val("MYSQL_PASSWORD", ""),
        "charset": "utf8mb4",
        "use_unicode": True,
    }
    if usar_database and database:
        config["database"] = database
    return config


def adaptar_placeholders_mysql(sql: str) -> str:
    return sql.replace("?", "%s")
