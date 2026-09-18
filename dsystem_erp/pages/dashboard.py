from dsystem_erp.app_context import aplicar_contexto_pagina
from dsystem_erp.services.dashboard import resumo_financeiro, total_saldo, resumo_atendimentos, resumo_orcamentos
from dsystem_erp.utils.datas import agora_sao_paulo


def renderizar_dashboard(ctx):
    aplicar_contexto_pagina(ctx, globals())
    if not tem_permissao('dashboard.view'):
        st.error('Você não tem permissão para acessar o Dashboard.')
        return
    hoje = agora_sao_paulo().date()
    st.title('Dashboard de Gestão')
    st.caption(f'Posição em {hoje:%d/%m/%Y} · Financeiro, atendimentos e orçamentos')
    st.button('Atualizar indicadores', key='dashboard_atualizar')

    def consultar(sql, *campos_empresa):
        conn = conectar_banco()
        try:
            cursor = conn.cursor()
            cursor.execute(sql)
            return filtrar_registros_por_empresa([dict(r) for r in cursor.fetchall()], *campos_empresa)
        finally:
            conn.close()

    st.subheader('Contas a pagar e a receber')
    st.caption('Até 5, 10 e 15 dias são períodos acumulados, incluindo hoje. Vencidos ficam separados. Os valores mostram o saldo após baixas parciais.')
    series = []
    for titulo, tabela, permissao, campo_cliente in (
        ('A pagar', 'contas_pagar', 'financeiro.pagar', 'fornecedor'),
        ('A receber', 'contas_receber', 'financeiro.receber', 'cliente'),
    ):
        if not tem_permissao(permissao):
            st.info(f'{titulo}: indicadores restritos à permissão do módulo financeiro correspondente.')
            continue
        registros = consultar(
            f'SELECT id, {campo_cliente}, numero_documento, data_vencimento, valor_total, valor_baixado, status FROM {tabela}',
            campo_cliente,
        )
        resumo = resumo_financeiro(registros, hoje)
        st.markdown(f'#### {titulo}')
        colunas = st.columns(4)
        grupos = [('Vencidos', resumo['vencidos'])] + [(f'Até {d} dias', resumo['janelas'][d]) for d in (5, 10, 15)]
        for coluna, (rotulo, itens) in zip(colunas, grupos):
            coluna.metric(rotulo, formatar_moeda_br(total_saldo(itens)), help=f'{len(itens)} título(s)')
            series.append({'Prazo': rotulo, 'Tipo': titulo, 'Saldo': float(total_saldo(itens))})
        with st.expander(f'Consultar títulos — {titulo}'):
            opcoes = dict(grupos + [('Todos em aberto', resumo['abertos'])])
            escolha = st.selectbox('Período:', list(opcoes), key=f'dash_periodo_{tabela}')
            linhas = [{'ID': r['id'], 'Cliente/Fornecedor': r.get(campo_cliente),
                       'Documento': r.get('numero_documento'), 'Vencimento': r.get('data_vencimento'),
                       'Saldo': float(r['saldo']), 'Status': r.get('status')} for r in opcoes[escolha]]
            if linhas:
                st.dataframe(linhas, hide_index=True, width='stretch')
            else:
                st.info('Nenhum título neste período.')
        if resumo['sem_data']:
            st.warning(f"{len(resumo['sem_data'])} título(s) {titulo.lower()} sem vencimento válido, fora dos indicadores por prazo.")
    if series:
        import pandas as pd
        comparativo = pd.DataFrame(series).pivot(index='Prazo', columns='Tipo', values='Saldo').fillna(0)
        st.bar_chart(comparativo.reindex(['Vencidos', 'Até 5 dias', 'Até 10 dias', 'Até 15 dias']))

    st.divider()
    st.subheader('Atendimentos e agenda')
    checklists = agendamentos = chamados = []
    if tem_permissao('atendimentos.view'):
        checklists = consultar('SELECT id, cliente, equipamento, status FROM atendimentos_checklist', 'cliente')
        agendamentos = consultar('SELECT id, cliente_nome, descricao, status, data_visita FROM agenda_visitas', 'cliente_nome')
    if tem_permissao('cliente.portal'):
        chamados = consultar('SELECT id, cliente_nome, titulo, status, ajuste_data, data_solicitada FROM chamados_cliente', 'cliente_nome')
    if tem_permissao('atendimentos.view') or tem_permissao('cliente.portal'):
        grupos_atendimento = resumo_atendimentos(checklists, agendamentos, chamados, hoje)
        for coluna, (rotulo, itens) in zip(st.columns(4), grupos_atendimento.items()):
            coluna.metric(rotulo, len(itens))
        st.caption('Em aberto inclui todos os não encerrados. Pendentes inclui novos, agendados e aguardando ação. Vencidos/a vencer usam a data agendada; checklists sem prazo não são classificados por vencimento. Os grupos podem se sobrepor.')
        filtro = st.selectbox('Consultar atendimentos:', list(grupos_atendimento), key='dash_atendimento')
        linhas = [{k: v for k, v in r.items() if not k.startswith('_')} for r in grupos_atendimento[filtro]]
        if linhas:
            st.dataframe(linhas, hide_index=True, width='stretch')
        else:
            st.info('Nenhum atendimento neste grupo.')
    else:
        st.info('Seu usuário não possui acesso aos indicadores de atendimento.')

    st.divider()
    st.subheader('Orçamentos e faturamento')
    if tem_permissao('orcamentos.view'):
        orcamentos = consultar('SELECT orc_id, numero, cliente, valor_total, status, data_orc, data_validade, faturamento_id FROM orcamentos', 'cliente')
        grupos_orcamento = resumo_orcamentos(orcamentos, hoje)
        for coluna, (rotulo, itens) in zip(st.columns(3), grupos_orcamento.items()):
            coluna.metric(rotulo, len(itens))
        st.caption('Cancelados não entram nos indicadores. Vencidos é um subconjunto dos não faturados.')
        filtro = st.selectbox('Consultar orçamentos:', list(grupos_orcamento), key='dash_orcamentos')
        linhas = [{'Número': r.get('numero'), 'Cliente': r.get('cliente'), 'Valor': r.get('valor_total'),
                   'Validade': r.get('data_validade'), 'Status': r.get('status'), 'Faturamento': r.get('faturamento_id')}
                  for r in grupos_orcamento[filtro]]
        if linhas:
            st.dataframe(linhas, hide_index=True, width='stretch')
        else:
            st.info('Nenhum orçamento neste grupo.')
    else:
        st.info('Seu usuário não possui acesso aos indicadores de orçamento.')
