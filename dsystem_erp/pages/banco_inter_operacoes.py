"""Revisão humana de boletos de notas e pagamentos; nenhum envio ao renderizar."""
import streamlit as st

from dsystem_erp.services.inter_producao import hoje, digitos
from dsystem_erp.services.inter_financeiro import dinheiro
from dsystem_erp.services.permissions import usuario_tem_permissao


def configurar_operacoes(repo, empresa, usuario, prefixo, acao, conectar_erp=None):
    from dsystem_erp.services.inter_runtime import configurar_movimentacoes, movimentacao_producao_liberada
    if str(usuario.get('is_admin', 0)).lower() not in ('1', 'true'):
        return
    with st.expander('Habilitar boletos e pagamentos em produção'):
        ativo_atual = acao(lambda: movimentacao_producao_liberada(repo, empresa))
        st.caption('Situação atual: '+('habilitado para operações com aprovação.' if ativo_atual else 'movimentações desativadas.'))
        st.warning('Habilitar não movimenta dinheiro. Cada envio exige aprovação e confirmação. Os escopos também precisam estar habilitados no aplicativo do Inter.')
        with st.form(prefixo+'habilitar', enter_to_submit=False):
            ativo = st.checkbox('Permitir operações reais nesta empresa', value=bool(ativo_atual), key=prefixo+'ativo')
            cobranca = st.checkbox('Emitir e consultar boleto com Pix', value=True)
            pix = st.checkbox('Preparar e enviar pagamentos Pix', value=True)
            boleto = st.checkbox('Pagar e agendar boletos/contas', value=True)
            confirmacao = st.text_input('Digite CONFIGURAR '+str(empresa))
            st.caption('Daniel e os usuários que ele autorizar precisam das permissões Preparar, Aprovar e/ou Executar no Gerenciador de Usuários, além do vínculo com esta empresa. O preparador não aprova o próprio pagamento.')
            if st.form_submit_button('Salvar habilitação — sem realizar transações'):
                escopos = ['extrato.read']
                for sim, base in ((cobranca, 'boleto-cobranca'), (pix, 'pagamento-pix'), (boleto, 'pagamento-boleto')):
                    if sim:
                        escopos.extend([base+'.read', base+'.write'])
                if acao(lambda: configurar_movimentacoes(repo, empresa, usuario, ativo, escopos, confirmacao, conectar_erp=conectar_erp)):
                    st.success('Configuração salva. Nenhuma operação enviada ao banco.')


def preparar_nota(servico, empresa, usuario, faturamento_id, prefixo, acao):
    parcelas = acao(lambda: servico.parcelas(empresa, usuario, faturamento_id))
    if parcelas is None:
        return
    if not parcelas:
        st.info('Nenhuma parcela em aberto disponível para boleto.')
        return
    por_id = {p['origem']['titulo_id']: p for p in parcelas}
    titulo = st.selectbox('Parcela da nota', list(por_id), key=prefixo+'parcela',
                          format_func=lambda i: f"{por_id[i]['origem']['documento']} · R$ {por_id[i]['payload']['valorNominal']:.2f} · {por_id[i]['payload']['dataVencimento']}")
    p = por_id[titulo]
    st.write('Pagador:', p['payload']['pagador']['nome'])
    st.caption('Preparar não emite. Revise e aprove no histórico; depois confirme o envio para emitir no Inter.')
    existente = acao(lambda: servico.localizar(empresa, usuario, 'titulo:contas_receber:'+str(titulo)))
    if existente:
        st.info('Esta parcela já tem uma operação: '+existente['id']+' — '+existente['estado'])
    elif st.button('Preparar boleto desta parcela no Inter', key=prefixo+'preparar'):
        uid = acao(lambda: servico.preparar_parcela(empresa, usuario, faturamento_id, titulo))
        if uid:
            st.success('Preparado para revisão: '+uid)


