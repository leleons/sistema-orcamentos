"""Entrada de notas fiscais e rastreabilidade das movimentações de estoque."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from xml.etree import ElementTree


def _nome_local(elemento) -> str:
    return str(elemento.tag).rsplit("}", 1)[-1]


def _filho_texto(elemento, nome: str) -> str:
    if elemento is None:
        return ""
    for filho in list(elemento):
        if _nome_local(filho) == nome:
            return str(filho.text or "").strip()
    return ""


def _primeiro(elemento, nome: str):
    if elemento is None:
        return None
    return next((item for item in elemento.iter() if _nome_local(item) == nome), None)


def _decimal_xml(valor) -> float:
    try:
        return float(Decimal(str(valor or "0").replace(",", ".")))
    except (InvalidOperation, ValueError):
        return 0.0


def interpretar_xml_nfe(conteudo: bytes | str) -> dict:
    """Extrai cabeçalho e produtos de uma NF-e, ignorando a versão do namespace."""
    try:
        raiz = ElementTree.fromstring(conteudo)
    except (ElementTree.ParseError, TypeError, ValueError) as erro:
        raise ValueError(f"XML de NF-e inválido: {erro}") from erro

    inf_nfe = _primeiro(raiz, "infNFe")
    if inf_nfe is None:
        raise ValueError("O arquivo não possui a estrutura infNFe de uma NF-e.")
    emitente = _primeiro(inf_nfe, "emit")
    ide = _primeiro(inf_nfe, "ide")
    protocolo = _primeiro(raiz, "infProt")
    data_emissao = _filho_texto(ide, "dhEmi") or _filho_texto(ide, "dEmi")
    if data_emissao:
        data_emissao = data_emissao[:10]
    chave = _filho_texto(protocolo, "chNFe")
    if not chave:
        identificador = str(inf_nfe.attrib.get("Id") or "")
        chave = identificador[3:] if identificador.upper().startswith("NFE") else identificador

    itens = []
    for detalhe in (item for item in inf_nfe.iter() if _nome_local(item) == "det"):
        produto = _primeiro(detalhe, "prod")
        if produto is None:
            continue
        quantidade = _decimal_xml(_filho_texto(produto, "qCom"))
        valor_unitario = _decimal_xml(_filho_texto(produto, "vUnCom"))
        valor_total = _decimal_xml(_filho_texto(produto, "vProd"))
        if valor_unitario <= 0 and quantidade > 0:
            valor_unitario = round(valor_total / quantidade, 6)
        itens.append({
            "numero_item": str(detalhe.attrib.get("nItem") or len(itens) + 1),
            "codigo_fornecedor": _filho_texto(produto, "cProd"),
            "codigo_barras": _filho_texto(produto, "cEAN"),
            "descricao": _filho_texto(produto, "xProd"),
            "ncm": _filho_texto(produto, "NCM"),
            "cfop": _filho_texto(produto, "CFOP"),
            "unidade": _filho_texto(produto, "uCom"),
            "quantidade": quantidade,
            "valor_unitario": valor_unitario,
            "valor_total": valor_total,
        })
    if not itens:
        raise ValueError("Nenhum produto foi encontrado no XML da NF-e.")
    return {
        "fornecedor": _filho_texto(emitente, "xNome"),
        "fornecedor_documento": _filho_texto(emitente, "CNPJ") or _filho_texto(emitente, "CPF"),
        "numero_nota": _filho_texto(ide, "nNF"),
        "serie": _filho_texto(ide, "serie"),
        "chave_acesso": chave,
        "data_compra": data_emissao,
        "itens": itens,
    }


def validar_saida_com_cliente(cliente_id, cliente_nome: str, quantidade: int, disponivel: int) -> str | None:
    if not cliente_id or not str(cliente_nome or "").strip():
        return "Selecione o cliente que receberá o item. Toda saída precisa estar vinculada a um cliente."
    if int(quantidade or 0) <= 0:
        return "Informe uma quantidade maior que zero."
    if int(quantidade or 0) > int(disponivel or 0):
        return f"A saída não pode superar o estoque disponível ({int(disponivel or 0)})."
    return None


def preparar_entrada_rapida(
    *,
    produto_id: int,
    descricao: str,
    quantidade: int,
    fornecedor: str,
    data_compra,
    com_nota: bool,
    numero_documento: str = "",
    valor_unitario: float = 0,
) -> dict:
    """Valida e prepara uma entrada unitária para o mesmo histórico das notas."""
    if int(produto_id or 0) <= 0:
        raise ValueError("Selecione o produto que receberá a entrada.")
    if int(quantidade or 0) <= 0:
        raise ValueError("Informe uma quantidade maior que zero.")
    fornecedor = str(fornecedor or "").strip()
    if not fornecedor:
        raise ValueError("Informe o fornecedor da compra.")
    numero_documento = str(numero_documento or "").strip()
    if com_nota and not numero_documento:
        raise ValueError("Informe o número da nota fiscal.")
    if not numero_documento:
        instante = datetime.now().strftime("%Y%m%d%H%M%S%f")
        numero_documento = f"SEM-NOTA-{produto_id}-{instante}"
    valor_unitario = float(valor_unitario or 0)
    return {
        "fornecedor": fornecedor,
        "numero_nota": numero_documento,
        "data_compra": _data_iso(data_compra),
        "origem": "Entrada rápida com nota" if com_nota else "Entrada rápida sem nota",
        "itens": [{
            "produto_id": int(produto_id), "numero_item": 1,
            "descricao": str(descricao or "Produto").strip() or "Produto",
            "unidade": "UN", "quantidade": int(quantidade),
            "valor_unitario": valor_unitario,
            "valor_total": round(int(quantidade) * valor_unitario, 2),
        }],
    }


def registrar_movimentacao(
    cursor,
    *,
    produto_id: int,
    tipo: str,
    quantidade: float,
    estoque_anterior: float,
    estoque_atual: float,
    cliente_id=None,
    cliente_nome: str = "",
    fornecedor: str = "",
    nota_entrada_id=None,
    origem: str = "",
    origem_id=None,
    observacoes: str = "",
    criado_por: str = "",
    criado_em: str = "",
) -> None:
    cursor.execute(
        """INSERT INTO estoque_movimentacoes
           (produto_id, tipo, quantidade, estoque_anterior, estoque_atual,
            cliente_id, cliente_nome, fornecedor, nota_entrada_id, origem,
            origem_id, observacoes, criado_por, criado_em)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (produto_id, tipo, quantidade, estoque_anterior, estoque_atual,
         cliente_id, str(cliente_nome or "").strip(), str(fornecedor or "").strip(),
         nota_entrada_id, origem, origem_id, str(observacoes or "").strip(),
         criado_por, criado_em),
    )


