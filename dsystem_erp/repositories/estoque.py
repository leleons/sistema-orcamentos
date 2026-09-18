from __future__ import annotations

from typing import Callable


ConnectionFactory = Callable[[], object]


def _fetchall(conn_factory: ConnectionFactory, sql: str, params: tuple = ()) -> list[dict]:
    conn = conn_factory()
    cursor = conn.cursor()
    cursor.execute(sql, params)
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def listar_estoque(conn_factory: ConnectionFactory) -> list[dict]:
    # O ID é crescente e funciona como ordem de inclusão para a tabela atual.
    # Assim, os produtos cadastrados/importados por último aparecem primeiro.
    # A foto fica fora desta consulta porque é um LONGBLOB. Carregar centenas de
    # imagens em toda interação do Streamlit deixava Estoque, Orçamentos e
    # Faturamento desnecessariamente lentos.
    return _fetchall(
        conn_factory,
        """SELECT id, codigo, codigo_entrada, codigo_item, produto, modelo,
                  nome_generico, categoria, fileira, caixa, tem_fonte,
                  quantidade, estoque_minimo, valor_custo, valor_venda,
                  custo_deslocamento, imposto_percentual, lucro_percentual,
                  preco_revenda_automatico, permitir_ajuste_preco,
                  situacao_nota, fornecedor, data_compra, ultima_nota_entrada_id,
                  observacoes, foto_nome, foto_mime
           FROM estoque
           ORDER BY id DESC""",
    )


def buscar_foto_estoque(conn_factory: ConnectionFactory, produto_id: int) -> dict | None:
    """Carrega a imagem somente quando um produto específico precisar exibi-la."""
    conn = conn_factory()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT foto, foto_nome, foto_mime FROM estoque WHERE id=? LIMIT 1",
            (produto_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def listar_alertas_estoque_minimo(conn_factory: ConnectionFactory) -> list[dict]:
    return _fetchall(
        conn_factory,
        """SELECT id, codigo_entrada, produto, categoria, quantidade, estoque_minimo, fornecedor
           FROM estoque
           WHERE estoque_minimo > 0 AND quantidade <= estoque_minimo
           ORDER BY quantidade ASC, produto ASC""",
    )


def listar_alertas_emprestimos_atrasados(conn_factory: ConnectionFactory, hoje_iso: str) -> list[dict]:
    return _fetchall(
        conn_factory,
        """SELECT id, responsavel, cliente_nome, data_retirada, data_limite, status
           FROM estoque_emprestimos
           WHERE status='Em aberto' AND data_limite<=?
           ORDER BY data_limite ASC, id ASC""",
        (hoje_iso,),
    )
