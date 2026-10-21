from __future__ import annotations

from dsystem_erp.app_context import aplicar_contexto_pagina
from dsystem_erp.migrations import garantir_coluna
from dsystem_erp.kanban_component import quadro_interativo
from dsystem_erp.pages.etiquetas_os import renderizar_etiquetas_os
from dsystem_erp.services.recepcao_kanban import (
    CORES_KANBAN_OS,
    STATUS_KANBAN_OS,
    alteracoes_do_quadro_registros,
    montar_quadro_registros,
    alvo_qr_equipamento,
    buscar_equipamento_qr,
    servicos_equipamento,
)


def renderizar_recepcao_kanban(ctx: dict) -> None:
    aplicar_contexto_pagina(ctx, globals())
    if not tem_permissao("recepcao.view"):
        st.error("Você não tem permissão para acessar a recepção.")
        st.stop()

    if not st.session_state.get("kanban_estrutura_verificada"):
        _garantir_estrutura_kanban()
        st.session_state["kanban_estrutura_verificada"] = True

    st.title("Recepção de Equipamentos — Kanban")
    if _renderizar_ficha_qr():
        return
    st.caption("Acompanhe em um único quadro as Ordens de Serviço, os atendimentos e os chamados.")
    if st.button("Abrir nova O.S. para receber equipamento", type="primary"):
        st.session_state["pagina_atual"] = "Ordem de Serviço (OS)"
        st.rerun()

    modo_kanban = st.radio(
        "Exibir:", ["Quadro ativo", "Itens arquivados"], horizontal=True,
        key="kanban_modo_exibicao",
        help="Itens entregues podem ser arquivados para não acumularem na coluna Entregue.",
    )
    valor_arquivado = 1 if modo_kanban == "Itens arquivados" else 0

    conn = conectar_banco()
    c = conn.cursor()
    c.execute("""SELECT eo.*, os.cliente, os.cpf_cnpj, os.atendente, os.tecnico_extra,
                        os.data_os, os.chamado_id
                 FROM equipamentos_os eo
                 JOIN ordens_servico os ON os.os_id=eo.os_id
                 WHERE COALESCE(eo.kanban_arquivado, 0)=?
                 ORDER BY eo.id DESC""", (valor_arquivado,))
    equipamentos = [dict(item) for item in c.fetchall()]
    c.execute(
        "SELECT * FROM atendimentos_checklist WHERE COALESCE(kanban_arquivado, 0)=? ORDER BY id DESC",
        (valor_arquivado,),
    )
    atendimentos = [dict(item) for item in c.fetchall()]
    c.execute(
        "SELECT * FROM chamados_cliente WHERE COALESCE(kanban_arquivado, 0)=? ORDER BY id DESC",
        (valor_arquivado,),
    )
    chamados = [dict(item) for item in c.fetchall()]
    conn.close()

    registros = [_registro_os(item) for item in equipamentos]
    registros.extend(_registro_atendimento(item) for item in atendimentos)
    registros.extend(_registro_chamado(item) for item in chamados)
    if not registros:
        st.info("Nenhuma O.S., atendimento ou chamado encontrado para montar o quadro.")
        return

    k1, k2, k3 = st.columns([2, 1, 1])
    busca = k1.text_input("Buscar cliente, O.S., item, equipamento ou série:").strip().casefold()
    origem_filtro = k2.selectbox(
        "Origem:", ["Todos", "Ordem de Serviço", "Atendimento", "Chamado"],
        key="kanban_filtro_origem",
    )
    apenas_meus = k3.checkbox("Somente atribuídos a mim")
    origem_codigo = {
        "Ordem de Serviço": "os",
        "Atendimento": "atendimento",
        "Chamado": "chamado",
    }.get(origem_filtro)
    if origem_codigo:
        registros = [item for item in registros if item.get("_origem_codigo") == origem_codigo]
    if busca:
        registros = [
            item for item in registros
            if busca in " ".join(str(valor or "") for valor in item.values()).casefold()
        ]
    if apenas_meus:
        usuario = (st.session_state.get("funcionario_nome") or st.session_state.get("username") or "").casefold()
        registros = [item for item in registros if usuario in str(item.get("_responsavel") or "").casefold()]
    if not registros:
        st.info("Nenhum registro corresponde aos filtros selecionados.")
        return

    totais = {
        status: sum(1 for item in registros if (item.get("kanban_status") or "Recebido") == status)
        for status in STATUS_KANBAN_OS
    }
    metricas = st.columns(len(STATUS_KANBAN_OS))
    for coluna, status in zip(metricas, STATUS_KANBAN_OS):
        coluna.metric(status, totais[status])

    pode_editar = tem_permissao("recepcao.edit")
    quadro, cartao_para_chave = montar_quadro_registros(registros)
    if pode_editar:
        st.caption("Arraste um cartão para mudar a etapa. A alteração é salva automaticamente no banco.")
    else:
        st.info("Seu usuário pode consultar o quadro, mas não possui permissão para mover equipamentos.")
    evento = quadro_interativo(
        quadro, CORES_KANBAN_OS, pode_editar=pode_editar,
        key="recepcao_kanban_interativo_v3", retornar_evento=True,
    )
    evento_novo = bool(
        evento
        and evento.get("evento_id")
        and evento.get("evento_id") != st.session_state.get("kanban_ultimo_evento_id")
    )
    if evento_novo:
        st.session_state["kanban_ultimo_evento_id"] = evento.get("evento_id")
    if evento_novo and evento.get("acao") == "abrir":
        chave_ativa = cartao_para_chave.get(evento.get("cartao"))
        if chave_ativa:
            st.session_state["kanban_registro_ativo"] = chave_ativa
    if pode_editar and evento_novo and evento.get("acao") == "mover":
        alteracoes = alteracoes_do_quadro_registros(
            evento.get("colunas"), registros, cartao_para_chave,
        )
        if alteracoes:
            _salvar_alteracoes_quadro(alteracoes)
            st.toast(f"{len(alteracoes)} alteração(ões) salva(s) no Kanban.", icon="✅")
            st.rerun()

    st.divider()
    _renderizar_detalhes_registro(registros, pode_editar, valor_arquivado)

    equipamentos_visiveis = [
        item for item in registros if item.get("_origem_codigo") == "os"
    ]
    if not equipamentos_visiveis:
        return
    st.subheader("Impressão de etiqueta da O.S.")
    equipamentos_por_rotulo = {
        f"OS #{int(item.get('os_id') or 0):05d} · {item.get('numero_item')} · {item.get('cliente') or 'Cliente'}": item
        for item in equipamentos_visiveis
    }
    rotulo_selecionado = st.selectbox("Selecionar equipamento:", list(equipamentos_por_rotulo))
    item_selecionado = equipamentos_por_rotulo[rotulo_selecionado]
    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Etapa atual", item_selecionado.get("kanban_status") or "Recebido")
    d2.write(f"**Equipamento:** {item_selecionado.get('equipamento') or 'Não informado'}")
    d3.write(f"**Série/patrimônio:** {item_selecionado.get('numero_serie') or 'Não informado'}")
    d4.write(f"**Técnico:** {item_selecionado.get('atendente') or item_selecionado.get('tecnico_extra') or 'Não definido'}")
    renderizar_etiquetas_os(st, [item_selecionado], config_sistema_val, APP_BASE_URL, "kanban_etiqueta")


