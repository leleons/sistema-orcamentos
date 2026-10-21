from __future__ import annotations

from functools import lru_cache
import re
import unicodedata

from dsystem_erp.app_context import aplicar_contexto_pagina
from dsystem_erp.migrations import garantir_coluna
from dsystem_erp.repositories.estoque import buscar_foto_estoque
from dsystem_erp.services.estoque_fiscal import (
    COMPRADO_COM_NOTA,
    SITUACOES_DOCUMENTO_COMPRA,
    normalizar_situacao_compra,
)
from dsystem_erp.services.precificacao_estoque import calcular_preco_revenda, decimal_valor
from dsystem_erp.services.estoque_importacao import (
    ESTADOS_POR_CODIGO,
    codigo_localizacao_valido,
    interpretar_codigo_localizacao,
    normalizar_tem_fonte,
)
from dsystem_erp.services.estoque_notas import (
    cancelar_saida_manual,
    interpretar_xml_nfe,
    registrar_entrada_nota,
    registrar_movimentacao,
    preparar_entrada_rapida,
    validar_saida_com_cliente,
)
from dsystem_erp.services.estoque_emprestimos import (
    STATUS_ITEM_ABERTO,
    criar_emprestimo,
    emprestimo_atrasado,
    garantir_tabelas_emprestimos,
    resolver_itens_emprestimo,
)
from dsystem_erp.ui_consulta import tabela_clicavel_id, tabela_selecionavel_id
from dsystem_erp.services.estoque_qr import gerar_qr_produto


def sincronizar_selecao_produto_estoque(estado_sessao, produto_id):
    """Propaga a seleção da grade para movimentação, edição e exclusão."""
    try:
        produto_id = int(produto_id)
    except (TypeError, ValueError):
        return None
    if produto_id <= 0:
        return None
    estado_sessao["estoque_produto_selecionado"] = produto_id
    estado_sessao["estoque_produto_movimentacao_id"] = produto_id
    estado_sessao["estoque_id_edicao"] = produto_id
    estado_sessao["estoque_id_exclusao"] = produto_id
    return produto_id


def texto_pesquisa_produto_estoque(produto, codigo_completo=""):
    """Reúne os campos pesquisáveis do produto em um único texto normalizado."""
    campos = (
        "codigo", "codigo_entrada", "codigo_item", "produto", "modelo", "nome_generico",
        "categoria", "caixa", "tem_fonte", "fornecedor", "observacoes",
    )
    valores = [str(produto.get(campo) or "") for campo in campos]
    valores.append(str(codigo_completo or ""))
    return " ".join(valores).casefold()


def codigo_item_estoque(produto):
    """Retorna o ID comercial usado como terceira parte do código completo."""
    valor = produto.get("codigo_item")
    if str(valor or "").strip().isdigit():
        return int(valor)
    ultima_parte = str(produto.get("codigo_entrada") or "").rsplit(".", 1)[-1].strip()
    if ultima_parte.isdigit():
        return int(ultima_parte)
    legado = str(produto.get("produto") or "").strip()
    if legado.isdigit():
        return int(legado)
    return int(produto.get("id") or 0)


def nome_produto_estoque(produto):
    """Escolhe uma descrição humana sem confundir o ID comercial com o nome."""
    return (
        produto.get("nome_generico")
        or produto.get("modelo")
        or produto.get("produto")
        or produto.get("codigo_entrada")
        or "Produto"
    )


def _normalizar_nome_produto(valor) -> str:
    texto = unicodedata.normalize("NFKD", str(valor or ""))
    texto = "".join(caractere for caractere in texto if not unicodedata.combining(caractere))
    return " ".join(re.findall(r"[a-z0-9]+", texto.casefold()))


def _descricao_compativel_nota(descricao: str, nome: str) -> bool:
    """Aceita somente nomes completos ou trechos compostos, evitando coincidências como 'mini'."""
    descricao_normalizada = _normalizar_nome_produto(descricao)
    nome_normalizado = _normalizar_nome_produto(nome)
    if not descricao_normalizada or not nome_normalizado:
        return False
    if descricao_normalizada == nome_normalizado:
        return True
    tokens_nome = nome_normalizado.split()
    if len(tokens_nome) < 2 or len(nome_normalizado) < 6:
        return False
    return nome_normalizado in descricao_normalizada or descricao_normalizada in nome_normalizado


def sugerir_produto_nota(item_nota, produtos) -> int | None:
    """Relaciona automaticamente apenas códigos exatos ou descrições confiáveis."""
    codigo = str(item_nota.get("codigo_fornecedor") or "").strip().casefold()
    codigo_barras = str(item_nota.get("codigo_barras") or "").strip().casefold()
    descricao = str(item_nota.get("descricao") or "").strip().casefold()
    for produto in produtos or []:
        codigos = {
            str(produto.get("codigo_entrada") or "").strip().casefold(),
            str(produto.get("codigo_item") or "").strip().casefold(),
            str(produto.get("codigo") or "").strip().casefold(),
        }
        if codigo and codigo in codigos:
            return int(produto.get("id") or 0) or None
        barras_produto = str(produto.get("codigo_barras") or "").strip().casefold()
        if codigo_barras and codigo_barras not in {"sem gtin", "semgtin"} and codigo_barras == barras_produto:
            return int(produto.get("id") or 0) or None
    for produto in produtos or []:
        nomes = (
            str(produto.get("produto") or "").strip().casefold(),
            str(produto.get("modelo") or "").strip().casefold(),
            str(produto.get("nome_generico") or "").strip().casefold(),
        )
        if descricao and any(_descricao_compativel_nota(descricao, nome) for nome in nomes):
            return int(produto.get("id") or 0) or None
    return None


