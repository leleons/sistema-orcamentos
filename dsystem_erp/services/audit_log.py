"""Persistência e apresentação resumida dos registros de auditoria."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any


ACOES_PT = {"insert": "Entrada", "update": "Editar", "delete": "Excluir"}


def acao_pt(acao: str) -> str:
    return ACOES_PT.get(acao, acao)


def inserir_log_cursor(
    cursor,
    acao: str,
    tabela: str,
    registro_id: Any = "",
    cliente: str = "",
    detalhes: dict | None = None,
    *,
    usuario: str = "sistema",
    pagina: str = "",
    ip: str = "",
    criado_em: datetime | str | None = None,
    tabela_log: str = "logs_sistema",
) -> None:
    momento = criado_em or datetime.now()
    if isinstance(momento, datetime):
        momento = momento.strftime("%Y-%m-%d %H:%M:%S")
    detalhes_json = json.dumps(detalhes or {}, ensure_ascii=False, default=str)
    cursor.execute(
        f"""INSERT INTO {tabela_log}
           (criado_em, usuario, acao, tabela, registro_id, cliente, pagina, detalhes, ip)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (
            momento,
            usuario or "sistema",
            acao_pt(acao),
            tabela,
            str(registro_id or ""),
            cliente or "",
            pagina or "",
            detalhes_json,
            ip or "",
        ),
    )


def resumir_detalhes_log(valor: Any, limite: int = 180) -> str:
    if not valor:
        return ""
    try:
        dados = json.loads(valor)
        if isinstance(dados, dict):
            partes = []
            for chave in ("novo", "alterado", "excluido"):
                bloco = dados.get(chave)
                if isinstance(bloco, dict):
                    preenchidos = [
                        f"{campo}: {conteudo}"
                        for campo, conteudo in bloco.items()
                        if conteudo not in (None, "")
                    ]
                    if preenchidos:
                        partes.append(f"{chave}: " + "; ".join(preenchidos[:4]))
            texto = " | ".join(partes) or json.dumps(dados, ensure_ascii=False)
        else:
            texto = str(dados)
    except (TypeError, ValueError, json.JSONDecodeError):
        texto = str(valor)
    return texto[:limite] + ("..." if len(texto) > limite else "")
