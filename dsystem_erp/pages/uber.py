from dsystem_erp.app_context import aplicar_contexto_pagina
from dsystem_erp.repositories.uber import TIPOS_CORRIDA, garantir_tabelas_uber, listar_corridas, salvar_corrida
from dsystem_erp.ui_consulta import tabela_clicavel_id
from dsystem_erp.utils.datas import agora_sao_paulo, parse_data_flex


def renderizar_uber(ctx):
    aplicar_contexto_pagina(ctx, globals())
    if not tem_permissao('uber.view'):
        st.error('Você não possui permissão para consultar as corridas.')
        return
    if not st.session_state.get('uber_schema_verificado'):
        conn = conectar_banco()
        try:
            garantir_tabelas_uber(conn.cursor())
            conn.commit()
        finally:
            conn.close()
        st.session_state['uber_schema_verificado'] = True
    st.title('Utilização de Uber')
    st.caption('Controle interno de corridas: uma corrida pode atender vários clientes. O valor é registrado uma única vez, sem rateio automático.')
    mensagem = st.session_state.pop('uber_mensagem', None)
    if mensagem:
        st.success(mensagem)
    clientes = {int(c['id']): c['nome'] for c in buscar_clientes()}
    corridas = listar_corridas(conectar_banco)
    corridas = [r for r in corridas if r['clientes'] and all(int(c['cliente_id']) in clientes for c in r['clientes'])]
    f1, f2 = st.columns([2, 1])
    busca = f1.text_input('Pesquisar cliente, colaborador ou produto:', key='uber_busca').strip().casefold()
    finalidade_filtro = f2.selectbox('Finalidade:', ['Todas'] + list(TIPOS_CORRIDA), key='uber_finalidade_filtro')
    visiveis = [r for r in corridas if (finalidade_filtro == 'Todas' or r['finalidade'] == finalidade_filtro)
                and (not busca or busca in (' '.join(c['cliente_nome'] for c in r['clientes']) + ' ' +
                     ' '.join(r['colaboradores']) + ' ' + str(r.get('produtos') or '')).casefold())]
    m1, m2 = st.columns(2)
    m1.metric('Corridas encontradas', len(visiveis))
    m2.metric('Valor total', formatar_moeda_br(sum(float(r['valor_total']) for r in visiveis if r['status'] != 'Cancelada')))
    linhas = [{'ID': r['id'], 'Data': str(r['data_corrida']), 'Clientes': ', '.join(c['cliente_nome'] for c in r['clientes']),
               'Finalidade': r['finalidade'], 'Colaboradores': ', '.join(r['colaboradores']),
               'Valor total': float(r['valor_total']), 'Produtos': r.get('produtos'), 'Status': r['status']} for r in visiveis]
    versao = st.session_state.get('uber_form_versao', 0)
    selecionado = tabela_clicavel_id(st, linhas, f'uber_grade_{versao}') if linhas else None
    if selecionado:
        st.session_state['uber_editar_id'] = int(selecionado)
        st.session_state['uber_form_versao'] = versao + 1
        st.rerun()
    st.caption('Clique em uma corrida para consultar ou editar.')
    ativo = next((r for r in corridas if r['id'] == st.session_state.get('uber_editar_id')), None)
    if not tem_permissao('uber.edit'):
        if ativo:
            st.write(f"Origem: {ativo.get('origem') or 'Não informada'}")
            st.write(f"Destino: {ativo.get('destino') or 'Não informado'}")
            st.write(f"Observações: {ativo.get('observacoes') or 'Nenhuma'}")
        return
    if st.button('Nova corrida', key='uber_nova'):
        st.session_state['uber_editar_id'] = None
        st.session_state['uber_form_versao'] = versao + 1
        st.rerun()
    st.subheader(f"Editar corrida #{ativo['id']}" if ativo else 'Registrar corrida')
    if not clientes:
        st.info('Cadastre ou solicite acesso a um cliente antes de registrar a corrida.')
        return
    if ativo and ativo['status'] == 'Cancelada':
        st.info('Esta corrida está cancelada e preservada no histórico.')
        return
    dados = ativo or {}
    funcionarios = listar_funcionarios_sistema()
    usuarios = {f['username']: f['label'] for f in funcionarios}
    for nome in dados.get('colaboradores', []):
        usuarios.setdefault(nome, nome)
    with st.form(f"uber_form_{dados.get('id', 'novo')}_{versao}"):
        ids_clientes = st.multiselect('Cliente(s) atendido(s):', list(clientes),
                                     default=[c['cliente_id'] for c in dados.get('clientes', [])],
                                     format_func=lambda id_: f'#{id_} — {clientes[id_]}')
        c1, c2, c3 = st.columns([1, 2, 1])
        data = c1.date_input('Data da corrida:', value=parse_data_flex(dados.get('data_corrida')) or agora_sao_paulo().date(), format='DD/MM/YYYY')
        tipo = c2.selectbox('Utilização:', TIPOS_CORRIDA, index=TIPOS_CORRIDA.index(dados.get('finalidade', TIPOS_CORRIDA[0])))
        valor = c3.number_input('Valor total da corrida (R$):', min_value=0.0, value=float(dados.get('valor_total') or 0), step=1.0, format='%.2f')
        equipe = st.multiselect('Colaborador(es) que acompanharam a corrida:', list(usuarios),
                                default=dados.get('colaboradores', []), format_func=lambda u: usuarios[u])
        st.caption('Obrigatório para entrega acompanhada ou suporte. No envio de produto sozinho, não há acompanhante.')
        produtos = st.text_input('Produto(s) enviado(s)/entregue(s):', value=dados.get('produtos') or '')
        a, b = st.columns(2)
        origem = a.text_input('Origem:', value=dados.get('origem') or '')
        destino = b.text_input('Destino:', value=dados.get('destino') or '')
        observacoes = st.text_area('Observações / serviço realizado:', value=dados.get('observacoes') or '')
        salvar = st.form_submit_button('Salvar corrida', type='primary', width='stretch')
    if salvar:
        try:
            id_salvo = salvar_corrida(conectar_banco, {
                'cliente_ids': ids_clientes, 'data_corrida': data, 'finalidade': tipo,
                'valor_total': valor, 'colaboradores': equipe, 'produtos': produtos,
                'origem': origem, 'destino': destino, 'observacoes': observacoes,
            }, st.session_state.get('username', ''), dados.get('id'), clientes_permitidos=clientes)
        except ValueError as ex:
            st.error(str(ex))
        else:
            st.session_state['uber_editar_id'] = None
            st.session_state['uber_form_versao'] = versao + 1
            st.session_state['uber_mensagem'] = f'Corrida #{id_salvo} salva com sucesso.'
            st.rerun()