def _renderizar_ficha_qr():
    alvo = alvo_qr_equipamento({chave: obter_query_param(chave) for chave in ("pagina", "equipamento_id", "os", "item")})
    if not alvo:
        return False
    # Chamado somente depois da autenticação e de recepcao.view, inclusive para arquivados.
    conn = conectar_banco()
    try:
        item = buscar_equipamento_qr(conn.cursor(), alvo)
    finally:
        conn.close()
    st.subheader("Ficha do equipamento da etiqueta")
    st.caption("Dados consultados agora no sistema. Editar o serviço não altera o QR já impresso.")
    if st.button("Atualizar ficha", key="qr_os_atualizar"):
        st.rerun()
    if item:
        registro = _registro_os(item)
        st.session_state["kanban_registro_ativo"] = registro["_chave"]
        _renderizar_detalhes_registro([registro], tem_permissao("recepcao.edit"), int(item.get("kanban_arquivado") or 0), ficha_qr=True)
    else:
        st.warning("Este equipamento não foi encontrado. Ele pode ter sido excluído; confira a O.S. com a recepção.")
    if st.button("Voltar ao quadro da recepção", key="qr_os_voltar"):
        for chave in ("pagina", "equipamento_id", "os", "item", "cliente", "equipamento", "serie", "chamado"):
            if chave in st.query_params:
                del st.query_params[chave]
        st.session_state.pop("qr_os_aberto", None)
        st.session_state.pop("kanban_registro_ativo", None)
        st.rerun()
    return True


