from __future__ import annotations

import html
import textwrap
from collections.abc import Iterable, Mapping

import pandas as pd

from dsystem_erp.services.security import mascarar_segredo


COLUNAS_EMAIL = (
    ("id", "ID"),
    ("cliente_vinculado", "Empresa/Cliente"),
    ("funcionario", "Usuário/Funcionário"),
    ("email", "E-mail"),
    ("senha", "Senha"),
    ("aliases", "Aliases"),
    ("provedor", "Provedor"),
    ("config_entrada", "Entrada"),
    ("config_saida", "Saída"),
    ("capacidade", "Capacidade"),
    ("data_verificacao", "Data Verificação"),
    ("backup_realizado", "Backup"),
    ("data_backup", "Data Backup"),
)


def preparar_tabela_emails(rows: Iterable[Mapping], incluir_senhas: bool = False) -> list[dict]:
    dados = []
    for row in rows or []:
        item = dict(row)
        if not incluir_senhas:
            item["senha"] = mascarar_segredo(item.get("senha"))
        dados.append({titulo: item.get(campo, "") for campo, titulo in COLUNAS_EMAIL})
    return dados


def gerar_excel_emails(rows: Iterable[Mapping], titulo: str, incluir_senhas: bool = False) -> bytes:
    dados = preparar_tabela_emails(rows, incluir_senhas=incluir_senhas)
    tabela = pd.DataFrame(dados).to_html(index=False, escape=True)
    titulo_seguro = html.escape(str(titulo or "E-mails"))
    return (
        f"<html><head><meta charset='utf-8'></head><body>"
        f"<h2>{titulo_seguro}</h2>{tabela}</body></html>"
    ).encode("utf-8")


def _pdf_escape(texto: object) -> str:
    return str(texto).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def gerar_pdf_emails(rows: Iterable[Mapping], titulo: str, incluir_senhas: bool = False) -> bytes:
    dados = preparar_tabela_emails(rows, incluir_senhas=incluir_senhas)
    linhas = [str(titulo or "E-mails"), ""]
    for item in dados:
        linhas.extend(
            [
                f"Empresa/Cliente: {item['Empresa/Cliente']}",
                f"Usuário/Funcionário: {item['Usuário/Funcionário']}",
                f"E-mail: {item['E-mail']}",
                f"Senha: {item['Senha']}",
                f"Aliases: {item['Aliases']}",
                f"Provedor: {item['Provedor']}",
                f"Entrada: {item['Entrada']} | Saída: {item['Saída']}",
                f"Capacidade: {item['Capacidade']} | Backup: {item['Backup']} | Data Backup: {item['Data Backup']}",
                "-" * 95,
            ]
        )
    if not dados:
        linhas.append("Nenhum e-mail encontrado.")

    paginas: list[list[str]] = []
    pagina: list[str] = []
    for linha in linhas:
        for parte in textwrap.wrap(str(linha), width=95) or [""]:
            pagina.append(parte)
            if len(pagina) >= 45:
                paginas.append(pagina)
                pagina = []
    if pagina:
        paginas.append(pagina)

    objetos = ["<< /Type /Catalog /Pages 2 0 R >>", "", "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    ids_paginas = []
    for pagina in paginas:
        id_pagina = len(objetos) + 1
        id_conteudo = id_pagina + 1
        ids_paginas.append(id_pagina)
        comandos = ["BT", "/F1 9 Tf", "50 800 Td"]
        for indice, linha in enumerate(pagina):
            if indice:
                comandos.append("0 -15 Td")
            comandos.append(f"({_pdf_escape(linha)}) Tj")
        comandos.append("ET")
        stream = "\n".join(comandos).encode("cp1252", errors="replace")
        objetos.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {id_conteudo} 0 R >>"
        )
        objetos.append(f"<< /Length {len(stream)} >>\nstream\n{stream.decode('cp1252')}\nendstream")

    objetos[1] = f"<< /Type /Pages /Kids [{' '.join(f'{pid} 0 R' for pid in ids_paginas)}] /Count {len(ids_paginas)} >>"
    saida = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for indice, objeto in enumerate(objetos, start=1):
        offsets.append(len(saida))
        saida.extend(f"{indice} 0 obj\n{objeto}\nendobj\n".encode("cp1252", errors="replace"))
    xref = len(saida)
    saida.extend(f"xref\n0 {len(objetos) + 1}\n0000000000 65535 f \n".encode("ascii"))
    for offset in offsets[1:]:
        saida.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    saida.extend(
        f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode("ascii")
    )
    return bytes(saida)
