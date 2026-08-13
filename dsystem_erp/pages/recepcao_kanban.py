from __future__ import annotations

from dsystem_erp.app_context import aplicar_contexto_pagina
from dsystem_erp.services.recepcao_kanban import STATUS_KANBAN_OS, gerar_etiqueta_equipamento, proximo_status


def renderizar_recepcao_kanban(ctx: dict) -> None:
    aplicar_contexto_pagina(ctx, globals())
    if not tem_permissao("recepcao.view"):
        st.error("Você não tem permissão para acessar a recepção.")
        st.stop()

    st.title("Recepção de Equipamentos — Kanban")
    st.caption("Todo equipamento deste quadro está obrigatoriamente vinculado a uma Ordem de Serviço.")
    if st.button("Abrir nova O.S. para receber equipamento", type="primary"):
        st.session_state["pagina_atual"] = "Ordem de Serviço (OS)"
        st.rerun()

    conn = conectar_banco(); c = conn.cursor()
    c.execute("""SELECT eo.*, os.cliente, os.cpf_cnpj, os.atendente, os.tecnico_extra,
                        os.data_os, os.chamado_id
                 FROM equipamentos_os eo
                 JOIN ordens_servico os ON os.os_id=eo.os_id
                 ORDER BY eo.id DESC""")
    equipamentos = [dict(item) for item in c.fetchall()]
    conn.close()
    if not equipamentos:
        st.info("Nenhuma máquina recebida. Salve uma O.S. para criar o primeiro cartão e a etiqueta.")
        return

    k1, k2 = st.columns([2, 1])
    busca = k1.text_input("Buscar cliente, O.S., item, equipamento ou série:").strip().casefold()
    apenas_meus = k2.checkbox("Somente atribuídos a mim")
    if busca:
        equipamentos = [item for item in equipamentos if busca in f"{item.get('os_id')} {item.get('numero_item')} {item.get('cliente')} {item.get('equipamento')} {item.get('numero_serie')}".casefold()]
    if apenas_meus:
        usuario = (st.session_state.get("funcionario_nome") or st.session_state.get("username") or "").casefold()
        equipamentos = [item for item in equipamentos if usuario in f"{item.get('atendente')} {item.get('tecnico_extra')}".casefold()]

    totais = {status: sum(1 for item in equipamentos if (item.get("kanban_status") or "Recebido") == status) for status in STATUS_KANBAN_OS}
    st.write(" | ".join(f"**{status}:** {totais[status]}" for status in STATUS_KANBAN_OS))

    for inicio in (0, 4):
        grupo = STATUS_KANBAN_OS[inicio:inicio + 4]
        colunas = st.columns(len(grupo))
        for coluna, status in zip(colunas, grupo):
            with coluna:
                st.markdown(f"### {status} ({totais[status]})")
                for item in [x for x in equipamentos if (x.get("kanban_status") or "Recebido") == status]:
                    with st.container(border=True):
                        st.markdown(f"**OS #{int(item.get('os_id') or 0):05d} · {item.get('numero_item')}**")
                        st.write(item.get("cliente") or "Cliente não informado")
                        st.caption(f"{item.get('tipo_equipamento') or ''} — {item.get('equipamento') or ''}")
                        if item.get("numero_serie"):
                            st.caption(f"Série/patrimônio: {item.get('numero_serie')}")
                        if item.get("chamado_id"):
                            st.caption(f"Chamado vinculado: #{item.get('chamado_id')}")
                        st.download_button(
                            "Imprimir etiqueta", data=gerar_etiqueta_equipamento(item, APP_BASE_URL),
                            file_name=f"etiqueta_{item.get('numero_item')}.pdf", mime="application/pdf",
                            width="stretch", key=f"kanban_etiqueta_{item['id']}",
                        )
                        if tem_permissao("recepcao.edit"):
                            a1, a2 = st.columns(2)
                            if a1.button("←", disabled=status == STATUS_KANBAN_OS[0], key=f"kanban_ant_{item['id']}", help="Voltar etapa"):
                                _mover(item["id"], proximo_status(status, -1)); st.rerun()
                            if a2.button("→", disabled=status == STATUS_KANBAN_OS[-1], key=f"kanban_prox_{item['id']}", help="Avançar etapa"):
                                _mover(item["id"], proximo_status(status, 1)); st.rerun()


def _mover(equipamento_id: int, novo_status: str) -> None:
    conn = conectar_banco(); c = conn.cursor()
    c.execute("UPDATE equipamentos_os SET kanban_status=?, kanban_alterado_por=?, kanban_alterado_em=? WHERE id=?",
              (novo_status, st.session_state.get("username", ""), agora_br(), equipamento_id))
    conn.commit(); conn.close()