def renderizar_entrada_notas(estoque_data) -> None:
    st.subheader("Entrada de Nota")
    st.caption(
        "Toda entrada registra a data da compra, o fornecedor, a nota e os itens. "
        "A quantidade do estoque é atualizada somente depois da confirmação."
    )
    modo_nota = st.radio(
        "Forma de entrada:", ["Manual", "Importar XML da NF-e"], horizontal=True,
        key="estoque_nota_modo",
    )
    dados_xml = None
    arquivo_xml = None
    if modo_nota == "Importar XML da NF-e":
        arquivo_xml = st.file_uploader(
            "Arquivo XML da NF-e:", type=["xml"], key="estoque_nota_xml"
        )
        if arquivo_xml:
            try:
                dados_xml = interpretar_xml_nfe(arquivo_xml.getvalue())
            except ValueError as erro_xml:
                st.error(str(erro_xml))
            else:
                st.success(
                    f"NF-e {dados_xml.get('numero_nota') or 'sem número'} reconhecida com "
                    f"{len(dados_xml.get('itens') or [])} item(ns)."
                )

    clientes_fornecedores = [
        item for item in buscar_clientes()
        if str(item.get("tipo") or "").casefold() in {"fornecedor", "ambos"}
    ]
    fornecedores_por_id = {int(item["id"]): item for item in clientes_fornecedores}
    opcoes_fornecedor = [0] + list(fornecedores_por_id)
    fornecedor_xml = str((dados_xml or {}).get("fornecedor") or "").strip()
    identificador_nota = str(
        (dados_xml or {}).get("chave_acesso") or (dados_xml or {}).get("numero_nota") or "manual"
    ).strip()[-16:]
    sufixo_nota = f"{modo_nota}_{identificador_nota}"
    fornecedor_id_sugerido = next(
        (identificador for identificador, item in fornecedores_por_id.items()
         if fornecedor_xml and fornecedor_xml.casefold() in str(item.get("nome") or "").casefold()),
        0,
    )
    nota_fornecedor_id = st.selectbox(
        "Fornecedor cadastrado:", opcoes_fornecedor,
        index=opcoes_fornecedor.index(fornecedor_id_sugerido),
        format_func=lambda valor: (
            "-- Informar manualmente --" if valor == 0
            else fornecedores_por_id[valor].get("nome") or f"Fornecedor #{valor}"
        ),
        key=f"estoque_nota_fornecedor_{sufixo_nota}",
    )
    fornecedor_cadastrado = fornecedores_por_id.get(int(nota_fornecedor_id or 0))
    cab1, cab2, cab3 = st.columns(3)
    fornecedor_nota = cab1.text_input(
        "Fornecedor da nota:",
        value=(fornecedor_cadastrado or {}).get("nome") or fornecedor_xml,
        disabled=bool(fornecedor_cadastrado),
        key=f"estoque_nota_fornecedor_nome_{sufixo_nota}_{nota_fornecedor_id}",
    )
    documento_fornecedor = cab2.text_input(
        "CPF/CNPJ do fornecedor:",
        value=(fornecedor_cadastrado or {}).get("cnpj") or str((dados_xml or {}).get("fornecedor_documento") or ""),
        disabled=bool(fornecedor_cadastrado),
        key=f"estoque_nota_fornecedor_doc_{sufixo_nota}_{nota_fornecedor_id}",
    )
    numero_nota = cab3.text_input(
        "Número da nota:", value=str((dados_xml or {}).get("numero_nota") or ""),
        key=f"estoque_nota_numero_{sufixo_nota}",
    )
    cab4, cab5, cab6 = st.columns(3)
    serie_nota = cab4.text_input(
        "Série:", value=str((dados_xml or {}).get("serie") or ""),
        key=f"estoque_nota_serie_{sufixo_nota}",
    )
    chave_nota = cab5.text_input(
        "Chave de acesso:", value=str((dados_xml or {}).get("chave_acesso") or ""),
        key=f"estoque_nota_chave_{sufixo_nota}",
    )
    data_xml = parse_data_flex((dados_xml or {}).get("data_compra")) or date.today()
    data_compra_nota = cab6.date_input(
        "Data da compra:", value=data_xml, key=f"estoque_nota_data_{sufixo_nota}"
    )

    produtos_por_id = {int(item["id"]): item for item in estoque_data}
    opcoes_produtos = [0] + list(produtos_por_id)
    itens_para_entrada = []
    if dados_xml:
        st.markdown("#### Itens encontrados no XML")
        for indice, item_xml in enumerate(dados_xml.get("itens") or [], 1):
            sugerido = sugerir_produto_nota(item_xml, estoque_data) or 0
            item1, item2, item3 = st.columns([3, 1, 1])
            produto_id = item1.selectbox(
                f"{indice}. {item_xml.get('descricao') or 'Produto'}:", opcoes_produtos,
                index=opcoes_produtos.index(sugerido) if sugerido in opcoes_produtos else 0,
                format_func=lambda valor: (
                    "-- Não vinculado --" if valor == 0
                    else f"{codigo_item_estoque(produtos_por_id[valor])} - {nome_produto_estoque(produtos_por_id[valor])}"
                ),
                key=f"estoque_nota_xml_produto_{sufixo_nota}_{indice}_{item_xml.get('codigo_fornecedor')}",
            )
            quantidade_item = item2.number_input(
                "Quantidade:", min_value=0.0, value=float(item_xml.get("quantidade") or 0),
                step=1.0, format="%.3f", key=f"estoque_nota_xml_qtd_{sufixo_nota}_{indice}",
            )
            valor_item = item3.number_input(
                "Valor unitário R$:", min_value=0.0,
                value=float(item_xml.get("valor_unitario") or 0), step=0.01,
                format="%.4f", key=f"estoque_nota_xml_valor_{sufixo_nota}_{indice}",
            )
            if produto_id:
                itens_para_entrada.append({
                    **item_xml, "produto_id": produto_id, "quantidade": quantidade_item,
                    "valor_unitario": valor_item,
                    "valor_total": round(quantidade_item * valor_item, 2),
                })
            elif produto_id == 0:
                st.caption("Item não vinculado: ele não será lançado. Cadastre o produto antes, se necessário.")
    elif modo_nota == "Manual":
        quantidade_linhas = st.number_input(
            "Quantidade de itens diferentes na nota:", min_value=1, max_value=100,
            value=1, step=1, key="estoque_nota_manual_qtd_itens",
        )
        st.markdown("#### Itens da nota")
        for indice in range(1, int(quantidade_linhas) + 1):
            item1, item2, item3 = st.columns([3, 1, 1])
            produto_id = item1.selectbox(
                f"Produto {indice}:", opcoes_produtos,
                format_func=lambda valor: (
                    "-- Selecionar --" if valor == 0
                    else f"{codigo_item_estoque(produtos_por_id[valor])} - {nome_produto_estoque(produtos_por_id[valor])}"
                ),
                key=f"estoque_nota_manual_produto_{indice}",
            )
            quantidade_item = item2.number_input(
                "Quantidade:", min_value=1, value=1, step=1,
                key=f"estoque_nota_manual_qtd_{indice}",
            )
            valor_item = item3.number_input(
                "Valor unitário R$:", min_value=0.0, step=0.01, format="%.4f",
                key=f"estoque_nota_manual_valor_{indice}",
            )
            if produto_id:
                produto_item = produtos_por_id[produto_id]
                itens_para_entrada.append({
                    "produto_id": produto_id, "numero_item": indice,
                    "codigo_fornecedor": "", "codigo_barras": "",
                    "descricao": nome_produto_estoque(produto_item), "ncm": "",
                    "cfop": "", "unidade": "UN", "quantidade": quantidade_item,
                    "valor_unitario": valor_item,
                    "valor_total": round(float(quantidade_item) * valor_item, 2),
                })

    observacoes_nota = st.text_area(
        "Observações da entrada:", key=f"estoque_nota_observacoes_{sufixo_nota}"
    )
    pode_salvar_nota = bool(
        fornecedor_nota.strip() and numero_nota.strip() and itens_para_entrada
        and (modo_nota == "Manual" or dados_xml)
    )
    if st.button(
        "Confirmar entrada da nota no estoque", type="primary", width="stretch",
        disabled=not pode_salvar_nota, key=f"estoque_nota_salvar_{sufixo_nota}",
    ):
        conn_nota = conectar_banco()
        try:
            nota_id = registrar_entrada_nota(
                conn_nota, fornecedor=fornecedor_nota,
                fornecedor_documento=documento_fornecedor, numero_nota=numero_nota,
                serie=serie_nota, chave_acesso=chave_nota,
                data_compra=data_compra_nota, itens=itens_para_entrada,
                origem="XML" if dados_xml else "Manual", observacoes=observacoes_nota,
                criado_por=st.session_state.get("username", ""), criado_em=agora_br(),
            )
        except Exception as erro_nota:
            st.error(f"A entrada não foi realizada: {erro_nota}")
        else:
            registrar_evento_sistema(
                "entrada_nota", "estoque_notas_entrada", nota_id, fornecedor_nota,
                {"numero_nota": numero_nota, "itens": len(itens_para_entrada),
                 "origem": "XML" if dados_xml else "Manual"},
            )
            st.success(f"Nota #{nota_id} registrada e estoque atualizado.")
            st.rerun()
        finally:
            conn_nota.close()

    st.write("---")
    st.markdown("#### Histórico de entradas por nota")
    conn_hist = conectar_banco()
    cursor_hist = conn_hist.cursor()
    cursor_hist.execute(
        """SELECT n.id, n.numero_nota, n.serie, n.fornecedor, n.data_compra, n.origem,
                  COUNT(i.id) AS itens, COALESCE(SUM(i.valor_total), 0) AS valor_total
           FROM estoque_notas_entrada n
           LEFT JOIN estoque_nota_entrada_itens i ON i.nota_entrada_id=n.id
           GROUP BY n.id, n.numero_nota, n.serie, n.fornecedor, n.data_compra, n.origem
           ORDER BY n.id DESC LIMIT 200"""
    )
    notas_salvas = [dict(item) for item in cursor_hist.fetchall()]
    conn_hist.close()
    if notas_salvas:
        st.dataframe([{
            "ID": item.get("id"), "Nota": item.get("numero_nota"),
            "Série": item.get("serie"), "Fornecedor": item.get("fornecedor"),
            "Compra": data_para_br(item.get("data_compra")), "Origem": item.get("origem"),
            "Itens": item.get("itens"), "Valor": formatar_moeda_br(item.get("valor_total")),
        } for item in notas_salvas], width="stretch", hide_index=True)
    else:
        st.info("Nenhuma entrada de nota registrada ainda.")


@lru_cache(maxsize=8)
def garantir_estrutura_codigo_estoque(conectar_banco):
    """Garante os campos novos mesmo durante o hot reload do Streamlit."""
    conn = conectar_banco()
    cursor = conn.cursor()
    try:
        garantir_coluna(cursor, "estoque", "modelo", "VARCHAR(255) DEFAULT ''")
        garantir_coluna(cursor, "estoque", "codigo_item", "INTEGER")
        garantir_coluna(cursor, "estoque", "tem_fonte", "VARCHAR(5) DEFAULT 'Não'")
        cursor.execute("SELECT id, codigo_item, codigo_entrada, produto FROM estoque ORDER BY id")
        produtos = [dict(item) for item in cursor.fetchall()]
        usados = set()
        for produto in produtos:
            codigo_item_original = produto.get("codigo_item")
            candidato = codigo_item_original
            if not str(candidato or "").strip().isdigit():
                parte_codigo = str(produto.get("codigo_entrada") or "").rsplit(".", 1)[-1].strip()
                candidato = parte_codigo if parte_codigo.isdigit() else None
            if not candidato and str(produto.get("produto") or "").strip().isdigit():
                candidato = str(produto.get("produto")).strip()
            candidato = int(candidato) if str(candidato or "").isdigit() else 0
            if candidato > 0 and candidato not in usados:
                produto["codigo_item"] = candidato
                usados.add(candidato)
                if int(codigo_item_original or 0) != candidato:
                    cursor.execute("UPDATE estoque SET codigo_item=? WHERE id=?", (candidato, produto.get("id")))
            else:
                produto["codigo_item"] = None
        proximo = 1
        for produto in produtos:
            if produto.get("codigo_item"):
                continue
            while proximo in usados:
                proximo += 1
            cursor.execute("UPDATE estoque SET codigo_item=? WHERE id=?", (proximo, produto.get("id")))
            usados.add(proximo)
        conn.commit()
    finally:
        conn.close()


@lru_cache(maxsize=8)
def garantir_estrutura_emprestimos(conectar_banco):
    """Executa o DDL de empréstimos uma vez por processo do Streamlit."""
    conn = conectar_banco()
    try:
        garantir_tabelas_emprestimos(conn)
    finally:
        conn.close()