def _salvar_alteracoes_quadro(alteracoes: list[dict]) -> None:
    usuario = st.session_state.get("username", "")
    momento = agora_br()
    conn = conectar_banco()
    c = conn.cursor()
    tabelas = {
        "os": "equipamentos_os",
        "atendimento": "atendimentos_checklist",
        "chamado": "chamados_cliente",
    }
    try:
        for alteracao in alteracoes:
            tabela = tabelas.get(alteracao.get("origem"))
            if not tabela:
                continue
            c.execute(
                f"""UPDATE {tabela}
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
            tabela = tabelas.get(alteracao.get("origem"))
            if not tabela:
                continue
            registrar_evento_sistema(
                "Movimentação Kanban",
                tabela,
                alteracao["id"],
                "",
                {"de": alteracao["status_anterior"], "para": alteracao["status"]},
            )


def _garantir_estrutura_kanban() -> None:
    """Aplica a evolução mínima mesmo quando o Streamlit ainda está aberto."""
    conn = conectar_banco()
    c = conn.cursor()
    try:
        alterou = False
        for tabela in ("equipamentos_os", "atendimentos_checklist", "chamados_cliente"):
            for coluna, tipo in (
                ("kanban_status", "VARCHAR(60) DEFAULT 'Recebido'"),
                ("kanban_ordem", "INTEGER DEFAULT 0"),
                ("kanban_alterado_por", "TEXT"),
                ("kanban_alterado_em", "TEXT"),
                ("kanban_arquivado", "INTEGER DEFAULT 0"),
            ):
                alterou = garantir_coluna(c, tabela, coluna, tipo) or alterou
        if alterou:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _registro_os(item: dict) -> dict:
    registro = dict(item)
    registro.update({
        "_origem": "O.S.",
        "_origem_codigo": "os",
        "_registro_id": int(item.get("id") or 0),
        "_chave": f"os:{int(item.get('id') or 0)}",
        "_cliente": item.get("cliente") or "Cliente não informado",
        "_titulo": item.get("equipamento") or item.get("tipo_equipamento") or "Equipamento",
        "_complemento": f"OS #{int(item.get('os_id') or 0):05d} · {item.get('numero_item') or ''}",
        "_responsavel": f"{item.get('atendente') or ''} {item.get('tecnico_extra') or ''}",
    })
    return registro


def _registro_atendimento(item: dict) -> dict:
    registro = dict(item)
    registro.update({
        "_origem": "Atendimento",
        "_origem_codigo": "atendimento",
        "_registro_id": int(item.get("id") or 0),
        "_chave": f"atendimento:{int(item.get('id') or 0)}",
        "_cliente": item.get("cliente") or "Cliente não informado",
        "_titulo": item.get("equipamento") or item.get("tipo_atendimento") or "Atendimento",
        "_complemento": f"{item.get('tipo_atendimento') or 'Atendimento'} · {item.get('status') or 'Em aberto'}",
        "_responsavel": f"{item.get('tecnicos') or ''} {item.get('funcionario_atendido') or ''}",
    })
    return registro


def _registro_chamado(item: dict) -> dict:
    registro = dict(item)
    registro.update({
        "_origem": "Chamado",
        "_origem_codigo": "chamado",
        "_registro_id": int(item.get("id") or 0),
        "_chave": f"chamado:{int(item.get('id') or 0)}",
        "_cliente": item.get("cliente_nome") or "Cliente não informado",
        "_titulo": item.get("titulo") or "Chamado sem assunto",
        "_complemento": f"{item.get('area_destino') or 'Suporte'} · {item.get('status') or 'Novo'}",
        "_responsavel": f"{item.get('funcionario_designado') or ''} {item.get('administrador') or ''}",
    })
    return registro


def _renderizar_detalhes_registro(
    registros: list[dict], pode_editar: bool = False, arquivados: int = 0, ficha_qr: bool = False
) -> None:
    chave = st.session_state.get("kanban_registro_ativo")
    registro = next((item for item in registros if item.get("_chave") == chave), None)
    if not registro:
        st.caption("Clique em um cartão para visualizar todas as informações do lançamento.")
        return

    st.subheader(f"Detalhes — {registro.get('_origem')} #{registro.get('_registro_id')}")
    with st.container(border=True):
        d1, d2, d3 = st.columns(3)
        d1.write(f"**Cliente:** {registro.get('_cliente') or 'Não informado'}")
        d2.write(f"**Etapa do Kanban:** {registro.get('kanban_status') or 'Recebido'}")
        d3.write(f"**Responsável:** {registro.get('_responsavel') or 'Não definido'}")
        origem = registro.get("_origem_codigo")
        if origem == "os":
            st.write(f"**O.S.:** #{int(registro.get('os_id') or 0):05d} — item {registro.get('numero_item') or ''}")
            st.write(f"**Equipamento:** {registro.get('tipo_equipamento') or ''} {registro.get('equipamento') or ''}")
            st.write(f"**Marca / série:** {registro.get('marca') or ''} / {registro.get('numero_serie') or 'Não informada'}")
            st.write(f"**Avaria/defeito:** {registro.get('avaria') or ''} {registro.get('defeito') or ''}")
            st.markdown("**O que fazer neste equipamento:**")
            st.text(servicos_equipamento(registro))
            if pode_editar:
                with st.expander("Editar serviço a fazer"):
                    with st.form(f"kanban_servico_{registro['_registro_id']}"):
                        novo_servico = st.text_area("Serviço / instruções para este item:", value=registro.get("servico") or registro.get("defeito") or "")
                        st.caption("Os indicadores de formatação, backup e aplicativos continuam sendo os do cadastro do equipamento.")
                        salvar = st.form_submit_button("Salvar instruções do equipamento")
                    if salvar:
                        conn_srv = conectar_banco()
                        try:
                            conn_srv.cursor().execute(
                                "UPDATE equipamentos_os SET servico=?, kanban_alterado_por=?, kanban_alterado_em=? WHERE id=?",
                                (novo_servico.strip(), st.session_state.get("username", ""), agora_br(), registro["_registro_id"]),
                            )
                            conn_srv.commit()
                        except Exception:
                            conn_srv.rollback()
                            raise
                        finally:
                            conn_srv.close()
                        st.toast("Instruções salvas. O mesmo QR abre o serviço atualizado.")
                        st.rerun()
            if registro.get("chamado_id"):
                st.write(f"**Chamado vinculado:** #{registro.get('chamado_id')}")
        elif origem == "atendimento":
            st.write(f"**Tipo:** {registro.get('tipo_atendimento') or 'Não informado'}")
            st.write(f"**Equipamento:** {registro.get('equipamento') or 'Não informado'}")
            st.write(f"**Funcionário atendido:** {registro.get('funcionario_atendido') or 'Não informado'}")
            st.write(f"**Técnico(s):** {registro.get('tecnicos') or 'Não informado'}")
            st.write(f"**Data de entrada:** {registro.get('data_entrada') or 'Não informada'}")
            st.write(f"**Status do atendimento:** {registro.get('status') or 'Não informado'}")
            st.write(f"**Observações:** {registro.get('detalhes_realizado') or registro.get('obs_entrada') or 'Nenhuma'}")
        else:
            st.write(f"**Assunto:** {registro.get('titulo') or 'Sem assunto'}")
            st.write(f"**Status do chamado:** {registro.get('status') or 'Novo'}")
            st.write(f"**Área:** {registro.get('area_destino') or 'Suporte'}")
            st.write(f"**Solicitante:** {registro.get('solicitante') or 'Não informado'}")
            st.write(f"**Descrição:** {registro.get('ajuste_descricao') or registro.get('descricao') or 'Não informada'}")
            st.write(f"**Data/horário:** {registro.get('ajuste_data') or registro.get('data_solicitada') or ''} {registro.get('ajuste_hora_inicio') or registro.get('hora_inicio') or ''}")
        if pode_editar:
            tabelas = {
                "os": "equipamentos_os", "atendimento": "atendimentos_checklist",
                "chamado": "chamados_cliente",
            }
            tabela = tabelas.get(registro.get("_origem_codigo"))
            pode_arquivar = arquivados or (registro.get("kanban_status") == "Entregue")
            if tabela and pode_arquivar:
                rotulo = "Restaurar item no quadro" if arquivados else "Arquivar e retirar da coluna Entregue"
                if st.button(rotulo, type="primary", key=f"kanban_arquivar_{chave}"):
                    conn_arq = conectar_banco(); c_arq = conn_arq.cursor()
                    c_arq.execute(
                        f"UPDATE {tabela} SET kanban_arquivado=?, kanban_alterado_por=?, kanban_alterado_em=? WHERE id=?",
                        (0 if arquivados else 1, st.session_state.get("username", ""), agora_br(), registro.get("_registro_id")),
                    )
                    conn_arq.commit(); conn_arq.close()
                    st.session_state["kanban_registro_ativo"] = None
                    st.toast("Item restaurado no quadro." if arquivados else "Item entregue arquivado.")
                    st.rerun()
        if not ficha_qr and st.button("Fechar detalhes", key=f"kanban_fechar_{chave}"):
            st.session_state["kanban_registro_ativo"] = None
            st.rerun()
