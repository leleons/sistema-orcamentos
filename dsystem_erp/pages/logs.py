"""Consulta e exportação dos logs funcionais e técnicos."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from dsystem_erp.app_context import aplicar_contexto_pagina
from dsystem_erp.services.audit_log import resumir_detalhes_log
from dsystem_erp.ui_consulta import tabela_clicavel_id


def renderizar_log_sistema(ctx) -> None:
    aplicar_contexto_pagina(ctx, globals())
    if not eh_admin_master():
        st.error("Este log é exclusivo para Daniel.fabio.")
        return

    st.title("Log do Sistema")
    st.caption(
        "Histórico exclusivo do Daniel.fabio com entradas, saídas, "
        "edições e exclusões registradas no site."
    )

    hoje = date.today()
    col1, col2, col3, col4 = st.columns([1.2, 1.2, 1, 1])
    with col1:
        data_inicio = st.date_input(
            "Data inicial:", value=hoje - timedelta(days=30), key="log_data_inicio"
        )
    with col2:
        data_fim = st.date_input("Data final:", value=hoje, key="log_data_fim")
    with col3:
        filtro_acao = st.selectbox(
            "Ação:", ["Todas", "Entrada", "Saída", "Editar", "Excluir"], key="log_acao"
        )
    with col4:
        limite = st.number_input(
            "Limite:", min_value=50, max_value=5000, value=500, step=50, key="log_limite"
        )

    col5, col6, col7 = st.columns([1.4, 1.2, 1.4])
    filtro_cliente = col5.text_input("Filtrar por cliente:", key="log_cliente")
    filtro_tabela = col6.text_input("Filtrar por módulo/tabela:", key="log_tabela")
    busca_livre = col7.text_input("Busca livre:", key="log_busca")

    inicio_sql = f"{data_inicio.strftime('%Y-%m-%d')} 00:00:00"
    fim_sql = f"{data_fim.strftime('%Y-%m-%d')} 23:59:59"
    where = ["criado_em BETWEEN %s AND %s"]
    params = [inicio_sql, fim_sql]
    if filtro_acao != "Todas":
        where.append("acao=%s")
        params.append(filtro_acao)
    if filtro_cliente.strip():
        where.append("cliente LIKE %s")
        params.append(f"%{filtro_cliente.strip()}%")
    if filtro_tabela.strip():
        where.append("tabela LIKE %s")
        params.append(f"%{filtro_tabela.strip()}%")
    if busca_livre.strip():
        where.append(
            "(usuario LIKE %s OR tabela LIKE %s OR registro_id LIKE %s "
            "OR cliente LIKE %s OR detalhes LIKE %s)"
        )
        busca = f"%{busca_livre.strip()}%"
        params.extend([busca, busca, busca, busca, busca])

    conn = conectar_banco()
    cursor = conn.cursor()
    cursor.execute(
        f"""SELECT * FROM {TABELA_LOG_SISTEMA}
            WHERE {' AND '.join(where)}
            ORDER BY criado_em DESC
            LIMIT %s""",
        params + [int(limite)],
    )
    logs = cursor.fetchall()
    conn.close()

    if not logs:
        st.info("Nenhum registro encontrado para os filtros selecionados.")
        return

    tabela_logs = []
    contagem_acoes = {}
    contagem_tabelas = {}
    for log in logs:
        item = dict(log)
        criado = item.get("criado_em")
        criado_fmt = (
            criado.strftime("%d/%m/%Y %H:%M:%S")
            if isinstance(criado, datetime)
            else str(criado or "")
        )
        tabela_logs.append(
            {
                "Data/Hora": criado_fmt,
                "Usuário": item.get("usuario", ""),
                "Ação": item.get("acao", ""),
                "Módulo/Tabela": item.get("tabela", ""),
                "ID": item.get("registro_id", ""),
                "Cliente": item.get("cliente", ""),
                "Página": item.get("pagina", ""),
                "Resumo": resumir_detalhes_log(item.get("detalhes")),
            }
        )
        acao_log = item.get("acao", "") or "Sem ação"
        tabela_log = item.get("tabela", "") or "Sem tabela"
        contagem_acoes[acao_log] = contagem_acoes.get(acao_log, 0) + 1
        contagem_tabelas[tabela_log] = contagem_tabelas.get(tabela_log, 0) + 1

    met1, met2, met3, met4 = st.columns(4)
    met1.metric("Registros filtrados", len(tabela_logs))
    met2.metric("Edições", contagem_acoes.get("Editar", 0))
    met3.metric("Exclusões", contagem_acoes.get("Excluir", 0))
    modulo_top = max(contagem_tabelas.items(), key=lambda item: item[1])[0]
    met4.metric("Módulo mais ativo", modulo_top)
    id_log_clicado = tabela_clicavel_id(
        st, tabela_logs, "logs_sistema_grade", campo_id="ID"
    ) if tabela_logs else None
    if id_log_clicado:
        st.session_state["log_id_detalhe_ativo"] = int(id_log_clicado)

    exp1, exp2, exp3 = st.columns([1, 1, 1.2])
    exp1.download_button(
        "Exportar log em Excel",
        data=gerar_excel_tabela(tabela_logs, "Log do Sistema"),
        file_name="log_sistema.xls",
        mime="application/vnd.ms-excel",
        width="stretch",
    )
    exp2.download_button(
        "Exportar log em PDF",
        data=gerar_pdf_tabela_simples(tabela_logs, "Log do Sistema"),
        file_name="log_sistema.pdf",
        mime="application/pdf",
        width="stretch",
    )
    with exp3:
        confirmar_limpeza = st.checkbox(
            "Confirmar limpeza do log filtrado", key="log_confirma_limpeza"
        )
        if st.button(
            "Limpar log filtrado",
            disabled=not confirmar_limpeza,
            width="stretch",
            key="btn_limpar_log",
        ):
            conn_limpa = conectar_banco()
            cursor_limpa = conn_limpa.cursor()
            cursor_limpa.execute(
                f"DELETE FROM {TABELA_LOG_SISTEMA} WHERE {' AND '.join(where)}", params
            )
            conn_limpa.commit()
            conn_limpa.close()
            st.success("Log filtrado limpo.")
            st.rerun()

    id_log = int(st.session_state.get("log_id_detalhe_ativo") or 0)
    with st.expander("Ver detalhes técnicos do log", expanded=bool(id_log)):
        log_sel = next(
            (dict(item) for item in logs if int(item.get("id") or 0) == int(id_log)), None
        )
        if log_sel:
            log_sel = {
                chave: (
                    valor.strftime("%Y-%m-%d %H:%M:%S")
                    if isinstance(valor, datetime)
                    else valor
                )
                for chave, valor in log_sel.items()
            }
            st.json(log_sel)
        else:
            st.caption("Clique em qualquer informação do log para abrir os detalhes.")

    renderizar_logs_tecnicos(ctx, contexto_aplicado=True)


def renderizar_logs_tecnicos(ctx, contexto_aplicado: bool = False) -> None:
    if not contexto_aplicado:
        aplicar_contexto_pagina(ctx, globals())
    st.write("---")
    st.subheader("Logs técnicos")
    st.caption(
        "Erros e eventos internos: backup, banco, emissão fiscal, e-mail, "
        "integrações e rotinas automáticas."
    )

    t1, t2, t3 = st.columns([1, 1.3, 1])
    nivel = t1.selectbox(
        "Nível técnico:", ["Todos", "ERROR", "WARNING", "INFO"], key="log_tecnico_nivel"
    )
    origem = t2.text_input("Origem:", key="log_tecnico_origem")
    limite = t3.number_input(
        "Limite técnico:",
        min_value=20,
        max_value=1000,
        value=200,
        step=20,
        key="log_tecnico_limite",
    )

    where = ["1=1"]
    params = []
    if nivel != "Todos":
        where.append("nivel=%s")
        params.append(nivel)
    if origem.strip():
        where.append("origem LIKE %s")
        params.append(f"%{origem.strip()}%")

    conn = conectar_banco()
    cursor = conn.cursor()
    try:
        cursor.execute(
            f"""SELECT id, criado_em, nivel, origem, mensagem, detalhes
                FROM logs_tecnicos
                WHERE {' AND '.join(where)}
                ORDER BY criado_em DESC
                LIMIT %s""",
            params + [int(limite)],
        )
        tecnicos = cursor.fetchall()
    except Exception as ex:
        conn.close()
        st.info(f"Log técnico ainda não está disponível neste banco: {ex}")
        return
    conn.close()

    if not tecnicos:
        st.info("Nenhum log técnico encontrado.")
        return

    linhas = []
    por_nivel = {}
    for log in tecnicos:
        item = dict(log)
        criado = item.get("criado_em")
        criado_fmt = (
            criado.strftime("%d/%m/%Y %H:%M:%S")
            if isinstance(criado, datetime)
            else str(criado or "")
        )
        nivel_item = item.get("nivel") or "-"
        por_nivel[nivel_item] = por_nivel.get(nivel_item, 0) + 1
        linhas.append(
            {
                "ID": item.get("id"),
                "Data/Hora": criado_fmt,
                "Nível": nivel_item,
                "Origem": item.get("origem") or "",
                "Mensagem": item.get("mensagem") or "",
                "Detalhes": resumir_detalhes_log(item.get("detalhes"), limite=240),
            }
        )

    l1, l2, l3 = st.columns(3)
    l1.metric("Eventos técnicos", len(linhas))
    l2.metric("Erros", por_nivel.get("ERROR", 0))
    l3.metric("Avisos", por_nivel.get("WARNING", 0))
    st.dataframe(linhas, width="stretch", hide_index=True)
    st.download_button(
        "Exportar logs técnicos",
        data=gerar_excel_tabela(linhas, "Logs Técnicos"),
        file_name="logs_tecnicos.xls",
        mime="application/vnd.ms-excel",
        width="stretch",
        key="exportar_logs_tecnicos",
    )
