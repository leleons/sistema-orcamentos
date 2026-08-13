"""Controle simples de migrations do banco.

Por enquanto o ERP ainda cria varias tabelas dentro de iniciar_banco(). A partir
daqui, novas alteracoes devem entrar em arquivos SQL dentro da pasta migrations
e serem registradas nesta tabela.
"""

from __future__ import annotations

from pathlib import Path


TABELA_MIGRATIONS = "schema_migrations"


def normalizar_nome_coluna(nome: str) -> str:
    return "".join(ch for ch in nome if ch.isalnum() or ch == "_")


def garantir_tabela_migrations(cursor) -> None:
    cursor.execute(
        f"""CREATE TABLE IF NOT EXISTS {TABELA_MIGRATIONS} (
            id INT PRIMARY KEY AUTO_INCREMENT,
            nome VARCHAR(180) UNIQUE,
            descricao TEXT,
            aplicado_em DATETIME DEFAULT CURRENT_TIMESTAMP
        )"""
    )


def migration_aplicada(cursor, nome: str) -> bool:
    garantir_tabela_migrations(cursor)
    cursor.execute(f"SELECT id FROM {TABELA_MIGRATIONS} WHERE nome=%s", (nome,))
    return cursor.fetchone() is not None


def registrar_migration(cursor, nome: str, descricao: str = "") -> None:
    garantir_tabela_migrations(cursor)
    cursor.execute(
        f"INSERT IGNORE INTO {TABELA_MIGRATIONS} (nome, descricao) VALUES (%s, %s)",
        (nome, descricao),
    )


def coluna_existe(cursor, tabela: str, coluna: str) -> bool:
    coluna_segura = normalizar_nome_coluna(coluna)
    tabela_segura = normalizar_nome_coluna(tabela)
    if not tabela_segura or not coluna_segura:
        return False
    cursor.execute(f"SHOW COLUMNS FROM `{tabela_segura}` LIKE %s", (coluna_segura,))
    return cursor.fetchone() is not None


def garantir_coluna(cursor, tabela: str, coluna: str, definicao: str) -> bool:
    coluna_segura = normalizar_nome_coluna(coluna)
    tabela_segura = normalizar_nome_coluna(tabela)
    if not tabela_segura or not coluna_segura:
        raise ValueError("Nome de tabela ou coluna invalido.")
    if coluna_existe(cursor, tabela_segura, coluna_segura):
        return False
    try:
        cursor.execute(f"ALTER TABLE `{tabela_segura}` ADD COLUMN `{coluna_segura}` {definicao}")
        return True
    except Exception as ex:
        if getattr(ex, "errno", None) == 1060:
            return False
        raise


def aplicar_sql_file(cursor, caminho: str | Path, nome: str | None = None, descricao: str = "") -> bool:
    caminho_sql = Path(caminho)
    nome_migration = nome or caminho_sql.name
    if migration_aplicada(cursor, nome_migration):
        return False
    sql = caminho_sql.read_text(encoding="utf-8-sig")
    for comando in [parte.strip() for parte in sql.split(";") if parte.strip()]:
        try:
            cursor.execute(comando)
        except Exception as ex:
            # MySQL/MariaDB older versions do not support ADD COLUMN IF NOT EXISTS.
            # Migrations that add optional columns can be re-run safely by ignoring
            # duplicate-column errors.
            if getattr(ex, "errno", None) == 1060:
                continue
            raise
    registrar_migration(cursor, nome_migration, descricao)
    return True


def aplicar_migrations_pendentes(cursor, pasta: str | Path | None = None) -> list[str]:
    pasta_migrations = Path(pasta) if pasta else Path(__file__).resolve().parent.parent / "migrations"
    garantir_tabela_migrations(cursor)
    aplicadas: list[str] = []
    if not pasta_migrations.exists():
        return aplicadas
    for caminho_sql in sorted(pasta_migrations.glob("*.sql")):
        if aplicar_sql_file(cursor, caminho_sql):
            aplicadas.append(caminho_sql.name)
    return aplicadas
