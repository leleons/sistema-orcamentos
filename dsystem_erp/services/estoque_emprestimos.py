"""Regras e persistência dos empréstimos temporários do estoque."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from dsystem_erp.services.estoque_notas import registrar_movimentacao


STATUS_ITEM_ABERTO = "Emprestado"
STATUS_ITEM_DEVOLVIDO = "Devolvido ao estoque"
STATUS_ITEM_BAIXADO = "Baixa definitiva"


def garantir_tabelas_emprestimos(conn) -> None:
    """Cria as tabelas também durante hot reload, sem depender do reinício do app."""
    cursor = conn.cursor()
    cursor.execute(
        """CREATE TABLE IF NOT EXISTS estoque_emprestimos (
            id INT PRIMARY KEY AUTO_INCREMENT,
            responsavel VARCHAR(255) NOT NULL,
            cliente_id INTEGER,
            cliente_nome VARCHAR(255),
            data_retirada DATE NOT NULL,
            data_limite DATE NOT NULL,
            status VARCHAR(40) DEFAULT 'Em aberto',
            observacoes LONGTEXT,
            criado_por VARCHAR(255),
            criado_em VARCHAR(30),
            encerrado_por VARCHAR(255),
            encerrado_em VARCHAR(30),
            INDEX idx_emprestimos_status_limite (status, data_limite)
        )"""
    )
    cursor.execute(
        """CREATE TABLE IF NOT EXISTS estoque_emprestimo_itens (
            id INT PRIMARY KEY AUTO_INCREMENT,
            emprestimo_id INT NOT NULL,
            produto_id INT NOT NULL,
            codigo VARCHAR(255),
            produto VARCHAR(255),
            quantidade INT NOT NULL,
            status VARCHAR(40) DEFAULT 'Emprestado',
            resolvido_por VARCHAR(255),
            resolvido_em VARCHAR(30),
            observacao_resolucao LONGTEXT,
            INDEX idx_emprestimo_itens_emprestimo (emprestimo_id),
            INDEX idx_emprestimo_itens_status (status)
        )"""
    )
    conn.commit()


def data_limite_emprestimo(data_retirada: date, dias: int = 2) -> date:
    return data_retirada + timedelta(days=dias)


def emprestimo_atrasado(emprestimo: dict, hoje: date | None = None) -> bool:
    if (emprestimo.get("status") or "") != "Em aberto":
        return False
    hoje = hoje or date.today()
    valor = emprestimo.get("data_limite")
    if isinstance(valor, datetime):
        limite = valor.date()
    elif isinstance(valor, date):
        limite = valor
    else:
        texto = str(valor or "").strip()
        limite = None
        for formato in ("%Y-%m-%d", "%d/%m/%Y"):
            try:
                limite = datetime.strptime(texto, formato).date()
                break
            except ValueError:
                continue
    return bool(limite and hoje >= limite)


def criar_emprestimo(
    conn,
    *,
    itens: list[dict],
    responsavel: str,
    cliente_id=None,
    cliente_nome: str = "",
    data_retirada: date | None = None,
    observacoes: str = "",
    criado_por: str = "",
    criado_em: str = "",
) -> int:
    if not itens:
        raise ValueError("Selecione pelo menos um item para o empréstimo.")
    if not str(responsavel or "").strip():
        raise ValueError("Informe quem está levando os itens.")
    if not cliente_id or not str(cliente_nome or "").strip():
        raise ValueError("Selecione o cliente de destino. Nenhum item pode sair sem cliente vinculado.")
    retirada = data_retirada or date.today()
    limite = data_limite_emprestimo(retirada)
    cursor = conn.cursor()
    try:
        cursor.execute(
            """INSERT INTO estoque_emprestimos
               (responsavel, cliente_id, cliente_nome, data_retirada, data_limite,
                status, observacoes, criado_por, criado_em)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (responsavel.strip(), cliente_id, cliente_nome.strip(), retirada.isoformat(),
             limite.isoformat(), "Em aberto", observacoes.strip(), criado_por, criado_em),
        )
        emprestimo_id = int(cursor.lastrowid)
        for item in itens:
            produto_id = int(item.get("produto_id") or 0)
            quantidade = int(item.get("quantidade") or 0)
            if produto_id <= 0 or quantidade <= 0:
                raise ValueError("Produto ou quantidade inválida no empréstimo.")
            cursor.execute(
                "SELECT id, codigo_entrada, codigo, produto, modelo, nome_generico, quantidade FROM estoque WHERE id=? FOR UPDATE",
                (produto_id,),
            )
            produto = cursor.fetchone()
            if not produto:
                raise ValueError(f"Produto #{produto_id} não foi encontrado.")
            disponivel = int(produto.get("quantidade") or 0)
            if quantidade > disponivel:
                nome = produto.get("nome_generico") or produto.get("modelo") or produto.get("produto") or produto_id
                raise ValueError(f"Estoque insuficiente para {nome}. Disponível: {disponivel}.")
            cursor.execute(
                "UPDATE estoque SET quantidade=? WHERE id=?",
                (disponivel - quantidade, produto_id),
            )
            cursor.execute(
                """INSERT INTO estoque_emprestimo_itens
                   (emprestimo_id, produto_id, codigo, produto, quantidade, status)
                   VALUES (?,?,?,?,?,?)""",
                (emprestimo_id, produto_id,
                 produto.get("codigo_entrada") or produto.get("codigo") or "",
                 produto.get("nome_generico") or produto.get("modelo") or produto.get("produto") or "",
                 quantidade, STATUS_ITEM_ABERTO),
            )
            registrar_movimentacao(
                cursor, produto_id=produto_id, tipo="Saída por empréstimo",
                quantidade=quantidade, estoque_anterior=disponivel,
                estoque_atual=disponivel - quantidade, cliente_id=cliente_id,
                cliente_nome=cliente_nome, origem="Empréstimo", origem_id=emprestimo_id,
                observacoes=observacoes, criado_por=criado_por, criado_em=criado_em,
            )
        conn.commit()
        return emprestimo_id
    except Exception:
        conn.rollback()
        raise