def preparar_pagamento(servico, empresa, usuario, prefixo, acao):
    tipo = st.selectbox('Forma de pagamento', ['pix_enviar', 'conta_pagar'],
                        format_func=lambda t: 'Pix' if t == 'pix_enviar' else 'Boleto / conta com código de barras', key=prefixo+'tipo_pag')
    with st.form(prefixo+'pagamento', enter_to_submit=False):
        referencia = st.text_input('Referência do pagamento', help='Use o número da conta/fornecedor e competência. Não troque a referência para reenviar uma operação incerta.')
        nome = st.text_input('Nome / razão social do favorecido')
        documento = st.text_input('CPF/CNPJ do favorecido')
        valor = st.text_input('Valor a pagar (R$)', placeholder='150,00')
        pagamento = st.date_input('Pagar em', value=hoje(), min_value=hoje())
        if tipo == 'pix_enviar':
            chave = st.text_input('Chave Pix')
            st.caption('O nome e CPF/CNPJ acima são informados para revisão, não consultados no DICT. Confira a titularidade da chave no banco antes de aprovar.')
        else:
            codigo = st.text_input('Código de barras ou linha digitável')
            vencimento = st.date_input('Vencimento do documento', value=hoje())
        if st.form_submit_button('Preparar pagamento — não enviar'):
            def preparar():
                quantia = dinheiro(valor.replace(',', '.'))
                if tipo == 'pix_enviar':
                    payload = dict(valor=float(quantia), dataPagamento=pagamento.isoformat(), destinatario=dict(tipo='CHAVE', chave=chave.strip()))
                else:
                    payload = dict(valorPagar=quantia, dataPagamento=pagamento.isoformat(), dataVencimento=vencimento.isoformat(),
                                   codBarraLinhaDigitavel=digitos(codigo), cpfCnpjBeneficiario=digitos(documento))
                return servico.preparar_pagamento(empresa, usuario, tipo, payload, referencia, nome, documento)
            uid = acao(preparar)
            if uid:
                st.success('Pagamento preparado para outro usuário aprovar: '+uid)


def renderizar_operacoes(repo, empresa, usuario, prefixo, acao, conectar_erp=None, faturamento_id=None):
    from dsystem_erp.services.inter_runtime import abrir_producao_movimentacao
    from dsystem_erp.pages.banco_inter import _historico
    servico = acao(lambda: abrir_producao_movimentacao(repo, empresa, usuario, conectar_erp=conectar_erp))
    if servico is None:
        return
    try:
        # A sessão pode anteceder uma concessão/revogação feita no Gerenciador de Usuários.
        atual = acao(lambda: servico.carregar_usuario(usuario['username']))
        if atual is None:
            return
        usuario = {**usuario, **atual}
        st.warning('Conta real. Preparar salva para revisão; somente a confirmação de envio chama o banco. Aceito/agendado não significa pago.')
        if usuario_tem_permissao('inter.preparar', usuario):
            if faturamento_id is not None:
                preparar_nota(servico, empresa, usuario, faturamento_id, prefixo+'nota_', acao)
            else:
                nota, pagamento = st.tabs(['Boleto de uma nota', 'Pagamento Pix / boleto'])
                with nota:
                    fat = st.number_input('Número do faturamento com nota autorizada', min_value=1, step=1, key=prefixo+'fat')
                    if st.checkbox('Carregar parcelas deste faturamento', key=prefixo+'carregar'):
                        preparar_nota(servico, empresa, usuario, fat, prefixo+'nota_', acao)
                with pagamento:
                    preparar_pagamento(servico, empresa, usuario, prefixo, acao)
        st.subheader('Revisão, aprovação e histórico')
        acao(lambda: _historico(servico, empresa, usuario, prefixo+'hist_'))
        st.caption('A baixa automática no financeiro de produção ainda não está habilitada. Confira a liquidação no banco antes de baixar no ERP.')
    finally:
        servico.cliente.session.close()


def boletos_no_faturamento(conectar_erp, faturamento, usuario):
    if not usuario_tem_permissao('inter.view', usuario) or 'boleto' not in str(faturamento.get('forma_pag') or '').casefold():
        return
    from dsystem_erp.services.inter_runtime import repositorio_configuracao
    from dsystem_erp.pages.banco_inter import _acao
    with st.expander('Boleto Banco Inter — nota e parcelas', expanded=False):
        if not st.checkbox('Abrir operações bancárias deste faturamento', key=f"inter_fat_abrir_{faturamento['id']}"):
            return
        repo = _acao(repositorio_configuracao)
        if repo is None:
            return
        empresas = _acao(lambda: repo.empresas(usuario['username'])) or []
        if not empresas:
            st.info('Peça ao administrador o vínculo com a empresa bancária.')
            return
        por_id = {e['id']: e for e in empresas}
        empresa = st.selectbox('Empresa que emitiu a nota / conta Inter', list(por_id),
                               format_func=lambda i: por_id[i]['nome'], key=f"inter_fat_empresa_{faturamento['id']}")
        renderizar_operacoes(repo, empresa, usuario, f"inter_fat_{empresa}_{faturamento['id']}_", _acao,
                             conectar_erp=conectar_erp, faturamento_id=faturamento['id'])
