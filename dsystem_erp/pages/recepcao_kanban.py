from __future__ import annotations

from dsystem_erp.app_context import aplicar_contexto_pagina
from dsystem_erp.services.recepcao_kanban import (
    CORES_KANBAN_OS,
    STATUS_KANBAN_OS,
    alteracoes_do_quadro,
    gerar_etiqueta_equipamento,
    montar_quadro_equipamentos,
)

try:
    from streamlit_sortables import sort_items
except ImportError:  # O deploy instala a versão fixada em requirements.txt.
    sort_items = None


ESTILO_KANBAN = """
.sortable-component {
  display: flex;
  gap: 14px;
  overflow-x: auto;
  padding: 8px 4px 18px;
  background: transparent;
}
.sortable-container {
  min-width: 270px;
  width: 270px;
  background: #111827;
  border: 1px solid #293548;
  border-radius: 14px;
  overflow: hidden;
  box-shadow: 0 8px 24px rgba(0,0,0,.18);
}
.sortable-container-header {
  padding: 13px 14px;
  background: #172033;
  color: #f8fafc;
  border-bottom: 1px solid #293548;
  font-size: 13px;
  font-weight: 800;
}
.sortable-container-body {
  min-height: 150px;
  padding: 9px;
  background: #0d1421;
}
.sortable-item, .sortable-item:hover {
  margin: 8px 0;
  padding: 12px 13px;
  border: 1px solid #2b3b52;
  border-left: 4px solid #1683ff;
  border-radius: 10px;
  background: #172033;
  color: #e5edf8;
  box-shadow: 0 3px 12px rgba(0,0,0,.2);
  font-size: 12px;
  line-height: 1.45;
  white-space: pre-line;
  cursor: grab;
}
.sortable-item:hover {
  border-color: #1683ff;
  transform: translateY(-1px);
}
"""
ESTILO_KANBAN += "\n".join(
    f".sortable-container:nth-child({indice}) {{ border-top: 3px solid {CORES_KANBAN_OS[status]}; }}"
    for indice, status in enumerate(STATUS_KANBAN_OS, start=1)
)


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
    if not equipamentos:
        st.info("Nenhum equipamento corresponde aos filtros selecionados.")
        return

    totais = {
        status: sum(1 for item in equipamentos if (item.get("kanban_status") or "Recebido") == status)
        for status in STATUS_KANBAN_OS
    }
    metricas = st.columns(len(STATUS_KANBAN_OS))
    for coluna, status in zip(metricas, STATUS_KANBAN_OS):
        coluna.metric(status, totais[status])

    quadro, cartao_para_id = montar_quadro_equipamentos(equipamentos)
    if sort_items is None:
        st.error("O componente do Kanban não está instalado. Execute: pip install -r requirements.txt")
    elif tem_permissao("recepcao.edit"):
        st.caption("Arraste um cartão para mudar a etapa. A alteração é salva automaticamente no banco.")
        resultado = sort_items(
            quadro,
            multi_containers=True,
            direction="horizontal",
            custom_style=ESTILO_KANBAN,
            key=f"recepcao_kanban_{st.session_state.get('kanban_versao', 0)}",
        )
        alteracoes = alteracoes_do_quadro(resultado, equipamentos, cartao_para_id)
        if alteracoes:
            _salvar_alteracoes_quadro(alteracoes)
            st.session_state["kanban_versao"] = st.session_state.get("kanban_versao", 0) + 1
            st.toast(f"{len(alteracoes)} alteração(ões) salva(s) no Kanban.", icon="✅")
            st.rerun()
    else:
        st.info("Seu usuário pode consultar o quadro, mas não possui permissão para mover equipamentos.")
        for status in STATUS_KANBAN_OS:
            with st.expander(f"{status} ({totais[status]})", expanded=status == "Recebido"):
                for item in [x for x in equipamentos if (x.get("kanban_status") or "Recebido") == status]:
                    st.write(f"OS #{int(item.get('os_id') or 0):05d} · {item.get('numero_item')} — {item.get('cliente') or 'Cliente'}")

    st.divider()
    st.subheader("Detalhes e impressão de etiqueta")
    equipamentos_por_rotulo = {
        f"OS #{int(item.get('os_id') or 0):05d} · {item.get('numero_item')} · {item.get('cliente') or 'Cliente'}": item
        for item in equipamentos
    }
    rotulo_selecionado = st.selectbox("Selecionar equipamento:", list(equipamentos_por_rotulo))
    item_selecionado = equipamentos_por_rotulo[rotulo_selecionado]
    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Etapa atual", item_selecionado.get("kanban_status") or "Recebido")
    d2.write(f"**Equipamento:** {item_selecionado.get('equipamento') or 'Não informado'}")
    d3.write(f"**Série/patrimônio:** {item_selecionado.get('numero_serie') or 'Não informado'}")
    d4.write(f"**Técnico:** {item_selecionado.get('atendente') or item_selecionado.get('tecnico_extra') or 'Não definido'}")
    st.download_button(
        "Imprimir etiqueta com código de barras e QR Code",
        data=gerar_etiqueta_equipamento(item_selecionado, APP_BASE_URL),
        file_name=f"etiqueta_{item_selecionado.get('numero_item')}.pdf",
        mime="application/pdf",
        width="stretch",
        key=f"kanban_etiqueta_{item_selecionado['id']}",
    )


def _salvar_alteracoes_quadro(alteracoes: list[dict]) -> None:
    usuario = st.session_state.get("username", "")
    momento = agora_br()
    conn = conectar_banco()
    c = conn.cursor()
    try:
        for alteracao in alteracoes:
            c.execute(
                """UPDATE equipamentos_os
                   SET kanban_status=?, kanban_ordem=?, kanban_alterado_por=?, kanban_alterado_em=?
                   WHERE id=?""",
                (alteracao["status"], alteracao["ordem"], usuario, momento, alteracao["id"]),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    for alteracao in alteracoes:
        if alteracao["status"] != alteracao["status_anterior"]:
            registrar_evento_sistema(
                "Movimentação Kanban",
                "equipamentos_os",
                alteracao["id"],
                "",
                {"de": alteracao["status_anterior"], "para": alteracao["status"]},
            )