def _data_iso(valor) -> str:
    if isinstance(valor, datetime):
        return valor.date().isoformat()
    if isinstance(valor, date):
        return valor.isoformat()
    texto = str(valor or "").strip()
    if not texto:
        return date.today().isoformat()
    for formato in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(texto[:10], formato).date().isoformat()
        except ValueError:
            continue
    raise ValueError("Data de compra inválida.")


def registrar_entrada_nota(
    conn,
    *,
    fornecedor: str,
    fornecedor_documento: str,
    numero_nota: str,
    serie: str,
    chave_acesso: str,
    data_compra,
    itens: list[dict],
    origem: str,
    observacoes: str,
    criado_por: str,
    criado_em: str,
) -> int:
    fornecedor = str(fornecedor or "").strip()
    numero_nota = str(numero_nota or "").strip()
    if not fornecedor:
        raise ValueError("Informe o fornecedor da nota.")
    if not numero_nota:
        raise ValueError("Informe o número da nota.")
    itens_validos = [item for item in itens or [] if int(item.get("produto_id") or 0) > 0]
    if not itens_validos:
        raise ValueError("Vincule pelo menos um item da nota a um produto do estoque.")
    data_compra_iso = _data_iso(data_compra)
    cursor = conn.cursor()
    try:
        cursor.execute(
            """SELECT id FROM estoque_notas_entrada
               WHERE fornecedor=? AND numero_nota=? AND COALESCE(serie, '')=?
               LIMIT 1""",
            (fornecedor, numero_nota, str(serie or "").strip()),
        )
        nota_existente = cursor.fetchone()
        if nota_existente:
            raise ValueError(
                f"A nota {numero_nota} deste fornecedor já foi lançada no estoque."
            )
        cursor.execute(
            """INSERT INTO estoque_notas_entrada
               (fornecedor, fornecedor_documento, numero_nota, serie, chave_acesso,
                data_compra, origem, observacoes, criado_por, criado_em)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (fornecedor, str(fornecedor_documento or "").strip(), numero_nota,
             str(serie or "").strip(), str(chave_acesso or "").strip() or None,
             data_compra_iso, origem, str(observacoes or "").strip(), criado_por, criado_em),
        )
        nota_id = int(cursor.lastrowid)
        for item in itens_validos:
            produto_id = int(item.get("produto_id") or 0)
            quantidade_informada = float(item.get("quantidade") or 0)
            if quantidade_informada <= 0:
                raise ValueError("Todos os itens vinculados precisam ter quantidade maior que zero.")
            if not quantidade_informada.is_integer():
                raise ValueError(
                    "A quantidade precisa ser inteira porque o estoque atual é controlado por unidades."
                )
            quantidade = int(quantidade_informada)
            cursor.execute(
                "SELECT id, quantidade FROM estoque WHERE id=? FOR UPDATE", (produto_id,)
            )
            produto = cursor.fetchone()
            if not produto:
                raise ValueError(f"Produto #{produto_id} não encontrado no estoque.")
            estoque_anterior = float(produto.get("quantidade") or 0)
            estoque_atual = estoque_anterior + quantidade
            valor_unitario = float(item.get("valor_unitario") or 0)
            valor_total = float(item.get("valor_total") or quantidade * valor_unitario)
            cursor.execute(
                """INSERT INTO estoque_nota_entrada_itens
                   (nota_entrada_id, produto_id, numero_item, codigo_fornecedor,
                    codigo_barras, descricao, ncm, cfop, unidade, quantidade,
                    valor_unitario, valor_total)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (nota_id, produto_id, item.get("numero_item"), item.get("codigo_fornecedor"),
                 item.get("codigo_barras"), item.get("descricao"), item.get("ncm"),
                 item.get("cfop"), item.get("unidade"), quantidade,
                 valor_unitario, valor_total),
            )
            cursor.execute(
                """UPDATE estoque SET quantidade=?, fornecedor=?, data_compra=?,
                   valor_custo=?, ultima_nota_entrada_id=? WHERE id=?""",
                (estoque_atual, fornecedor, data_compra_iso, valor_unitario,
                 nota_id, produto_id),
            )
            registrar_movimentacao(
                cursor, produto_id=produto_id,
                tipo="Entrada sem nota" if "sem nota" in str(origem).casefold() else "Entrada por nota",
                quantidade=quantidade, estoque_anterior=estoque_anterior,
                estoque_atual=estoque_atual, fornecedor=fornecedor,
                nota_entrada_id=nota_id, origem=origem, origem_id=nota_id,
                observacoes=f"NF {numero_nota}", criado_por=criado_por,
                criado_em=criado_em,
            )
        conn.commit()
        return nota_id
    except Exception:
        conn.rollback()
        raise