def renderizar_emprestimos_estoque(estoque_data) -> None:
    st.subheader("Empréstimos de itens do estoque")
    garantir_estrutura_emprestimos(conectar_banco)
    conn_lista = conectar_banco()
    cursor_lista = conn_lista.cursor()
    cursor_lista.execute("SELECT * FROM estoque_emprestimos ORDER BY id DESC")
    emprestimos = [dict(item) for item in cursor_lista.fetchall()]
    cursor_lista.execute("SELECT * FROM estoque_emprestimo_itens ORDER BY id")
    itens_emprestados = [dict(item) for item in cursor_lista.fetchall()]
    cursor_lista.execute("SELECT username, funcionario_nome FROM usuarios ORDER BY funcionario_nome, username")
    usuarios = [dict(item) for item in cursor_lista.fetchall()]
    conn_lista.close()

    atrasados = [item for item in emprestimos if emprestimo_atrasado(item)]
    if atrasados:
        st.error(
            f"Atenção: {len(atrasados)} empréstimo(s) chegaram ao prazo de dois dias. "
            "Confirme abaixo se os itens retornaram ou ficaram com o cliente."
        )
        st.dataframe(
            [{
                "Empréstimo": item.get("id"), "Responsável": item.get("responsavel"),
                "Cliente": item.get("cliente_nome") or "Não informado",
                "Retirada": data_para_br(item.get("data_retirada")),
                "Prazo para confirmação": data_para_br(item.get("data_limite")),
            } for item in atrasados],
            width="stretch", hide_index=True,
        )
    else:
        st.success("Nenhum empréstimo aguardando confirmação após o prazo de dois dias.")

    with st.expander("Registrar novo empréstimo", expanded=not emprestimos):
        produtos_disponiveis = [item for item in estoque_data if int(item.get("quantidade") or 0) > 0]
        produtos_por_id = {int(item["id"]): item for item in produtos_disponiveis}
        usuario_atual = (st.session_state.get("username") or "").strip()
        opcoes_responsavel = []
        rotulos_responsavel = {}
        for usuario in usuarios:
            login = usuario.get("username") or ""
            if login:
                opcoes_responsavel.append(login)
                rotulos_responsavel[login] = usuario.get("funcionario_nome") or login
        if usuario_atual and usuario_atual not in opcoes_responsavel:
            opcoes_responsavel.insert(0, usuario_atual)
            rotulos_responsavel[usuario_atual] = usuario_atual
        indice_responsavel = opcoes_responsavel.index(usuario_atual) if usuario_atual in opcoes_responsavel else 0
        emp1, emp2, emp3 = st.columns(3)
        responsavel = emp1.selectbox(
            "Quem está levando:", opcoes_responsavel,
            index=indice_responsavel, format_func=lambda valor: rotulos_responsavel.get(valor, valor),
            key="emprestimo_responsavel",
        ) if opcoes_responsavel else emp1.text_input("Quem está levando:", key="emprestimo_responsavel_texto")
        clientes_emprestimo = buscar_clientes()
        opcoes_clientes = [0] + [int(item["id"]) for item in clientes_emprestimo]
        clientes_por_id = {int(item["id"]): item for item in clientes_emprestimo}
        cliente_id = emp2.selectbox(
            "Cliente de destino:", opcoes_clientes,
            format_func=lambda valor: "-- Selecionar cliente --" if valor == 0 else clientes_por_id[valor].get("nome") or f"Cliente #{valor}",
            key="emprestimo_cliente",
        )
        data_retirada = emp3.date_input("Data da retirada:", value=date.today(), key="emprestimo_data_retirada")
        produtos_selecionados = st.multiselect(
            "Itens emprestados:", list(produtos_por_id),
            format_func=lambda produto_id: (
                f"{codigo_item_estoque(produtos_por_id[produto_id])} - "
                f"{nome_produto_estoque(produtos_por_id[produto_id])} "
                f"(Disponível: {produtos_por_id[produto_id].get('quantidade') or 0})"
            ),
            key="emprestimo_produtos",
        )
        itens_novo_emprestimo = []
        for produto_id in produtos_selecionados:
            produto = produtos_por_id[produto_id]
            quantidade = st.number_input(
                f"Quantidade — {nome_produto_estoque(produto)}:", min_value=1,
                max_value=max(1, int(produto.get("quantidade") or 0)), value=1, step=1,
                key=f"emprestimo_quantidade_{produto_id}",
            )
            itens_novo_emprestimo.append({"produto_id": produto_id, "quantidade": int(quantidade)})
        observacoes = st.text_area("Observações do empréstimo:", key="emprestimo_observacoes")
        st.caption("O prazo de confirmação será gerado automaticamente para dois dias após a retirada.")
        if st.button(
            "Registrar empréstimo", type="primary", width="stretch",
            disabled=not produtos_selecionados or not cliente_id, key="emprestimo_salvar",
        ):
            cliente = clientes_por_id.get(int(cliente_id or 0), {})
            conn_novo = conectar_banco()
            try:
                emprestimo_id = criar_emprestimo(
                    conn_novo, itens=itens_novo_emprestimo, responsavel=responsavel,
                    cliente_id=cliente_id or None, cliente_nome=cliente.get("nome") or "",
                    data_retirada=data_retirada, observacoes=observacoes,
                    criado_por=usuario_atual, criado_em=agora_br(),
                )
            except Exception as ex:
                st.error(f"Não foi possível registrar o empréstimo: {ex}")
            else:
                registrar_evento_sistema(
                    "emprestimo", "estoque_emprestimos", emprestimo_id,
                    cliente.get("nome") or responsavel,
                    {"responsavel": responsavel, "itens": itens_novo_emprestimo},
                )
                st.session_state["_estoque_widgets_para_limpar"] = [
                    "emprestimo_produtos", "emprestimo_observacoes",
                    *(f"emprestimo_quantidade_{item_novo['produto_id']}" for item_novo in itens_novo_emprestimo),
                ]
                st.success(f"Empréstimo #{emprestimo_id} registrado e itens reservados no estoque.")
                st.rerun()
            finally:
                conn_novo.close()

    st.markdown("#### Histórico e confirmação")
    filtro_emprestimo = st.selectbox(
        "Status:", ["Todos", "Em aberto", "Concluído"], key="emprestimo_filtro_status"
    )
    emprestimos_filtrados = emprestimos if filtro_emprestimo == "Todos" else [
        item for item in emprestimos if item.get("status") == filtro_emprestimo
    ]
    resumo_emprestimos = [{
        "ID": item.get("id"), "Responsável": item.get("responsavel"),
        "Cliente": item.get("cliente_nome") or "Não informado",
        "Retirada": data_para_br(item.get("data_retirada")),
        "Prazo": data_para_br(item.get("data_limite")), "Status": item.get("status"),
        "Alerta": "Confirmar agora" if emprestimo_atrasado(item) else "",
    } for item in emprestimos_filtrados]
    if not resumo_emprestimos:
        st.info("Nenhum empréstimo encontrado.")
        return
    emprestimo_clicado = tabela_clicavel_id(
        st, resumo_emprestimos, "emprestimos_estoque_grade", "ID"
    )
    if emprestimo_clicado is not None:
        st.session_state["emprestimo_estoque_selecionado"] = int(emprestimo_clicado)
    emprestimo_id = int(st.session_state.get("emprestimo_estoque_selecionado") or 0)
    st.caption("Clique em qualquer informação para conferir os itens e encerrar o empréstimo.")
    emprestimo = next((item for item in emprestimos if int(item.get("id") or 0) == emprestimo_id), None)
    if not emprestimo:
        return
    itens_do_emprestimo = [
        item for item in itens_emprestados if int(item.get("emprestimo_id") or 0) == emprestimo_id
    ]
    st.dataframe(
        [{"Item": item.get("id"), "Código": item.get("codigo"), "Produto": item.get("produto"),
          "Quantidade": item.get("quantidade"), "Situação": item.get("status")}
         for item in itens_do_emprestimo],
        width="stretch", hide_index=True,
    )
    itens_abertos = [item for item in itens_do_emprestimo if item.get("status") == STATUS_ITEM_ABERTO]
    if itens_abertos:
        itens_abertos_por_id = {int(item["id"]): item for item in itens_abertos}
        itens_resolver = st.multiselect(
            "Itens que serão confirmados agora:", list(itens_abertos_por_id),
            default=list(itens_abertos_por_id),
            format_func=lambda item_id: (
                f"{itens_abertos_por_id[item_id].get('produto')} "
                f"(Qtd: {itens_abertos_por_id[item_id].get('quantidade')})"
            ),
            key=f"emprestimo_itens_resolver_{emprestimo_id}",
        )
        destino = st.radio(
            "Destino dos itens selecionados:",
            ["Retornaram ao estoque", "Ficaram com o cliente — baixa definitiva"],
            horizontal=True, key=f"emprestimo_destino_{emprestimo_id}",
        )
        obs_resolucao = st.text_area(
            "Observação da confirmação:", key=f"emprestimo_obs_resolucao_{emprestimo_id}"
        )
        confirmar_resolucao = st.checkbox(
            "Confirmo o destino dos itens selecionados.", key=f"emprestimo_confirmar_{emprestimo_id}"
        )
        if st.button(
            "Encerrar itens selecionados", type="primary", width="stretch",
            disabled=not confirmar_resolucao or not itens_resolver,
            key=f"emprestimo_resolver_{emprestimo_id}",
        ):
            conn_resolver = conectar_banco()
            try:
                status_final = resolver_itens_emprestimo(
                    conn_resolver, emprestimo_id=emprestimo_id, item_ids=itens_resolver,
                    devolver_ao_estoque=destino == "Retornaram ao estoque",
                    resolvido_por=st.session_state.get("username", ""),
                    resolvido_em=agora_br(), observacao=obs_resolucao,
                )
            except Exception as ex:
                st.error(f"Não foi possível encerrar os itens: {ex}")
            else:
                registrar_evento_sistema(
                    "resolucao_emprestimo", "estoque_emprestimos", emprestimo_id,
                    emprestimo.get("cliente_nome") or emprestimo.get("responsavel") or "",
                    {"destino": destino, "itens": itens_resolver, "status": status_final},
                )
                st.session_state["_estoque_widgets_para_limpar"] = list((
                    f"emprestimo_itens_resolver_{emprestimo_id}",
                    f"emprestimo_destino_{emprestimo_id}",
                    f"emprestimo_obs_resolucao_{emprestimo_id}",
                    f"emprestimo_confirmar_{emprestimo_id}",
                ))
                st.success("Destino dos itens confirmado e estoque atualizado.")
                st.rerun()
            finally:
                conn_resolver.close()
    else:
        st.success("Todos os itens deste empréstimo já foram confirmados.")


