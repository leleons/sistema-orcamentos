"""Painel de consultas reais. O timer lê apenas o cache local, nunca o banco Inter."""
from datetime import date, datetime, timedelta
from decimal import Decimal
from html import escape

import pandas as pd
import streamlit as st

from dsystem_erp.services.inter_painel import (
    BRASILIA, PainelInter, agora_utc, carregar_usuario, proxima_atualizacao, reais, slot_atual,
)


def _cartao(titulo, valor, detalhe, cor):
    st.markdown(f'''<div style="border:1px solid #69758655;border-top:3px solid {cor};
        border-radius:14px;padding:22px 24px;background:var(--secondary-background-color)">
        <div style="font-size:14px;opacity:.8">{escape(titulo)}</div>
        <div style="font-size:clamp(25px,2.8vw,38px);font-weight:700;margin:8px 0">{escape(valor)}</div>
        <div style="font-size:12px;opacity:.7">{escape(detalhe)}</div></div>''', unsafe_allow_html=True)


@st.fragment(run_every='60s')
def renderizar_painel(repo, consultas, empresa, nome_empresa, prefixo, acao, conectar_erp=None):
    # Sessão e permissões são relidas em cada atualização do fragmento.
    usuario = dict(st.session_state)
    painel = PainelInter(repo, consultas, obter_usuario=lambda nome: carregar_usuario(nome, conectar_erp))
    resultado = acao(lambda: painel.ler(empresa, usuario))
    if resultado is None:
        return
    titulo, atualizar = st.columns([3, 1], vertical_alignment='center')
    with titulo:
        st.subheader('Saldo e transações')
        st.caption(f'{nome_empresa} · Conta real · Somente leitura')
    with atualizar:
        clicou = st.button('Atualizar agora', key=prefixo+'saldo_real', type='primary', use_container_width=True)
    if clicou:
        with st.spinner('Consultando saldo e todas as páginas do extrato…'):
            status = acao(lambda: painel.atualizar(empresa, usuario))
        if status == 'em_andamento':
            st.info('Uma atualização já está em andamento. Aguarde a conclusão.')
        elif status == 'atualizado':
            st.success('Saldo e transações atualizados.')
        resultado = acao(lambda: painel.ler(empresa, usuario))
        if resultado is None:
            return
    agora = agora_utc()
    dados = resultado['dados']
    if resultado['agenda_ativa']:
        proxima = proxima_atualizacao(agora).strftime('%d/%m às %H:%M')
        st.caption(f'Automático às 08:00 e 12:00 (Brasília) · Próxima: {proxima} · Computador ligado, usuário Windows conectado e MySQL ativo.')
    else:
        st.caption('Horários previstos: 08:00 e 12:00 (Brasília). Agendador desta instalação ainda não ativado; atualização manual disponível.')
    if not dados:
        st.info('Sua conta está pronta para consulta. Clique em Atualizar agora para carregar o saldo e as transações dos últimos 30 dias.')
        if resultado['erro']:
            st.warning('A última tentativa de atualização falhou. Verifique a conexão e a configuração da conta.')
        return
    atualizado = datetime.fromisoformat(dados['atualizado_em']).astimezone(BRASILIA)
    st.caption('Última consulta completa: ' + atualizado.strftime('%d/%m/%Y às %H:%M') + ' (Brasília). O saldo não é em tempo real.')
    ultimo_slot = slot_atual(agora)
    atrasado = resultado['agenda_ativa'] and ultimo_slot and atualizado < datetime.fromisoformat(ultimo_slot).replace(tzinfo=BRASILIA) and agora.astimezone(BRASILIA) > datetime.fromisoformat(ultimo_slot).replace(tzinfo=BRASILIA) + timedelta(minutes=20)
    if resultado['erro'] or atrasado or agora - atualizado > timedelta(days=1):
        st.warning('A atualização mais recente está pendente ou falhou. Estes são os últimos dados completos salvos; use Atualizar agora para tentar novamente.')
    transacoes = dados['transacoes']
    entradas = sum((Decimal(t['valor']) for t in transacoes if t['direcao'] == 'Entrada'), Decimal(0))
    saidas = sum((Decimal(t['valor']) for t in transacoes if t['direcao'] == 'Saída'), Decimal(0))
    periodo = f"{date.fromisoformat(dados['inicio']):%d/%m} a {date.fromisoformat(dados['fim']):%d/%m/%Y}"
    saldo_col, entradas_col, saidas_col = st.columns([1.3, 1, 1])
    with saldo_col:
        _cartao('SALDO DISPONÍVEL', reais(dados['saldo']), 'Conta corrente · Banco Inter', '#ff7a00')
    with entradas_col:
        _cartao('ENTRADAS NO PERÍODO', reais(entradas), periodo, '#25b982')
    with saidas_col:
        _cartao('SAÍDAS NO PERÍODO', reais(saidas), periodo, '#e66b6b')
    if dados.get('referencia_saldo'):
        st.caption('Data de referência do saldo informada pelo Inter: ' + str(dados['referencia_saldo']))
    st.markdown('#### Transações')
    st.caption(f'{len(transacoes)} movimentações · Extrato completo de {periodo} · Filtros abaixo alteram somente a lista.')
    busca_col, tipo_col, periodo_col = st.columns([2, 1, 1])
    with busca_col:
        busca = st.text_input('Buscar transação', placeholder='Descrição ou tipo da movimentação', key=prefixo+'busca').strip().casefold()
    with tipo_col:
        tipo = st.selectbox('Movimentação', ['Todas', 'Entrada', 'Saída'], key=prefixo+'direcao')
    with periodo_col:
        intervalo = st.selectbox('Período da lista', ['Últimos 30 dias', 'Últimos 7 dias', 'Hoje'], key=prefixo+'periodo_lista')
    dias = {'Últimos 30 dias': 29, 'Últimos 7 dias': 6, 'Hoje': 0}[intervalo]
    limite = (agora.astimezone(BRASILIA).date() - timedelta(days=dias)).isoformat()
    selecionadas = [t for t in transacoes if t['data'] >= limite and (tipo == 'Todas' or t['direcao'] == tipo)
                   and (not busca or busca in (t['descricao']+' '+t['tipo']).casefold())]
    if not selecionadas:
        st.info('Nenhuma transação neste período ou com os filtros selecionados.')
    else:
        df = pd.DataFrame([{'Data': date.fromisoformat(t['data']), 'Descrição': t['descricao'],
                            'Tipo': t['tipo'], 'Movimentação': t['direcao'],
                            'Valor': ('+ ' if t['direcao'] == 'Entrada' else '− ') + reais(t['valor'])}
                           for t in selecionadas])
        st.dataframe(df, hide_index=True, use_container_width=True,
                     column_config={'Data': st.column_config.DateColumn(format='DD/MM/YYYY'),
                                    'Descrição': st.column_config.TextColumn(width='large')})
    st.caption('Pagamentos, transferências, cobranças e baixas continuam bloqueados. Nenhum lançamento financeiro é alterado por esta tela.')
