from __future__ import annotations

from dsystem_erp.app_context import aplicar_contexto_pagina
from dsystem_erp.ui_consulta import tabela_selecionavel_id


def renderizar_contratos(ctx: dict) -> None:
    aplicar_contexto_pagina(ctx, globals())
    if not tem_permissao("contratos.view"):
        st.error("Você não tem permissão para acessar contratos.")
        st.stop()

    st.title("Contratos")
    st.caption("Consulta central de contratos de clientes, fornecedores e funcionários.")
    if tem_permissao("contratos.edit"):
        with st.expander("Cadastrar contrato existente", expanded=False):
            with st.form("contrato_existente", clear_on_submit=True):
                uc1, uc2, uc3 = st.columns(3)
                novo_tipo = uc1.text_input("Tipo do contrato:")
                nova_classificacao = uc2.selectbox("Vinculado a:", ["Cliente", "Fornecedor", "Funcionário", "Outro"])
                nova_parte = uc3.text_input("Nome da parte:")
                uc4, uc5, uc6 = st.columns(3)
                novo_inicio = uc4.date_input("Data de início:", value=None)
                novo_vencimento = uc5.date_input("Data de vencimento:", value=None)
                novo_valor = uc6.text_input("Valor do contrato:")
                novo_arquivo = st.file_uploader("Arquivo do contrato:", type=["pdf", "doc", "docx", "jpg", "jpeg", "png"])
                nova_obs = st.text_area("Observações:")
                cadastrar = st.form_submit_button("Cadastrar contrato", type="primary", width="stretch")
            if cadastrar:
                if not novo_tipo.strip() or not nova_parte.strip() or not novo_arquivo:
                    st.error("Informe tipo, nome da parte e arquivo.")
                elif not upload_dentro_limite(novo_arquivo):
                    erro_upload_grande("contrato")
                else:
                    dados, nome, mime = dados_upload(novo_arquivo)
                    conn_novo = conectar_banco(); cn = conn_novo.cursor()
                    cn.execute("""INSERT INTO contratos
                               (tipo, parte_tipo, parte_nome, nome_arquivo, mime_type, arquivo, status,
                                valor, data_inicio, data_vencimento, observacoes, criado_por, criado_em)
                               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                               (novo_tipo.strip(), nova_classificacao, nova_parte.strip(), nome, mime, dados, "Ativo",
                                novo_valor, data_para_banco_br(novo_inicio) if novo_inicio else "",
                                data_para_banco_br(novo_vencimento) if novo_vencimento else "", nova_obs,
                                st.session_state.get("username", ""), agora_br()))
                    conn_novo.commit(); conn_novo.close(); st.success("Contrato cadastrado."); st.rerun()
    conn = conectar_banco(); c = conn.cursor()
    c.execute("SELECT * FROM contratos ORDER BY id DESC")
    contratos = [dict(item) for item in c.fetchall()]
    conn.close()

    f1, f2, f3 = st.columns(3)
    busca = f1.text_input("Buscar nome, tipo ou arquivo:", key="contratos_busca").strip().casefold()
    tipos = sorted({item.get("tipo") or "Sem tipo" for item in contratos})
    tipo_filtro = f2.selectbox("Tipo:", ["Todos"] + tipos, key="contratos_tipo")
    status_filtro = f3.selectbox("Status:", ["Todos", "Ativo", "Encerrado", "Cancelado", "Em renovação"], key="contratos_status")
    filtrados = contratos
    if busca:
        filtrados = [x for x in filtrados if busca in f"{x.get('parte_nome','')} {x.get('tipo','')} {x.get('nome_arquivo','')}".casefold()]
    if tipo_filtro != "Todos":
        filtrados = [x for x in filtrados if (x.get("tipo") or "Sem tipo") == tipo_filtro]
    if status_filtro != "Todos":
        filtrados = [x for x in filtrados if (x.get("status") or "Ativo") == status_filtro]

    linhas = [{
        "ID": x.get("id"), "Tipo": x.get("tipo"), "Vinculado a": x.get("parte_nome"),
        "Classificação": x.get("parte_tipo"), "Início": data_para_br(x.get("data_inicio")),
        "Vencimento": data_para_br(x.get("data_vencimento")), "Valor": x.get("valor") or "",
        "Status": x.get("status") or "Ativo", "Arquivo": x.get("nome_arquivo"),
    } for x in filtrados]
    selecionado_id = tabela_selecionavel_id(st, linhas, "contratos_grade", "ID") if linhas else None
    if not linhas:
        st.info("Nenhum contrato encontrado. Os próximos contratos gerados serão arquivados aqui automaticamente.")
        return
    st.caption("Clique na linha do contrato para abrir a consulta e edição abaixo.")
    if selecionado_id:
        st.session_state["contrato_aberto_id"] = int(selecionado_id)
    contrato_id = st.session_state.get("contrato_aberto_id")
    contrato = next((x for x in contratos if int(x.get("id") or 0) == int(contrato_id or 0)), None)
    if not contrato:
        return

    st.divider()
    st.subheader(f"Contrato #{contrato['id']} — {contrato.get('parte_nome') or ''}")
    ce1, ce2, ce3 = st.columns(3)
    tipo_edit = ce1.text_input("Tipo do contrato:", value=contrato.get("tipo") or "", disabled=not tem_permissao("contratos.edit"), key=f"contrato_tipo_{contrato['id']}")
    parte_edit = ce2.text_input("Cliente/fornecedor/funcionário:", value=contrato.get("parte_nome") or "", disabled=not tem_permissao("contratos.edit"), key=f"contrato_parte_{contrato['id']}")
    status_edit = ce3.selectbox("Status:", ["Ativo", "Em renovação", "Encerrado", "Cancelado"], index=["Ativo", "Em renovação", "Encerrado", "Cancelado"].index(contrato.get("status") if contrato.get("status") in ["Ativo", "Em renovação", "Encerrado", "Cancelado"] else "Ativo"), disabled=not tem_permissao("contratos.edit"), key=f"contrato_status_{contrato['id']}")
    observacoes = st.text_area("Observações:", value=contrato.get("observacoes") or "", disabled=not tem_permissao("contratos.edit"), key=f"contrato_obs_{contrato['id']}")
    if contrato.get("arquivo"):
        st.download_button("Baixar contrato", data=contrato["arquivo"], file_name=contrato.get("nome_arquivo") or f"contrato_{contrato['id']}.pdf", mime=contrato.get("mime_type") or "application/pdf", width="stretch")
    if tem_permissao("contratos.edit"):
        if st.button("Salvar alterações do contrato", type="primary", width="stretch", key=f"contrato_salvar_{contrato['id']}"):
            conn = conectar_banco(); c = conn.cursor()
            c.execute("UPDATE contratos SET tipo=?, parte_nome=?, status=?, observacoes=?, alterado_por=?, alterado_em=? WHERE id=?", (tipo_edit, parte_edit, status_edit, observacoes, st.session_state.get("username", ""), agora_br(), contrato["id"]))
            conn.commit(); conn.close(); st.success("Contrato atualizado."); st.rerun()
    if tem_permissao("contratos.delete"):
        with st.expander("Excluir contrato"):
            confirmar = st.checkbox("Confirmo a exclusão do contrato e do arquivo armazenado.", key=f"contrato_confirmar_exclusao_{contrato['id']}")
            if st.button("Excluir contrato", disabled=not confirmar, key=f"contrato_excluir_{contrato['id']}"):
                deletar_registro("contratos", "id", contrato["id"]); st.session_state.pop("contrato_aberto_id", None); st.rerun()