def renderizar_estoque(ctx: dict) -> None:
    aplicar_contexto_pagina(ctx, globals())
    for chave_widget in st.session_state.pop("_estoque_widgets_para_limpar", []):
        st.session_state.pop(chave_widget, None)
    st.markdown(
        """
        <style>
        /* Reforço de leitura exclusivo do módulo de estoque. */
        div[data-testid="stWidgetLabel"] p,
        div[data-testid="stDataFrame"],
        div[data-testid="stDataFrame"] *,
        div[data-testid="stTabs"] button p,
        div[data-testid="stCaptionContainer"] p {
            font-size: 19px !important;
        }
        div[data-testid="stButton"] button,
        div[data-testid="stDownloadButton"] button,
        div[data-baseweb="select"] *,
        input, textarea {
            font-size: 18px !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.title("Controle de Estoque e Inventário")
    aba_est1, aba_est2, aba_est3, aba_nota, aba_est4, aba_est5, aba_est6, aba_est7 = st.tabs([
        "Visão Geral e Movimentação", "Cadastrar Novo Produto", "Editar / Excluir",
        "Entrada de Nota", "Empréstimos", "Solicitar Compra", "Relatório de Compra", "Importar Excel",
    ])

    garantir_estrutura_codigo_estoque(conectar_banco)
    estoque_data = repo_listar_estoque(conectar_banco)
    proximo_codigo_item = max(
        (codigo_item_estoque(produto) for produto in estoque_data),
        default=0,
    ) + 1

    with aba_est1:
        st.subheader("Visão Geral do Estoque")
        if estoque_data:
            col_pesquisa, col_estado = st.columns([2, 1])
            pesquisa_estoque = col_pesquisa.text_input(
                "Pesquisar produto:",
                placeholder="Nome, código, nome genérico, categoria, caixa ou fornecedor",
                key="estoque_pesquisa",
            ).strip().casefold()
            estado_estoque = col_estado.selectbox(
                "Estado do produto:",
                ["Todos", "Novo", "Usado"],
                key="estoque_filtro_estado",
            )

            estoque_filtrado = []
            for produto in estoque_data:
                codigo_completo = montar_codigo_entrada(
                    produto.get("codigo"), produto.get("categoria"), codigo_item_estoque(produto)
                )
                texto_pesquisavel = texto_pesquisa_produto_estoque(produto, codigo_completo)
                corresponde_pesquisa = not pesquisa_estoque or pesquisa_estoque in texto_pesquisavel
                codigo_estado = str(produto.get("codigo") or "").casefold()
                corresponde_estado = estado_estoque == "Todos" or estado_estoque.casefold() in codigo_estado
                if corresponde_pesquisa and corresponde_estado:
                    estoque_filtrado.append(produto)

            st.caption(f"{len(estoque_filtrado)} de {len(estoque_data)} produto(s) encontrado(s).")
            df_estoque = pd.DataFrame(preparar_tabela_estoque(estoque_filtrado))
            id_estoque_selecionado = tabela_selecionavel_id(
                st,
                df_estoque.to_dict("records"),
                "estoque_grade_consulta",
                "ID interno",
                column_config={"ID interno": None},
            )
            if id_estoque_selecionado:
                sincronizar_selecao_produto_estoque(st.session_state, id_estoque_selecionado)
            st.caption("Selecione o produto para carregá-lo na movimentação rápida e na aba Editar / Excluir.")
            st.download_button("Baixar estoque em Excel", data=gerar_excel_tabela(preparar_tabela_estoque(estoque_filtrado, incluir_id_interno=False), "Relatório de Estoque"), file_name="relatorio_estoque.xls", mime="application/vnd.ms-excel", width="stretch")

            st.write("---")
            st.subheader("Baixa de Estoque")
            st.caption("Selecione o cliente ou o usuário da empresa que receberá o item.")
            col_mov1, col_mov2 = st.columns([2, 1])
            
            produtos_por_id = {int(p["id"]): p for p in estoque_data}
            ids_produtos = list(produtos_por_id)
            id_padrao = int(st.session_state.get("estoque_produto_selecionado") or ids_produtos[0])
            if id_padrao not in produtos_por_id:
                id_padrao = ids_produtos[0]
            if st.session_state.get("estoque_produto_movimentacao_id") not in produtos_por_id:
                st.session_state["estoque_produto_movimentacao_id"] = id_padrao
            id_sel = col_mov1.selectbox(
                "Selecione o Produto para Movimentar:",
                ids_produtos,
                key="estoque_produto_movimentacao_id",
                format_func=lambda produto_id: (
                    f"{codigo_item_estoque(produtos_por_id[produto_id])} - "
                    f"{nome_produto_estoque(produtos_por_id[produto_id])} "
                    f"(Qtd: {produtos_por_id[produto_id].get('quantidade') or 0})"
                ),
            )
            
            if id_sel:
                prod_info = produtos_por_id.get(int(id_sel))
                if prod_info:
                    st.download_button("Baixar QR do produto", data=gerar_qr_produto(prod_info),
                        file_name=f"produto_{id_sel}_qr.png", mime="image/png", key=f"qr_produto_{id_sel}")
                foto_produto = buscar_foto_estoque(conectar_banco, int(id_sel)) if prod_info else None
                if foto_produto and foto_produto.get("foto"):
                    st.image(
                        foto_produto.get("foto"),
                        caption=foto_produto.get("foto_nome") or prod_info.get("produto"),
                        width=260,
                    )
                
                qtd_mov = col_mov2.number_input("Quantidade da saída:", min_value=1, value=1, step=1)
                destino_saida = st.radio("Destino da saída:", ["Cliente", "Uso interno"], horizontal=True, key="estoque_baixa_destino")
                uso_interno = destino_saida == "Uso interno"
                usuarios_saida = {item['username']: item for item in listar_funcionarios_sistema()} if uso_interno else {}
                usuario_saida = ""
                if uso_interno:
                    usuario_saida = st.selectbox("Usuário da empresa que receberá o item:", [""] + list(usuarios_saida),
                        format_func=lambda valor: usuarios_saida[valor]['label'] if valor else "-- Selecionar usuário --",
                        key="estoque_baixa_usuario")
                clientes_saida = buscar_clientes() if not uso_interno else []
                clientes_saida_por_id = {int(item["id"]): item for item in clientes_saida}
                cliente_saida_id = 0 if uso_interno else st.selectbox(
                    "Cliente que receberá o item:", [0] + list(clientes_saida_por_id),
                    format_func=lambda valor: (
                        "-- Selecionar cliente --" if valor == 0
                        else clientes_saida_por_id[valor].get("nome") or f"Cliente #{valor}"
                    ),
                    key="estoque_baixa_cliente",
                )
                motivo_saida = st.text_input(
                    "Motivo/histórico da baixa:", key="estoque_baixa_motivo"
                )
                
                if st.button("Confirmar baixa de estoque", type="primary"):
                    cliente_saida = clientes_saida_por_id.get(int(cliente_saida_id or 0), {})
                    destinatario_id = usuario_saida if uso_interno else cliente_saida_id
                    destinatario_nome = usuarios_saida.get(usuario_saida, {}).get('label', '') if uso_interno else cliente_saida.get('nome') or ''
                    erro_saida = validar_saida_com_cliente(
                        destinatario_id, destinatario_nome, qtd_mov,
                        int(prod_info.get("quantidade") or 0), uso_interno=uso_interno,
                    )
                    if erro_saida:
                        st.error(erro_saida)
                    else:
                        conn = conectar_banco()
                        c = conn.cursor()
                        try:
                            c.execute(
                                "SELECT quantidade FROM estoque WHERE id=? FOR UPDATE",
                                (prod_info["id"],),
                            )
                            estoque_atualizado = c.fetchone() or {}
                            quantidade_anterior = int(estoque_atualizado.get("quantidade") or 0)
                            erro_saida = validar_saida_com_cliente(
                                destinatario_id, destinatario_nome, qtd_mov,
                                quantidade_anterior, uso_interno=uso_interno,
                            )
                            if erro_saida:
                                raise ValueError(erro_saida)
                            nova_qtd = quantidade_anterior - int(qtd_mov)
                            c.execute("UPDATE estoque SET quantidade=? WHERE id=?", (nova_qtd, prod_info['id']))
                            registrar_movimentacao(
                                c, produto_id=int(prod_info["id"]), tipo="Saída para uso interno" if uso_interno else "Saída para cliente",
                                quantidade=int(qtd_mov), estoque_anterior=quantidade_anterior,
                                estoque_atual=nova_qtd, cliente_id=None if uso_interno else int(cliente_saida_id),
                                cliente_nome=cliente_saida.get("nome") or "",
                                origem="Baixa manual", observacoes=(f"Uso interno — Usuário: {destinatario_nome}. {motivo_saida}" if uso_interno else motivo_saida),
                                criado_por=st.session_state.get("username", ""), criado_em=agora_br(),
                            )
                            conn.commit()
                        except Exception as erro_baixa:
                            conn.rollback()
                            st.error(f"A baixa não foi realizada: {erro_baixa}")
                        else:
                            registrar_evento_sistema(
                                "Saída", "estoque", prod_info["id"],
                                destinatario_nome,
                                {"produto": prod_info.get("produto"), "quantidade": qtd_mov,
                                 "estoque_anterior": quantidade_anterior, "estoque_atual": nova_qtd,
                                 "cliente_id": cliente_saida_id or None, "usuario_destinatario": usuario_saida,
                                 "destino": destino_saida, "motivo": motivo_saida},
                            )
                            st.success(f"Baixa registrada. Nova quantidade em estoque: {nova_qtd}")
                            st.rerun()
                        finally:
                            conn.close()

            st.write("---")
            st.markdown("#### Histórico de movimentações")
            with st.expander("Cancelar saída manual e devolver ao estoque"):
                if tem_permissao("estoque.edit"):
                    id_estorno = st.number_input("ID da saída no histórico:", min_value=1, step=1, key="estorno_estoque_id")
                    motivo_estorno = st.text_input("Motivo do cancelamento:", key="estorno_estoque_motivo")
                    if st.button("Confirmar cancelamento da saída", key="estorno_estoque_salvar"):
                        conn_estorno = conectar_banco()
                        try:
                            cancelar_saida_manual(conn_estorno, id_estorno, motivo_estorno,
                                st.session_state.get("username", ""), agora_br())
                        except ValueError as erro:
                            st.error(str(erro))
                        else:
                            st.success("Saída cancelada e quantidade devolvida ao estoque.")
                            st.rerun()
                        finally:
                            conn_estorno.close()
            filtro_movimento = st.text_input(
                "Pesquisar cliente, fornecedor ou produto no histórico:",
                key="estoque_movimentacao_pesquisa",
            ).strip().casefold()
            conn_mov = conectar_banco()
            cursor_mov = conn_mov.cursor()
            cursor_mov.execute(
                """SELECT m.id, m.tipo, m.quantidade, m.estoque_anterior, m.estoque_atual,
                          m.cliente_nome, m.fornecedor, m.origem, m.origem_id,
                          m.observacoes, m.criado_por, m.criado_em,
                          COALESCE(e.nome_generico, e.modelo, e.produto, e.codigo_entrada) AS produto
                   FROM estoque_movimentacoes m
                   JOIN estoque e ON e.id=m.produto_id
                   ORDER BY m.id DESC LIMIT 300"""
            )
            movimentacoes = [dict(item) for item in cursor_mov.fetchall()]
            conn_mov.close()
            if filtro_movimento:
                movimentacoes = [
                    item for item in movimentacoes
                    if filtro_movimento in " ".join(str(item.get(campo) or "") for campo in (
                        "produto", "cliente_nome", "fornecedor", "tipo", "origem", "observacoes"
                    )).casefold()
                ]
            if movimentacoes:
                st.dataframe([{
                    "ID": item.get("id"), "Produto": item.get("produto"),
                    "Movimento": item.get("tipo"), "Quantidade": item.get("quantidade"),
                    "Antes": item.get("estoque_anterior"), "Depois": item.get("estoque_atual"),
                    "Cliente": item.get("cliente_nome") or "",
                    "Fornecedor": item.get("fornecedor") or "", "Origem": item.get("origem") or "",
                    "Referência": item.get("origem_id") or "", "Histórico": item.get("observacoes") or "",
                    "Usuário": item.get("criado_por") or "", "Data": item.get("criado_em") or "",
                } for item in movimentacoes], width="stretch", hide_index=True)
            else:
                st.info("Nenhuma movimentação encontrada.")
        else:
            st.info("Nenhum produto cadastrado no seu estoque ainda.")

    with aba_est2:
        # Limpar o rascunho apenas depois de uma gravação confirmada. Validar ou
        # recalcular nunca deve apagar os valores que o usuário está preenchendo.
        if st.session_state.pop('estoque_limpar_cadastro', False):
            for chave in list(st.session_state):
                if str(chave).startswith('estoque_novo_'):
                    del st.session_state[chave]
        ultimo_qr = st.session_state.get("estoque_ultimo_produto_qr")
        if ultimo_qr:
            st.download_button("Baixar QR do produto recém-cadastrado", data=gerar_qr_produto(ultimo_qr),
                file_name=f"produto_{ultimo_qr['id']}_qr.png", mime="image/png", key="qr_ultimo_produto")
        st.subheader("Cadastrar Produto")
        st.caption('Enter não cadastra o produto. Use a prévia para calcular e salve somente quando terminar de preencher.')
        with st.form("form_estoque", clear_on_submit=False, enter_to_submit=False):
            ce1, ce2, ce3 = st.columns(3)
            opcoes_fileira1 = [""] + list(ESTADOS_POR_CODIGO.values())
            opcoes_fileira2 = ["", "2-01 Informática", "2-02 CFTV", "2-03 Alarme", "2-04 Infraestrutura"]
            e_cod = ce1.selectbox("Fileira 1 (Obrigatório):", opcoes_fileira1, key='estoque_novo_cod')
            e_cat = ce2.selectbox("Fileira 2 (Obrigatório):", opcoes_fileira2, key='estoque_novo_cat')
            e_modelo = ce3.text_input("Fileira 3 / Modelo (Obrigatório):", key='estoque_novo_modelo')
            e_nome_generico = st.text_input("Nome genérico / descrição:", key='estoque_novo_nome')

            ce_loc1, ce_loc2, ce_loc3 = st.columns(3)
            ce_loc1.number_input(
                "ID do produto:", value=int(proximo_codigo_item), disabled=True,
                help="Gerado automaticamente e usado como terceira parte do código.",
            )
            e_codigo_entrada = montar_codigo_entrada(e_cod, e_cat, proximo_codigo_item)
            ce_loc2.text_input(
                "Código completo:", value=e_codigo_entrada, disabled=True,
                help="Gerado automaticamente no formato 01.02.01 com as três partes do endereço do estoque.",
            )
            e_caixa = ce_loc3.text_input("Caixa / Gaveta:", key='estoque_novo_caixa')

            ce4, ce5, ce_fonte = st.columns(3)
            e_qtd = ce4.number_input(
                "Quantidade inicial:", min_value=0, value=0, step=1, key='estoque_novo_qtd',
                help="Informe quantas unidades já existem no momento do cadastro. Essa entrada ficará no histórico.",
            )
            e_min = ce5.number_input("Estoque Mínimo (Alerta):", min_value=0, value=5, key='estoque_novo_min')
            e_tem_fonte = ce_fonte.radio("Tem fonte?", ["Não", "Sim"], horizontal=True, key='estoque_novo_fonte')
            e_situacao_nota = st.radio(
                "Documento da compra:", list(SITUACOES_DOCUMENTO_COMPRA), horizontal=True, key='estoque_novo_documento',
                help="Produtos comprados sem nota serão classificados como serviço na venda, mas continuarão baixando o estoque.",
            )

            e_preco_auto = st.checkbox("Calcular preço de revenda automaticamente", value=True, key='estoque_novo_auto')
            ce6, ce7, ce8 = st.columns(3)
            e_custo = ce6.number_input("Valor de compra (R$):", min_value=0.0, step=0.01, format="%.2f", key='estoque_novo_custo')
            e_deslocamento = ce7.number_input("Deslocamento por unidade (R$):", min_value=0.0, step=0.01, format="%.2f", key='estoque_novo_deslocamento')
            e_forn = ce8.text_input(
                "Fornecedor da última compra:", disabled=True,
                help="Preenchido automaticamente quando a nota de entrada for lançada.",
            )
            cp1, cp2, cp3 = st.columns(3)
            e_imposto = cp1.number_input("Impostos (%):", min_value=0.0, step=0.1, format="%.2f", key='estoque_novo_imposto')
            e_lucro = cp2.number_input("Lucro (%):", min_value=0.0, step=0.1, format="%.2f", key='estoque_novo_lucro')
            e_ajuste = cp3.checkbox("Permitir ajuste no orçamento/faturamento", value=False, key='estoque_novo_ajuste')
            preco_calculado = float(calcular_preco_revenda(e_custo, e_deslocamento, e_imposto, e_lucro))
            e_venda_manual = st.number_input(
                "Valor de revenda manual (R$):", min_value=0.0, step=0.01, format="%.2f",
                disabled=e_preco_auto, key='estoque_novo_venda', help="Usado somente quando o cálculo automático estiver desmarcado. Atualize a prévia para habilitar o campo.",
            )
            st.form_submit_button('Calcular / atualizar prévia', key='estoque_novo_previa', help='Atualiza o cálculo e as opções do formulário, sem gravar um produto.')
            st.metric("Preço de revenda utilizado", formatar_moeda_br(preco_calculado if e_preco_auto else e_venda_manual))

            e_obs = st.text_area("Observações Adicionais:", key='estoque_novo_obs')
            e_foto = st.file_uploader("Foto do item (opcional):", type=TIPOS_IMAGEM_UPLOAD, key="estoque_novo_foto")

            if st.form_submit_button("Salvar Produto no Estoque", key='estoque_novo_salvar'):
                if e_cod and e_cat and e_modelo.strip():
                    if e_foto and not upload_dentro_limite(e_foto):
                        erro_upload_grande("foto")
                        st.stop()
                    conn = conectar_banco()
                    c = conn.cursor()
                    produto_salvo = False
                    try:
                        c.execute("SELECT COALESCE(MAX(codigo_item), 0) AS ultimo FROM estoque")
                        ultimo_codigo = c.fetchone()
                        codigo_item_novo = int((ultimo_codigo or {}).get("ultimo") or 0) + 1
                        cod_entrada_final = montar_codigo_entrada(e_cod, e_cat, codigo_item_novo)
                        foto_dados, foto_nome, foto_mime = dados_upload(e_foto)
                        valor_revenda = preco_calculado if e_preco_auto else e_venda_manual
                        descricao_produto = e_nome_generico.strip() or e_modelo.strip()
                        c.execute('''INSERT INTO estoque (codigo, codigo_entrada, codigo_item, produto, modelo, nome_generico, categoria, fileira, caixa, tem_fonte, quantidade, estoque_minimo, valor_custo, valor_venda, fornecedor, observacoes, foto_nome, foto_mime, foto, custo_deslocamento, imposto_percentual, lucro_percentual, preco_revenda_automatico, permitir_ajuste_preco, situacao_nota) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', (e_cod, cod_entrada_final, codigo_item_novo, descricao_produto, e_modelo.strip(), e_nome_generico.strip(), e_cat, e_cod, e_caixa, e_tem_fonte, e_qtd, e_min, e_custo, valor_revenda, e_forn, e_obs, foto_nome, foto_mime, foto_dados, e_deslocamento, e_imposto, e_lucro, "Sim" if e_preco_auto else "Não", int(e_ajuste), e_situacao_nota))
                        produto_id_novo = int(c.lastrowid or 0)
                        if int(e_qtd or 0) > 0:
                            registrar_movimentacao(
                                c,
                                produto_id=produto_id_novo,
                                tipo="Entrada inicial",
                                quantidade=int(e_qtd),
                                estoque_anterior=0,
                                estoque_atual=int(e_qtd),
                                fornecedor=e_forn,
                                origem="Cadastro do produto",
                                origem_id=produto_id_novo,
                                observacoes=e_obs,
                                criado_por=st.session_state.get("username", ""),
                                criado_em=agora_br(),
                            )
                        conn.commit()
                        produto_salvo = True
                    except Exception as e:
                        conn.rollback()
                        st.error(f"Erro ao salvar: {e}")
                    finally:
                        conn.close()
                    if produto_salvo:
                        st.session_state['estoque_limpar_cadastro'] = True
                        st.session_state["estoque_ultimo_produto_qr"] = {"id": produto_id_novo, "codigo_entrada": cod_entrada_final}
                        st.toast("Produto cadastrado com sucesso!")
                        st.rerun()
                else:
                    st.error("As duas primeiras fileiras e a Fileira 3 / Modelo são obrigatórias.")

    with aba_est3:
        st.caption("O QR identifica o produto pelo ID e código cadastrado.")
        st.subheader("Editar ou Excluir Produto")
        if estoque_data:
            act_est = st.radio("Selecione a Ação:", ["Editar Produto", "Excluir Produto"], horizontal=True)
            
            if act_est == "Excluir Produto":
                produtos_por_id_exclusao = {int(p["id"]): p for p in estoque_data}
                ids_exclusao = list(produtos_por_id_exclusao)
                if st.session_state.get("estoque_id_exclusao") not in produtos_por_id_exclusao:
                    st.session_state["estoque_id_exclusao"] = ids_exclusao[0]
                id_del_est = st.selectbox(
                    "Produto para excluir:", ids_exclusao, key="estoque_id_exclusao",
                    format_func=lambda produto_id: (
                        f"{codigo_item_estoque(produtos_por_id_exclusao[produto_id])} - "
                        f"{nome_produto_estoque(produtos_por_id_exclusao[produto_id])}"
                    ),
                )
                if st.button("Excluir Produto Permanentemente"):
                    deletar_registro('estoque', 'id', id_del_est)
                    st.success("Produto removido com sucesso.")
                    st.rerun()

                if eh_admin_master():
                    st.write("---")
                    with st.expander("Excluir todos os itens do estoque", expanded=False):
                        st.error("Atenção: esta ação excluirá permanentemente todos os produtos do estoque.")
                        confirmacao_excluir_estoque = st.text_input(
                            'Para confirmar, digite "EXCLUIR TODO O ESTOQUE":',
                            key="confirmacao_excluir_todo_estoque",
                        )
                        confirmar_exclusao_total = st.checkbox(
                            "Confirmo que desejo excluir todos os itens do estoque.",
                            key="checkbox_excluir_todo_estoque",
                        )
                        if st.button(
                            "Excluir todos os itens permanentemente",
                            type="primary",
                            disabled=not (
                                confirmar_exclusao_total
                                and confirmacao_excluir_estoque.strip().upper() == "EXCLUIR TODO O ESTOQUE"
                            ),
                            key="btn_excluir_todo_estoque",
                        ):
                            if not eh_admin_master():
                                st.error("Esta ação é exclusiva do administrador master Daniel.fabio.")
                                st.stop()
                            conn = conectar_banco()
                            c = conn.cursor()
                            try:
                                quantidade_excluida = len(estoque_data)
                                c.execute("DELETE FROM estoque")
                                conn.commit()
                            except Exception:
                                conn.rollback()
                                raise
                            finally:
                                conn.close()
                            registrar_evento_sistema(
                                "exclusao_total",
                                "estoque",
                                0,
                                "Todos os itens",
                                {"quantidade_excluida": quantidade_excluida},
                            )
                            st.success(f"Todos os {quantidade_excluida} itens do estoque foram excluídos.")
                            st.rerun()
                    
            elif act_est == "Editar Produto":
                pesquisa_edicao = st.text_input(
                    "Consultar produto por nome:",
                    placeholder="Digite o nome, modelo ou nome genérico",
                    key="estoque_pesquisa_edicao",
                ).strip().casefold()
                produtos_edicao_filtrados = [
                    produto for produto in estoque_data
                    if not pesquisa_edicao or pesquisa_edicao in texto_pesquisa_produto_estoque(produto)
                ]
                produtos_por_id_edicao = {int(p["id"]): p for p in produtos_edicao_filtrados}
                ids_edicao = list(produtos_por_id_edicao)
                if not ids_edicao:
                    st.info("Nenhum produto encontrado com esse nome.")
                    id_ed_est = None
                elif st.session_state.get("estoque_id_edicao") not in produtos_por_id_edicao:
                    st.session_state["estoque_id_edicao"] = ids_edicao[0]
                if ids_edicao:
                    id_ed_est = st.selectbox(
                        "Produto para editar:", ids_edicao, key="estoque_id_edicao",
                        format_func=lambda produto_id: (
                            f"{codigo_item_estoque(produtos_por_id_edicao[produto_id])} - "
                            f"{nome_produto_estoque(produtos_por_id_edicao[produto_id])}"
                        ),
                    )
                prod_edit = produtos_por_id_edicao.get(int(id_ed_est)) if id_ed_est else None
                
                if prod_edit:
                    st.download_button("Baixar QR do produto", data=gerar_qr_produto(prod_edit),
                        file_name=f"produto_{id_ed_est}_qr.png", mime="image/png", key=f"qr_editar_produto_{id_ed_est}")
                    st.caption("O QR contém os dados salvos do produto. Salve as alterações antes de baixar uma nova etiqueta; etiquetas antigas não se atualizam automaticamente.")
                    with st.expander(f"Editando Produto: {prod_edit.get('codigo_entrada') or prod_edit['produto']}", expanded=True):
                        opcoes_estado_edit = list(ESTADOS_POR_CODIGO.values())
                        estado_atual = str(prod_edit.get("codigo") or "")
                        if estado_atual and estado_atual not in opcoes_estado_edit:
                            opcoes_estado_edit.append(estado_atual)
                        ne_cod = st.selectbox(
                            "Fileira 1 / Estado:",
                            opcoes_estado_edit,
                            index=opcoes_estado_edit.index(estado_atual) if estado_atual in opcoes_estado_edit else 0,
                            key=f"ecod_{id_ed_est}",
                        )
                        ne_cat = st.text_input("Fileira 2:", value=prod_edit['categoria'], key=f"ecat_{id_ed_est}")
                        codigo_item_edit = codigo_item_estoque(prod_edit)
                        ne_modelo = st.text_input(
                            "Fileira 3 / Modelo:",
                            value=prod_edit.get("modelo") or (
                                "" if str(prod_edit.get("produto") or "").isdigit() else prod_edit.get("produto") or ""
                            ),
                            key=f"emodelo_{id_ed_est}",
                        )
                        ne_nome_generico = st.text_input("Nome genérico / descrição:", value=prod_edit.get("nome_generico") or "", key=f"enomegenerico_{id_ed_est}")
                        col_loc1, col_loc2, col_loc3 = st.columns(3)
                        col_loc1.number_input("ID do produto:", value=int(codigo_item_edit), disabled=True, key=f"ecodigoitem_{id_ed_est}")
                        ne_codigo_entrada = montar_codigo_entrada(ne_cod, ne_cat, codigo_item_edit)
                        col_loc2.text_input("Código completo:", value=ne_codigo_entrada, disabled=True, key=f"ecodent_{id_ed_est}")
                        ne_caixa = col_loc3.text_input("Caixa / Gaveta:", value=prod_edit.get('caixa') or "", key=f"ecaixa_{id_ed_est}")
                        
                        col_eq1, col_eq2, col_eq3 = st.columns(3)
                        ne_qtd = col_eq1.number_input(
                            "Quantidade atual:", value=prod_edit['quantidade'], disabled=True,
                            help="Alterada somente por nota de entrada, baixa ou empréstimo.",
                            # A quantidade faz parte da chave porque widgets desabilitados do
                            # Streamlit preservam o valor anterior mesmo após st.rerun().
                            key=f"eqtd_{id_ed_est}_{prod_edit['quantidade']}",
                        )
                        ne_min = col_eq2.number_input("Estoque Mínimo:", value=prod_edit['estoque_minimo'], key=f"emin_{id_ed_est}")
                        tem_fonte_atual = normalizar_tem_fonte(prod_edit.get("tem_fonte"))
                        ne_tem_fonte = col_eq3.radio(
                            "Tem fonte?", ["Não", "Sim"],
                            index=1 if tem_fonte_atual == "Sim" else 0,
                            horizontal=True, key=f"etemfonte_{id_ed_est}",
                        )
                        situacao_nota_atual = normalizar_situacao_compra(prod_edit.get("situacao_nota"))
                        ne_situacao_nota = st.radio(
                            "Documento da compra:", list(SITUACOES_DOCUMENTO_COMPRA),
                            index=0 if situacao_nota_atual == COMPRADO_COM_NOTA else 1, horizontal=True,
                            key=f"esituacaonota_{id_ed_est}",
                        )

                        st.markdown("#### Adicionar unidades ao estoque")
                        st.caption("Use esta área para repor este produto. A entrada ficará registrada no histórico e somará à quantidade atual.")
                        fornecedores_entrada = [
                            item for item in buscar_clientes()
                            if str(item.get("tipo") or "").casefold() in {"fornecedor", "ambos"}
                        ]
                        fornecedores_entrada_por_id = {int(item["id"]): item for item in fornecedores_entrada}
                        ent1, ent2, ent3 = st.columns(3)
                        entrada_qtd = ent1.number_input(
                            "Quantidade para adicionar:", min_value=1, value=1, step=1,
                            key=f"entrada_rapida_qtd_{id_ed_est}",
                        )
                        entrada_data = ent2.date_input(
                            "Data da compra:", value=date.today(), key=f"entrada_rapida_data_{id_ed_est}"
                        )
                        entrada_valor = ent3.number_input(
                            "Valor unitário da compra (R$):", min_value=0.0,
                            value=float(decimal_valor(prod_edit.get("valor_custo"))), step=0.01,
                            key=f"entrada_rapida_valor_{id_ed_est}",
                        )
                        entrada_fornecedor_id = st.selectbox(
                            "Fornecedor cadastrado:", [0] + list(fornecedores_entrada_por_id),
                            format_func=lambda valor: (
                                "-- Informar manualmente --" if valor == 0
                                else fornecedores_entrada_por_id[valor].get("nome") or f"Fornecedor #{valor}"
                            ),
                            key=f"entrada_rapida_fornecedor_id_{id_ed_est}",
                        )
                        fornecedor_entrada_cadastrado = fornecedores_entrada_por_id.get(int(entrada_fornecedor_id or 0), {})
                        entrada_fornecedor = st.text_input(
                            "Fornecedor da compra:",
                            value=fornecedor_entrada_cadastrado.get("nome") or "",
                            disabled=bool(fornecedor_entrada_cadastrado),
                            key=f"entrada_rapida_fornecedor_{id_ed_est}_{entrada_fornecedor_id}",
                        )
                        entrada_com_nota = st.radio(
                            "Documento da entrada:", ["Com nota fiscal", "Sem nota fiscal"],
                            horizontal=True, key=f"entrada_rapida_documento_{id_ed_est}",
                        ) == "Com nota fiscal"
                        entrada_numero = st.text_input(
                            "Número da nota fiscal:" if entrada_com_nota else "Referência (opcional):",
                            key=f"entrada_rapida_numero_{id_ed_est}_{entrada_com_nota}",
                        )
                        entrada_obs = st.text_input(
                            "Observação da entrada:", key=f"entrada_rapida_obs_{id_ed_est}"
                        )
                        if st.button("Adicionar quantidade ao estoque", type="primary", key=f"entrada_rapida_salvar_{id_ed_est}"):
                            try:
                                entrada = preparar_entrada_rapida(
                                    produto_id=int(id_ed_est), descricao=nome_produto_estoque(prod_edit),
                                    quantidade=int(entrada_qtd), fornecedor=entrada_fornecedor,
                                    data_compra=entrada_data, com_nota=entrada_com_nota,
                                    numero_documento=entrada_numero, valor_unitario=entrada_valor,
                                )
                                conn_entrada = conectar_banco()
                                try:
                                    nota_entrada_id = registrar_entrada_nota(
                                        conn_entrada, fornecedor=entrada["fornecedor"],
                                        fornecedor_documento=fornecedor_entrada_cadastrado.get("cnpj") or "",
                                        numero_nota=entrada["numero_nota"], serie="", chave_acesso="",
                                        data_compra=entrada["data_compra"], itens=entrada["itens"],
                                        origem=entrada["origem"], observacoes=entrada_obs,
                                        criado_por=st.session_state.get("username", ""), criado_em=agora_br(),
                                    )
                                finally:
                                    conn_entrada.close()
                            except Exception as erro_entrada:
                                st.error(f"A quantidade não foi adicionada: {erro_entrada}")
                            else:
                                registrar_evento_sistema(
                                    "Entrada", "estoque", int(id_ed_est), entrada_fornecedor,
                                    {"quantidade": int(entrada_qtd), "nota_entrada_id": nota_entrada_id,
                                     "documento": entrada["numero_nota"], "com_nota": entrada_com_nota},
                                )
                                st.success(f"Foram adicionadas {int(entrada_qtd)} unidade(s) ao estoque.")
                                st.rerun()
                        
                        auto_atual = str(prod_edit.get("preco_revenda_automatico") or "Não").casefold() in {"sim", "1", "true"}
                        ne_preco_auto = st.checkbox("Calcular preço de revenda automaticamente", value=auto_atual, key=f"eprecoauto_{id_ed_est}")
                        col_ev1, col_ev2, col_ev3 = st.columns(3)
                        ne_custo = col_ev1.number_input("Valor de compra (R$):", min_value=0.0, value=float(decimal_valor(prod_edit.get('valor_custo'))), step=0.01, key=f"ecusto_{id_ed_est}")
                        ne_deslocamento = col_ev2.number_input("Deslocamento/unidade (R$):", min_value=0.0, value=float(decimal_valor(prod_edit.get('custo_deslocamento'))), step=0.01, key=f"edesloc_{id_ed_est}")
                        ne_forn = col_ev3.text_input(
                            "Fornecedor da última compra:", value=prod_edit.get('fornecedor') or "",
                            disabled=True, key=f"eforn_{id_ed_est}",
                        )
                        st.text_input(
                            "Data da última compra:",
                            value=data_para_br(prod_edit.get("data_compra")) or "Nenhuma nota lançada",
                            disabled=True, key=f"edata_compra_{id_ed_est}",
                        )
                        col_pr1, col_pr2, col_pr3 = st.columns(3)
                        ne_imposto = col_pr1.number_input("Impostos (%):", min_value=0.0, value=float(prod_edit.get('imposto_percentual') or 0), step=0.1, key=f"eimposto_{id_ed_est}")
                        ne_lucro = col_pr2.number_input("Lucro (%):", min_value=0.0, value=float(prod_edit.get('lucro_percentual') or 0), step=0.1, key=f"elucro_{id_ed_est}")
                        ne_ajuste = col_pr3.checkbox("Permitir ajuste comercial", value=bool(prod_edit.get('permitir_ajuste_preco')), key=f"eajuste_{id_ed_est}")
                        preco_edit_calculado = float(calcular_preco_revenda(ne_custo, ne_deslocamento, ne_imposto, ne_lucro))
                        ne_venda_manual = st.number_input("Valor de revenda manual (R$):", min_value=0.0, value=float(decimal_valor(prod_edit.get('valor_venda'))), step=0.01, disabled=ne_preco_auto, key=f"evenda_{id_ed_est}")
                        st.metric("Preço de revenda utilizado", formatar_moeda_br(preco_edit_calculado if ne_preco_auto else ne_venda_manual))
                        
                        ne_obs = st.text_area("Observações:", value=prod_edit['observacoes'], key=f"eobs_{id_ed_est}")
                        foto_produto_edit = buscar_foto_estoque(conectar_banco, int(id_ed_est))
                        if foto_produto_edit and foto_produto_edit.get("foto"):
                            st.image(
                                foto_produto_edit.get("foto"),
                                caption=foto_produto_edit.get("foto_nome") or "Foto atual",
                                width=260,
                            )
                        ne_foto = st.file_uploader("Trocar foto do item (opcional):", type=TIPOS_IMAGEM_UPLOAD, key=f"efoto_{id_ed_est}")
                        
                        if st.button("Guardar Edição do Produto", type="primary"):
                            if ne_foto and not upload_dentro_limite(ne_foto):
                                erro_upload_grande("foto")
                                st.stop()
                            conn = conectar_banco()
                            c = conn.cursor()
                            cod_entrada_edit = montar_codigo_entrada(ne_cod, ne_cat, codigo_item_edit)
                            descricao_edit = ne_nome_generico.strip() or ne_modelo.strip()
                            ne_venda = preco_edit_calculado if ne_preco_auto else ne_venda_manual
                            if ne_foto:
                                foto_dados, foto_nome, foto_mime = dados_upload(ne_foto)
                                c.execute('''UPDATE estoque SET codigo=?, codigo_entrada=?, codigo_item=?, produto=?, modelo=?, nome_generico=?, categoria=?, fileira=?, caixa=?, tem_fonte=?, quantidade=?, estoque_minimo=?, valor_custo=?, valor_venda=?, fornecedor=?, observacoes=?, foto_nome=?, foto_mime=?, foto=?, custo_deslocamento=?, imposto_percentual=?, lucro_percentual=?, preco_revenda_automatico=?, permitir_ajuste_preco=?, situacao_nota=? WHERE id=?''', (ne_cod, cod_entrada_edit, codigo_item_edit, descricao_edit, ne_modelo, ne_nome_generico, ne_cat, ne_cod, ne_caixa, ne_tem_fonte, ne_qtd, ne_min, ne_custo, ne_venda, ne_forn, ne_obs, foto_nome, foto_mime, foto_dados, ne_deslocamento, ne_imposto, ne_lucro, "Sim" if ne_preco_auto else "Não", int(ne_ajuste), ne_situacao_nota, id_ed_est))
                            else:
                                c.execute('''UPDATE estoque SET codigo=?, codigo_entrada=?, codigo_item=?, produto=?, modelo=?, nome_generico=?, categoria=?, fileira=?, caixa=?, tem_fonte=?, quantidade=?, estoque_minimo=?, valor_custo=?, valor_venda=?, fornecedor=?, observacoes=?, custo_deslocamento=?, imposto_percentual=?, lucro_percentual=?, preco_revenda_automatico=?, permitir_ajuste_preco=?, situacao_nota=? WHERE id=?''', (ne_cod, cod_entrada_edit, codigo_item_edit, descricao_edit, ne_modelo, ne_nome_generico, ne_cat, ne_cod, ne_caixa, ne_tem_fonte, ne_qtd, ne_min, ne_custo, ne_venda, ne_forn, ne_obs, ne_deslocamento, ne_imposto, ne_lucro, "Sim" if ne_preco_auto else "Não", int(ne_ajuste), ne_situacao_nota, id_ed_est))
                            conn.commit()
                            conn.close()
                            st.success("Produto atualizado com sucesso!")
                            st.rerun()
                else:
                    st.info("Produto com este ID não foi encontrado.")

    with aba_nota:
        renderizar_entrada_notas(estoque_data)

    with aba_est4:
        renderizar_emprestimos_estoque(estoque_data)

    with aba_est5:
        st.subheader("Pedidos de Compra")
        itens_baixos = [p for p in estoque_data if int(p['quantidade'] or 0) <= int(p['estoque_minimo'] or 0)]
        if itens_baixos:
            st.warning("Itens abaixo ou no estoque mínimo encontrados.")
            st.dataframe([dict(p) for p in itens_baixos], width="stretch", hide_index=True)
        else:
            st.info("Nenhum item está abaixo do estoque mínimo no momento.")

        st.write("---")
        if estoque_data:
            produtos_compra_por_id = {int(item["id"]): item for item in estoque_data}
            produtos_compra_selecionados = st.multiselect(
                "Produtos para solicitar compra:", list(produtos_compra_por_id),
                format_func=lambda produto_id: (
                    f"{codigo_item_estoque(produtos_compra_por_id[produto_id])} - "
                    f"{nome_produto_estoque(produtos_compra_por_id[produto_id])} "
                    f"(Atual: {produtos_compra_por_id[produto_id].get('quantidade') or 0} / "
                    f"Mín: {produtos_compra_por_id[produto_id].get('estoque_minimo') or 0})"
                ),
                key="produtos_solicitacao_compra",
            )
            itens_solicitacao_compra = []
            for produto_id in produtos_compra_selecionados:
                prod_compra = produtos_compra_por_id[produto_id]
                pc1, pc2 = st.columns(2)
                qtd_solicitada = pc1.number_input(
                    f"Quantidade — {nome_produto_estoque(prod_compra)}:",
                    min_value=1, value=max(1, int(prod_compra.get("estoque_minimo") or 1) - int(prod_compra.get("quantidade") or 0)),
                    step=1, key=f"qtd_solicitacao_compra_{produto_id}",
                )
                fornecedor_sug = pc2.text_input(
                    f"Fornecedor — {nome_produto_estoque(prod_compra)}:",
                    value=prod_compra.get("fornecedor") or "",
                    key=f"fornecedor_solicitacao_compra_{produto_id}",
                )
                itens_solicitacao_compra.append((prod_compra, int(qtd_solicitada), fornecedor_sug))
            obs_compra = st.text_area("Observações do pedido:")

            if st.button(
                "Salvar Solicitações de Compra", type="primary", width="stretch",
                disabled=not itens_solicitacao_compra,
            ):
                conn_pc = conectar_banco()
                cpc = conn_pc.cursor()
                try:
                    for prod_compra, qtd_solicitada, fornecedor_sug in itens_solicitacao_compra:
                        cpc.execute('''INSERT INTO pedidos_compra
                            (data_pedido, produto_id, codigo, produto, quantidade_solicitada, fornecedor, status, observacoes)
                            VALUES (?,?,?,?,?,?,?,?)''',
                            (date.today().strftime("%d/%m/%Y"), prod_compra['id'], prod_compra['codigo'],
                             nome_produto_estoque(prod_compra), qtd_solicitada, fornecedor_sug, "Solicitado", obs_compra))
                    conn_pc.commit()
                except Exception as ex:
                    conn_pc.rollback()
                    st.error(f"Não foi possível salvar as solicitações: {ex}")
                else:
                    st.session_state["_estoque_widgets_para_limpar"] = [
                        "produtos_solicitacao_compra",
                        *(f"qtd_solicitacao_compra_{prod_compra['id']}" for prod_compra, _, _ in itens_solicitacao_compra),
                        *(f"fornecedor_solicitacao_compra_{prod_compra['id']}" for prod_compra, _, _ in itens_solicitacao_compra),
                    ]
                    st.success(f"{len(itens_solicitacao_compra)} solicitação(ões) de compra salva(s).")
                    st.rerun()
                finally:
                    conn_pc.close()

        conn_pc = conectar_banco()
        conn_pc.row_factory = None
        cpc = conn_pc.cursor()
        cpc.execute("SELECT * FROM pedidos_compra ORDER BY id DESC")
        pedidos = cpc.fetchall()
        conn_pc.close()

        if pedidos:
            st.write("---")
            st.subheader("Histórico de Solicitações")
            st.dataframe([dict(p) for p in pedidos], width="stretch", hide_index=True)

    with aba_est6:
        st.subheader("Relatório de Compra")
        conn_rel = conectar_banco()
        cr = conn_rel.cursor()
        cr.execute('''
            SELECT pc.*, COALESCE(e.categoria, '') AS categoria,
                   COALESCE(e.codigo_entrada, '') AS codigo_entrada,
                   COALESCE(e.fileira, '') AS fileira, COALESCE(e.caixa, '') AS caixa
            FROM pedidos_compra pc
            LEFT JOIN estoque e ON e.id = pc.produto_id
            ORDER BY pc.id DESC
        ''')
        compras_rel = cr.fetchall()
        conn_rel.close()

        if compras_rel:
            status_opcoes = ["Todos"] + sorted({(p.get("status") or "Sem status") for p in compras_rel})
            filtro_status = st.selectbox("Filtrar por status:", status_opcoes)
            compras_filtradas = compras_rel if filtro_status == "Todos" else [p for p in compras_rel if (p.get("status") or "Sem status") == filtro_status]
            tabela_compras = preparar_tabela_compras(compras_filtradas)
            st.dataframe(tabela_compras, width="stretch", hide_index=True)
            st.download_button(
                "Baixar relatório de compra em Excel",
                data=gerar_excel_tabela(tabela_compras, "Relatório de Compra"),
                file_name="relatorio_compra.xls",
                mime="application/vnd.ms-excel",
                width="stretch",
            )
        else:
            st.info("Nenhuma solicitação de compra cadastrada.")

    with aba_est7:
        st.subheader("Importar Produtos de uma Planilha Excel")
        st.caption("A primeira linha deve conter os nomes das colunas. Formato aceito: .xlsx")
        arquivo_excel_estoque = st.file_uploader("Selecionar planilha de produtos:", type=["xlsx"], key="estoque_importar_excel")

        if arquivo_excel_estoque:
            try:
                cabecalhos_excel, produtos_excel = ler_excel_estoque(arquivo_excel_estoque)
            except Exception as ex:
                st.error(f"Não foi possível ler a planilha: {ex}")
                cabecalhos_excel, produtos_excel = [], []

            if produtos_excel:
                st.success(f"Planilha lida: {len(produtos_excel)} produtos encontrados.")
                st.write("**Prévia das primeiras linhas:**")
                st.dataframe(produtos_excel[:10], width="stretch", hide_index=True)

                st.write("**Relacionar colunas da planilha com o formato do estoque:**")
                opcoes_colunas = ["-- Não importar --"] + cabecalhos_excel
                mapeamento_estoque = {}
                coluna_codigo_sugerida = sugerir_coluna_estoque("codigo_entrada", cabecalhos_excel)
                if coluna_codigo_sugerida == "-- Não importar --":
                    coluna_codigo_sugerida = cabecalhos_excel[0]
                amostra_codigo_valida = any(
                    codigo_localizacao_valido(linha.get(coluna_codigo_sugerida))
                    for linha in produtos_excel[:20]
                )
                separar_codigo_automaticamente = st.checkbox(
                    "Interpretar automaticamente o estado, a área e a identificação do código",
                    value=amostra_codigo_valida,
                    key="estoque_separar_codigo_importacao",
                    help="Exemplo: 02.04.07 será importado como Usado, Infraestrutura e identificação 07.",
                )
                coluna_codigo_composto = None
                campos_extraidos_codigo = {"codigo", "categoria", "codigo_item", "codigo_entrada"}
                if separar_codigo_automaticamente:
                    coluna_codigo_composto = st.selectbox(
                        "Coluna do código no formato 02.04.07:",
                        cabecalhos_excel,
                        index=cabecalhos_excel.index(coluna_codigo_sugerida),
                        key="estoque_coluna_codigo_composto",
                    )
                    st.info(
                        f"A coluna {coluna_codigo_composto} será interpretada automaticamente. "
                        "Primeira parte: 01 Novo ou 02 Usado. Segunda parte: 01 Informática, "
                        "02 CFTV, 03 Alarme ou 04 Infraestrutura. A terceira parte é o ID do produto."
                    )
                cols_mapa = st.columns(3)
                campos_para_mapear = [
                    (campo, rotulo)
                    for campo, rotulo in COLUNAS_ESTOQUE_IMPORTACAO.items()
                    if not separar_codigo_automaticamente or campo not in campos_extraidos_codigo
                ]
                for idx, (campo, rotulo) in enumerate(campos_para_mapear):
                    sugestao = sugerir_coluna_estoque(campo, cabecalhos_excel)
                    indice_sugestao = opcoes_colunas.index(sugestao) if sugestao in opcoes_colunas else 0
                    mapeamento_estoque[campo] = cols_mapa[idx % 3].selectbox(
                        rotulo, opcoes_colunas, index=indice_sugestao, key=f"mapa_estoque_{campo}"
                    )

                modo_importacao = st.radio(
                    "Quando o mesmo código interno e produto já existirem:",
                    ["Atualizar produto existente", "Ignorar produto repetido"],
                    horizontal=True,
                    key="estoque_modo_importacao",
                )

                if st.button("Importar produtos para o banco", type="primary", width="stretch", key="btn_importar_estoque_excel"):
                    codigo_item_mapeado = mapeamento_estoque.get("codigo_item", "-- Não importar --")
                    descricao_mapeada = mapeamento_estoque.get("nome_generico", "-- Não importar --")
                    modelo_mapeado = mapeamento_estoque.get("modelo", "-- Não importar --")
                    if not separar_codigo_automaticamente and codigo_item_mapeado == "-- Não importar --":
                        st.error("Relacione o ID do produto usado como terceira parte do código.")
                    elif descricao_mapeada == "-- Não importar --" and modelo_mapeado == "-- Não importar --":
                        st.error("Relacione pelo menos a descrição ou o modelo do produto.")
                    else:
                        conn_imp = conectar_banco()
                        cimp = conn_imp.cursor()
                        importados, atualizados, ignorados, codigos_invalidos = 0, 0, 0, 0
                        erro_importacao = None
                        try:
                            for linha in produtos_excel:
                                dados_produto = {
                                    campo: linha.get(coluna) if coluna != "-- Não importar --" else ""
                                    for campo, coluna in mapeamento_estoque.items()
                                }
                                if separar_codigo_automaticamente:
                                    codigo, categoria, identificacao = interpretar_codigo_localizacao(
                                        linha.get(coluna_codigo_composto)
                                    )
                                    if not identificacao:
                                        ignorados += 1
                                        codigos_invalidos += 1
                                        continue
                                    dados_produto.update({
                                        "codigo": codigo,
                                        "categoria": categoria,
                                        "codigo_item": identificacao,
                                        "codigo_entrada": montar_codigo_entrada(codigo, categoria, identificacao),
                                    })
                                nome_generico = texto_importacao(dados_produto["nome_generico"])
                                modelo = texto_importacao(dados_produto["modelo"])
                                produto = nome_generico or modelo
                                if not produto:
                                    ignorados += 1
                                    continue
                                codigo = texto_importacao(dados_produto["codigo"])
                                categoria = texto_importacao(dados_produto["categoria"])
                                codigo_item = inteiro_importacao(dados_produto["codigo_item"])
                                if codigo_item <= 0:
                                    ignorados += 1
                                    codigos_invalidos += 1
                                    continue
                                codigo_entrada = texto_importacao(dados_produto["codigo_entrada"]) or montar_codigo_entrada(codigo, categoria, codigo_item)
                                valores = (
                                    codigo, codigo_entrada, codigo_item, produto, modelo, nome_generico, categoria, codigo,
                                    texto_importacao(dados_produto["caixa"]),
                                    normalizar_tem_fonte(dados_produto["tem_fonte"]),
                                    inteiro_importacao(dados_produto["quantidade"]),
                                    inteiro_importacao(dados_produto["estoque_minimo"], 5),
                                    texto_importacao(dados_produto["valor_custo"]),
                                    texto_importacao(dados_produto["valor_venda"]),
                                    texto_importacao(dados_produto["fornecedor"]),
                                    texto_importacao(dados_produto["observacoes"]),
                                )
                                cimp.execute(
                                    """SELECT id FROM estoque
                                       WHERE codigo_entrada=? OR codigo_item=?
                                       ORDER BY id DESC LIMIT 1""",
                                    (codigo_entrada, codigo_item),
                                )
                                existente = cimp.fetchone()
                                if existente and modo_importacao == "Ignorar produto repetido":
                                    ignorados += 1
                                elif existente:
                                    cimp.execute(
                                        """UPDATE estoque SET codigo=?, codigo_entrada=?, codigo_item=?, produto=?, modelo=COALESCE(NULLIF(?, ''), modelo), nome_generico=?, categoria=?, fileira=?,
                                           caixa=?, tem_fonte=?, quantidade=?, estoque_minimo=?, valor_custo=?, valor_venda=?, fornecedor=?, observacoes=?
                                           WHERE id=?""",
                                        valores + (existente["id"],),
                                    )
                                    atualizados += 1
                                else:
                                    cimp.execute(
                                        """INSERT INTO estoque
                                           (codigo, codigo_entrada, codigo_item, produto, modelo, nome_generico, categoria, fileira, caixa, tem_fonte, quantidade,
                                            estoque_minimo, valor_custo, valor_venda, fornecedor, observacoes)
                                           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                                        valores,
                                    )
                                    importados += 1
                            conn_imp.commit()
                        except Exception as ex:
                            conn_imp.rollback()
                            erro_importacao = str(ex)
                        finally:
                            conn_imp.close()

                        if erro_importacao:
                            st.error(f"A importação foi cancelada sem alterar o banco: {erro_importacao}")
                        else:
                            st.success(f"Importação concluída: {importados} novos, {atualizados} atualizados e {ignorados} ignorados.")
                            if codigos_invalidos:
                                st.warning(
                                    f"{codigos_invalidos} linha(s) foram ignoradas porque o código não tinha "
                                    "um estado, uma área e uma identificação válidos, como 01.01.07 ou 02.04.07."
                                )
                            st.rerun()
            elif cabecalhos_excel:
                st.warning("A planilha não possui produtos abaixo do cabeçalho.")

