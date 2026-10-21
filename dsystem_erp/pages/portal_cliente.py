from __future__ import annotations

from dsystem_erp.app_context import aplicar_contexto_pagina
from dsystem_erp.services.portal_cliente import portal_funcionario


def renderizar_portal_cliente_page(ctx: dict) -> None:
    aplicar_contexto_pagina(ctx, globals())
    conn = conectar_banco()
    c = conn.cursor()

    if st.session_state.get("tipo_login") != "cliente":
        st.title("Gestão de chamados")
        if eh_chefe_chamados() or st.session_state.get("is_admin", 0):
            renderizar_gestao_chamados_chefe()
        else:
            renderizar_chamados_funcionario()
        conn.close()
        return

    cliente_portal = None
    cliente_portal_id = None
    if st.session_state.get("tipo_login") == "cliente":
        cliente_portal = st.session_state.get("cliente_nome")
        cliente_portal_id = st.session_state.get("cliente_id")
    elif st.session_state.get("is_admin", 0):
        clientes_portal = buscar_clientes()
        nomes_portal = [cli["nome"] for cli in clientes_portal]
        cliente_portal = st.selectbox("Cliente:", nomes_portal) if nomes_portal else None
        cliente_portal_id = next((cli.get("id") for cli in clientes_portal if cli.get("nome") == cliente_portal), None)
    else:
        usuario_cliente = st.session_state.get("username", "")
        c.execute(
            "SELECT id, nome FROM clientes WHERE nome=%s OR email=%s OR codigo_cliente=%s LIMIT 1",
            (usuario_cliente, usuario_cliente, usuario_cliente),
        )
        cli = c.fetchone()
        cliente_portal = cli["nome"] if cli else usuario_cliente
        cliente_portal_id = cli["id"] if cli else None

    if cliente_portal:
        secao_portal = st.session_state.get("portal_cliente_secao", "inicio")
        secao_query_portal = obter_query_param("secao", "")
        if secao_query_portal:
            secao_portal = normalizar_secao_portal(secao_query_portal)
            st.session_state["portal_cliente_secao"] = secao_portal

        if st.session_state.get("acao_portal") == "abrir_chamado":
            st.session_state["portal_cliente_secao"] = "abrir_chamado"
            secao_portal = "abrir_chamado"
        elif st.session_state.get("chamado_destacado"):
            st.session_state["portal_cliente_secao"] = "meus_chamados"
            secao_portal = "meus_chamados"

        if portal_funcionario(st.session_state) and secao_portal not in ('inicio', 'abrir_chamado', 'meus_chamados', 'contato'):
            secao_portal = 'meus_chamados'
            st.session_state['portal_cliente_secao'] = secao_portal
        renderizar_portal_cliente_home(cliente_portal, cliente_portal_id)

        if secao_portal != "inicio":
            st.write("---")

        if secao_portal == "documentos":
            renderizar_portal_documentos_cliente(cliente_portal, cliente_portal_id)
        elif secao_portal == "os":
            renderizar_portal_ordens_servico(
                cliente_portal, c, conn, cliente_portal_id=cliente_portal_id
            )
        elif secao_portal == "abrir_chamado":
            if tem_permissao("cliente.chamados"):
                renderizar_abertura_chamado(cliente_portal, cliente_portal_id)
            else:
                st.info("Seu usuário não tem permissão para abrir chamados.")
        elif secao_portal == "meus_chamados":
            renderizar_chamados_cliente(cliente_portal, cliente_portal_id)
        elif secao_portal == "notas":
            renderizar_portal_notas_cliente(cliente_portal)
        elif secao_portal == "financeiro":
            renderizar_portal_financeiro_cliente(cliente_portal, cliente_portal_id)
        elif secao_portal == "contato":
            renderizar_portal_contato_cliente(cliente_portal)
        elif secao_portal == "gestao_chamados" and eh_chefe_chamados():
            renderizar_gestao_chamados_chefe()
        elif secao_portal == "chamados_atribuidos" and st.session_state.get("tipo_login") != "cliente":
            renderizar_chamados_funcionario()

        if st.session_state.get("tipo_login") != "cliente":
            admin_cols = st.columns(2)
            if eh_chefe_chamados() and admin_cols[0].button("Gestão de chamados", width="stretch", key="portal_admin_gestao_chamados"):
                selecionar_secao_portal("gestao_chamados")
            if admin_cols[1].button("Chamados atribuídos", width="stretch", key="portal_admin_chamados_atribuidos"):
                selecionar_secao_portal("chamados_atribuidos")
    else:
        st.info("Nenhum cliente encontrado para este acesso.")
    conn.close()

