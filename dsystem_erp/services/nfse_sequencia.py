from __future__ import annotations

from xml.etree import ElementTree


def _nome_local(tag) -> str:
    return str(tag or "").rsplit("}", 1)[-1]


def maior_numero_fiscal_nos_xmls(xmls, tipo: str = "dps", serie=None) -> int:
    """Recupera a maior numeração já usada nos XMLs, inclusive antes da sequência local."""
    maior = 0
    tag_numero = "nDPS" if tipo == "dps" else "NumeroLote"
    serie_esperada = str(serie or "").strip()
    for xml in xmls or []:
        texto = xml.get("xml_envio") if isinstance(xml, dict) else (xml[0] if isinstance(xml, (tuple, list)) else xml)
        if not texto:
            continue
        try:
            conteudo = texto if isinstance(texto, bytes) else str(texto).encode("utf-8")
            raiz = ElementTree.fromstring(conteudo)
        except (ElementTree.ParseError, ValueError):
            continue
        if tipo == "dps" and serie_esperada:
            serie_xml = next((str(no.text or "").strip() for no in raiz.iter() if _nome_local(no.tag) == "serie"), "")
            if serie_xml and serie_xml != serie_esperada:
                continue
        for no in raiz.iter():
            if _nome_local(no.tag) != tag_numero:
                continue
            try:
                maior = max(maior, int(str(no.text or "0").strip()))
            except ValueError:
                pass
    return maior


def _cursor_dicionario(conexao):
    try:
        return conexao.cursor(dictionary=True)
    except TypeError:
        return conexao.cursor()


def _valor_linha(linha, chave="ultimo_numero"):
    if isinstance(linha, dict):
        return linha.get(chave)
    if isinstance(linha, (tuple, list)) and linha:
        return linha[0]
    return None


def proximo_numero_nfse(
    conectar_banco,
    *,
    ambiente: str,
    cnpj: str,
    serie,
    tipo: str = "dps",
    reservar: bool = False,
) -> int:
    """Consulta ou reserva atomicamente a próxima DPS/lote por ambiente, emitente e série."""
    if tipo not in {"dps", "lote"}:
        raise ValueError("Tipo de sequência fiscal inválido.")
    chave = f"{tipo}:{ambiente}:{cnpj}:{serie}"
    conexao = conectar_banco()
    cursor = _cursor_dicionario(conexao)
    try:
        cursor.execute(
            """CREATE TABLE IF NOT EXISTS nfse_sequencias (
                   chave VARCHAR(255) PRIMARY KEY,
                   ultimo_numero BIGINT NOT NULL DEFAULT 0,
                   atualizado_em DATETIME DEFAULT CURRENT_TIMESTAMP
               )"""
        )
        xmls = []
        try:
            cursor.execute(
                "SELECT xml_envio FROM nfse_envios WHERE ambiente=? AND xml_envio IS NOT NULL",
                (ambiente,),
            )
            xmls = cursor.fetchall() or []
        except Exception:
            xmls = []
        semente = maior_numero_fiscal_nos_xmls(xmls, tipo=tipo, serie=serie)
        cursor.execute(
            """INSERT INTO nfse_sequencias (chave, ultimo_numero, atualizado_em)
               VALUES (?, ?, CURRENT_TIMESTAMP)
               ON DUPLICATE KEY UPDATE
                   ultimo_numero=GREATEST(ultimo_numero, VALUES(ultimo_numero))""",
            (chave, semente),
        )
        cursor.execute("SELECT ultimo_numero FROM nfse_sequencias WHERE chave=? FOR UPDATE", (chave,))
        atual = int(_valor_linha(cursor.fetchone()) or 0)
        proximo = atual + 1
        if reservar:
            cursor.execute(
                "UPDATE nfse_sequencias SET ultimo_numero=?, atualizado_em=CURRENT_TIMESTAMP WHERE chave=?",
                (proximo, chave),
            )
        conexao.commit()
        return proximo
    except Exception:
        conexao.rollback()
        raise
    finally:
        conexao.close()