def resolver_itens_emprestimo(
    conn,
    *,
    emprestimo_id: int,
    item_ids: list[int],
    devolver_ao_estoque: bool,
    resolvido_por: str = "",
    resolvido_em: str = "",
    observacao: str = "",
) -> str:
    if not item_ids:
        raise ValueError("Selecione pelo menos um item do empréstimo.")
    cursor = conn.cursor()
    novo_status = STATUS_ITEM_DEVOLVIDO if devolver_ao_estoque else STATUS_ITEM_BAIXADO
    try:
        for item_id in {int(valor) for valor in item_ids}:
            cursor.execute(
                """SELECT * FROM estoque_emprestimo_itens
                   WHERE id=? AND emprestimo_id=? FOR UPDATE""",
                (item_id, int(emprestimo_id)),
            )
            item = cursor.fetchone()
            if not item:
                raise ValueError(f"Item de empréstimo #{item_id} não foi encontrado.")
            if item.get("status") != STATUS_ITEM_ABERTO:
                raise ValueError(f"O item #{item_id} já foi encerrado.")
            if devolver_ao_estoque:
                cursor.execute(
                    "UPDATE estoque SET quantidade=quantidade+? WHERE id=?",
                    (int(item.get("quantidade") or 0), int(item.get("produto_id") or 0)),
                )
            cursor.execute(
                """UPDATE estoque_emprestimo_itens SET status=?, resolvido_por=?,
                   resolvido_em=?, observacao_resolucao=? WHERE id=?""",
                (novo_status, resolvido_por, resolvido_em, observacao.strip(), item_id),
            )
        cursor.execute(
            """SELECT COUNT(*) AS pendentes FROM estoque_emprestimo_itens
               WHERE emprestimo_id=? AND status=?""",
            (int(emprestimo_id), STATUS_ITEM_ABERTO),
        )
        pendentes = int((cursor.fetchone() or {}).get("pendentes") or 0)
        status_emprestimo = "Em aberto" if pendentes else "Concluído"
        cursor.execute(
            """UPDATE estoque_emprestimos SET status=?, encerrado_por=?, encerrado_em=?
               WHERE id=?""",
            (status_emprestimo, None if pendentes else resolvido_por,
             None if pendentes else resolvido_em, int(emprestimo_id)),
        )
        conn.commit()
        return status_emprestimo
    except Exception:
        conn.rollback()
        raise
