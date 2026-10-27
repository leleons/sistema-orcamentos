"""Interface bancária; consultas e movimentações têm fluxos separados."""
from datetime import date, timedelta
from io import BytesIO
import json
import os
from pathlib import Path
import tempfile

import streamlit as st
from mysql.connector import Error as MySQLError

from dsystem_erp.config import config_val
from dsystem_erp.services.permissions import usuario_tem_permissao
from dsystem_erp.repositories.inter import criar_repositorio_demo
from dsystem_erp.services.inter_api import InterSimulado, InterErro, pdf_da_resposta, OPERACOES
from dsystem_erp.services.inter_financeiro import FinanceiroInter, dinheiro


def _acao(funcao):
    try:
        return funcao()
    except (ValueError, PermissionError, InterErro) as erro:
        st.error(str(erro))
    except MySQLError as erro:
        if erro.errno in (2002, 2003, 2005, 2006, 2013, 2055):
            st.error('Não foi possível conectar à base de configuração do Inter. Confira se o MySQL está em execução. Se houve tentativa de envio, consulte o histórico/banco antes de repetir.')
        elif erro.errno in (1044, 1045):
            st.error('O MySQL recusou o acesso à base de configuração do Inter. Peça ao administrador para conferir as permissões da conexão nesta instalação.')
        elif erro.errno in (1049, 1146):
            st.error('A base de configuração do Inter ainda não foi preparada nesta instalação. As chaves do computador local não são copiadas automaticamente para o servidor.')
        else:
            st.error('Não foi possível acessar a configuração do Inter nesta instalação. Peça ao administrador para verificar a base isolada da integração.')
    except Exception:
        # Não exibir SQL, credenciais, corpo HTTP ou traceback ao usuário.
        st.error('Operação não concluída. Confira a configuração do ambiente selecionado. Não repita um envio incerto.')
    return None


def _abrir_conta_real(*, configurar=False):
    st.session_state['inter_ambiente'] = (
        'Configurar chaves (sem conexão bancária)' if configurar else 'Produção — somente consultas')
    st.session_state['inter_config_ambiente'] = 'producao'


def _abrir_operacoes_reais():
    st.session_state['inter_ambiente'] = 'Produção — boletos e pagamentos'


def _preparar(servico, empresa, usuario, prefixo):
    st.caption('Preparar apenas salva para revisão. Não envia ao banco.')
    tipo = st.selectbox('Operação', ['pix_enviar', 'pix_receber', 'conta_pagar', 'boleto_emitir'], key=prefixo+'tipo')
    with st.form(prefixo+'nova', enter_to_submit=False):
        referencia = st.text_input('Referência única do lançamento', help='Reutilize a mesma referência para evitar duplicidade.')
        valor = st.text_input('Valor (R$)', value='10.00')
        identificador = None
        if tipo in ('pix_enviar', 'pix_receber'):
            chave = st.text_input('Chave Pix do favorecido' if tipo == 'pix_enviar' else 'Chave Pix recebedora')
            if tipo == 'pix_receber':
                identificador = st.text_input('txid (26 a 35 letras/números)')
            else:
                pagamento = st.date_input('Data de pagamento/agendamento', min_value=date.today())
        else:
            vencimento = st.date_input('Vencimento')
            if tipo == 'conta_pagar':
                codigo = st.text_input('Código de barras ou linha digitável (somente números)')
                pagamento = st.date_input('Data de pagamento/agendamento', min_value=date.today())
            else:
                st.caption('Pagador: utilize dados fictícios no ambiente de teste.')
                numero = st.text_input('Seu número (até 15 caracteres)')
                pagador = {k: st.text_input(rotulo) for k, rotulo in (
                    ('nome', 'Nome / razão social'), ('cpfCnpj', 'CPF/CNPJ do pagador'),
                    ('endereco', 'Endereço'), ('bairro', 'Bairro'), ('cidade', 'Cidade'), ('uf', 'UF'), ('cep', 'CEP'))}
                pagador['tipoPessoa'] = st.selectbox('Tipo de pessoa', ['FISICA', 'JURIDICA'])
        if st.form_submit_button('Preparar para aprovação'):
            def salvar():
                quantia = dinheiro(valor.replace(',', '.'))
                if tipo == 'pix_enviar':
                    payload = {'valor': float(quantia), 'destinatario': {'tipo': 'CHAVE', 'chave': chave}, 'dataPagamento': pagamento.isoformat()}
                elif tipo == 'pix_receber':
                    payload = {'valor': {'original': quantia}, 'chave': chave, 'calendario': {'expiracao': 3600}}
                elif tipo == 'conta_pagar':
                    payload = {'valorPagar': quantia, 'codBarraLinhaDigitavel': codigo, 'dataVencimento': vencimento.isoformat(), 'dataPagamento': pagamento.isoformat()}
                else:
                    payload = {'seuNumero': numero, 'valorNominal': float(quantia), 'dataVencimento': vencimento.isoformat(), 'numDiasAgenda': 30, 'pagador': pagador, 'formasRecebimento': ['BOLETO', 'PIX']}
                return servico.criar(empresa, usuario, tipo, payload, referencia, identificador)
            uid = _acao(salvar)
            if uid:
                st.success('Preparada, sem envio: ' + uid)


def _avancado(servico, empresa, usuario, prefixo):
    st.caption('Homologação técnica: JSON conforme os exemplos da documentação oficial. Todos passam pela aprovação.')
    modo = st.selectbox('Fluxo', ['Folha Pix (lote interno)', 'Boleto mensal', 'Pix Automático', 'Lote de boletos'], key=prefixo+'fluxo')
    with st.form(prefixo+'avancado', enter_to_submit=False):
        ref = st.text_input('Referência estável / contrato')
        competencia = st.text_input('Competência (AAAA-MM)', value=date.today().strftime('%Y-%m')) if modo == 'Boleto mensal' else None
        operacao = st.selectbox('Etapa Pix Automático', ['rec_criar', 'rec_location', 'rec_solicitar', 'rec_cobrar', 'rec_cancelar']) if modo == 'Pix Automático' else None
        identificador = st.text_input('Identificador da recorrência ou txid (quando exigido)') if operacao else None
        texto = st.text_area('Dados JSON', value='[]' if modo.startswith('Folha') else '{}', height=180,
            help='Folha: [{"funcionario_id":1,"payload":{"valor":10,"destinatario":{"tipo":"CHAVE","chave":"chave-ficticia"}}}]')
        if st.form_submit_button('Preparar fluxo para aprovação'):
            def salvar():
                dados = json.loads(texto)
                if modo.startswith('Folha'):
                    return servico.criar_folha_pix(empresa, usuario, ref, dados)
                if modo == 'Boleto mensal':
                    return servico.cobranca_mensal(empresa, usuario, ref, competencia, dados)
                return servico.criar(empresa, usuario, operacao or 'lote_boletos', dados, ref, identificador or None)
            resultado = _acao(salvar)
            if resultado:
                st.success('Preparado; revise no histórico antes de aprovar.')
                st.write(resultado)


def _historico(servico, empresa, usuario, prefixo):
    registros = (servico.listar(empresa, usuario) if servico.ambiente == 'producao'
                 else servico.repo.listar(empresa, servico.ambiente, usuario['username']))
    if not registros:
        st.info('Nenhuma operação neste ambiente e empresa.')
        return
    st.dataframe(registros, hide_index=True)
    uid = st.selectbox('Operação para revisar', [r['id'] for r in registros], key=prefixo+'operacao')
    dados = servico.detalhes(empresa, usuario, uid)
    st.caption(f"Empresa: {empresa} · Operação: {dados['tipo']} · Registro: {uid}")
    if dados.get('identificador'):
        st.write('Identificador bancário solicitado:', dados['identificador'])
    st.write('Estado local: **'+dados['estado']+'**. Enviada não significa liquidada.')
    if servico.ambiente in ('sandbox', 'producao'):
        st.write('Conta de origem:', servico.cliente.credencial.conta or 'Conta única da integração da empresa selecionada')
    if dados.get('contexto'):
        revisao = {k: v for k, v in dados['contexto'].items() if k != 'credencial'}
        st.write('Origem / favorecido informado para revisão:', revisao)
    st.json(dados['payload'])
    if dados['estado'] == 'PENDENTE_APROVACAO' and usuario_tem_permissao('inter.aprovar', usuario):
        st.caption('Pagamentos exigem outro usuário autorizado como aprovador.')
        with st.form(prefixo+uid+'aprovar', enter_to_submit=False):
            confirmacao = st.text_input('Digite CONFIRMAR '+uid)
            if st.form_submit_button('Aprovar dados revisados'):
                def aprovar():
                    servico.aprovar(empresa, usuario, uid, dados['digest'], confirmacao)
                    return True
                if _acao(aprovar):
                    st.rerun()
    if dados['estado'] == 'APROVADA' and usuario_tem_permissao('inter.executar', usuario):
        with st.form(prefixo+uid+'envio', enter_to_submit=False):
            confirmacao_envio = st.text_input('Digite ENVIAR '+uid) if servico.ambiente == 'producao' else None
            if st.form_submit_button('Executar operação aprovada — '+servico.ambiente):
                resultado = _acao(lambda: servico.executar(empresa, usuario, uid,
                    confirmacao=confirmacao_envio, digest=dados['digest']))
                if resultado:
                    st.rerun()
    if st.button('Consultar status no banco / simulador', key=prefixo+'consultar'):
        _acao(lambda: servico.atualizar(empresa, usuario, uid))
        dados = servico.detalhes(empresa, usuario, uid)
    resposta = dados.get('resposta') or {}
    st.json(resposta)
    st.download_button('Baixar registro da consulta (não é comprovante bancário)',
                       json.dumps(resposta, ensure_ascii=False, indent=2), file_name='consulta_inter.json', mime='application/json')
    if isinstance(resposta, dict):
        copia = (resposta.get('pix') or {}).get('pixCopiaECola') if isinstance(resposta.get('pix'), dict) else resposta.get('pixCopiaECola')
        if copia and servico.ambiente in ('sandbox', 'producao'):
            import qrcode
            imagem = BytesIO()
            qrcode.make(copia).save(imagem, format='PNG')
            st.code(copia)
            st.image(imagem.getvalue(), width=240)
    if dados['tipo'] == 'boleto_emitir' and dados['externo']:
        if st.button('Obter PDF do boleto', key=prefixo+'pdf'):
            pdf = _acao(lambda: pdf_da_resposta(servico.consultar(empresa, usuario, 'boleto_pdf', identificador=dados['externo'])))
            if pdf:
                st.download_button('Baixar PDF retornado pelo Inter', pdf, file_name='boleto_inter.pdf', mime='application/pdf', on_click='ignore')
    if servico.repo.financeiro_teste and usuario_tem_permissao('inter.conciliar', usuario):
        from dsystem_erp.services.inter_conciliacao import vincular_titulo, conciliar_operacao
        titulo = st.number_input('ID do título na base de teste (empresa previamente validada)', min_value=1, step=1)
        if st.button('Vincular título de teste', key=prefixo+'vincular'):
            _acao(lambda: vincular_titulo(servico, empresa, usuario, uid, titulo))
        if st.button('Consultar liquidação e conciliar', key=prefixo+'conciliar'):
            st.write(_acao(lambda: conciliar_operacao(servico, empresa, usuario, uid)))


def _configurar_chaves(repo, empresa, usuario, prefixo, *, ambiente='sandbox', conectar_erp=None):
    if not usuario_tem_permissao('inter.configurar', usuario):
        st.error('Peça ao administrador a permissão inter.configurar.')
        return
    from dsystem_erp.services.inter_runtime import salvar_credencial_upload, status_configuracao, ler_zip_certificado
    st.subheader('Chaves e certificados do Banco Inter')
    status = _acao(lambda: status_configuracao(repo, empresa, usuario, ambiente=ambiente))
    if ambiente == 'producao':
        from dsystem_erp.pages.banco_inter_operacoes import configurar_operacoes
        configurar_operacoes(repo, empresa, usuario, prefixo, _acao, conectar_erp)
        if conectar_erp and str(usuario.get('is_admin', 0)).lower() in ('1', 'true'):
            from dsystem_erp.services.inter_acessos import listar_acessos, salvar_acessos
            with st.expander('Autorizar outros usuários a consultar esta empresa'):
                st.caption('Marque as permissões Banco Inter no Gerenciador de Usuários e vincule a empresa aqui. Consultar banco sozinho não permite preparar, aprovar ou executar pagamentos.')
                acessos = _acao(lambda: listar_acessos(repo, empresa, usuario, conectar_erp))
                if acessos:
                    elegiveis, atuais = acessos
                    escolhidos = st.multiselect('Usuários com acesso a esta empresa', elegiveis,
                        default=[v for v in atuais if v in elegiveis], key=prefixo+'acessos')
                    if st.button('Salvar acessos de consulta', key=prefixo+'salvar_acessos'):
                        if _acao(lambda: salvar_acessos(repo, empresa, usuario, conectar_erp, escolhidos)):
                            st.success('Acessos atualizados. O administrador atual mantém seu acesso.')
        st.info('Este formulário cadastra chaves para saldo e extrato. Para autorizar boletos e pagamentos com as mesmas chaves, use Habilitar boletos e pagamentos acima. Salvar não chama o banco.')
        from dsystem_erp.services.inter_pendente import existe_pendente, importar_pendente
        if existe_pendente() and not (status and status['configurada']):
            st.caption('Existe um pacote local protegido, preparado neste Windows. Ele ainda não foi vinculado a nenhuma empresa.')
            confirma = st.checkbox('Confirmo que as credenciais locais pertencem à empresa selecionada', key=prefixo+'confirmar_local')
            if st.button('Cadastrar credenciais locais protegidas nesta empresa', disabled=not confirma, key=prefixo+'importar_local'):
                if _acao(lambda: importar_pendente(repo, empresa, usuario)):
                    st.success('Credenciais cadastradas para consultas. Nenhum pagamento autorizado.')
    else:
        st.info('Ambiente: homologação (sandbox). Salvar não conecta ao banco e não ativa pagamentos. Não use credenciais de produção nesta etapa.')
    if status and status['configurada']:
        conta = 'Conta final '+status['conta_final'] if status['conta_final'] else 'Conta única da integração (sem número informado)'
        st.success('Configuração salva para esta empresa. '+conta+'. Os segredos não são exibidos novamente.')
        st.caption('Para substituir, envie todos os campos e arquivos novamente. Operações pendentes impedem a troca.')
    else:
        st.caption('Esta empresa ainda não possui configuração salva.')
    formato = st.radio('Formato dos certificados', ['ZIP do Inter', 'Arquivos separados'], key=prefixo+'formato')
    with st.form(prefixo+'credencial', enter_to_submit=False, clear_on_submit=True):
        valores = {k: st.text_input(rotulo, type='password' if k in ('client_id','client_secret') else 'default') for k, rotulo in (
            ('conta', 'Conta corrente (opcional se a integração tem somente uma conta)'),
            ('client_id', 'Client ID do Banco Inter'), ('client_secret', 'Client Secret do Banco Inter'))}
        pacote = certificado = chave = None
        if formato == 'ZIP do Inter':
            pacote = st.file_uploader('ZIP de chave e certificado baixado no Inter', type=['zip'], key=prefixo+'zip_upload')
        else:
            certificado = st.file_uploader('Certificado do Inter (.crt ou .pem)', type=['crt','pem','cer'], key=prefixo+'certificado_upload')
            chave = st.file_uploader('Chave privada do Inter (.key ou .pem)', type=['key','pem'], key=prefixo+'chave_upload')
        st.caption('ZIP até 512 KB; certificado e chave PEM até 128 KB cada. Para múltiplas contas, informe o número com dígito e sem zeros iniciais.')
        if ambiente == 'producao':
            valores['escopos'] = ['extrato.read']
            st.caption('Permissão solicitada ao Inter: extrato.read. Nenhum escopo de pagamento será utilizado.')
        else:
            valores['escopos'] = st.multiselect('Permissões habilitadas na integração do Inter (escopos)', sorted({o[2] for o in OPERACOES.values()}))
        rotulo_salvar = ('Salvar chaves para consultas reais — pagamentos bloqueados'
                         if ambiente == 'producao' else 'Salvar chaves com segurança — sem ativar integração')
        if st.form_submit_button(rotulo_salvar):
            def salvar():
                if pacote is not None:
                    cert_bytes, chave_bytes = ler_zip_certificado(pacote.getvalue())
                    return salvar_credencial_upload(repo, empresa, usuario, valores, cert_bytes, chave_bytes, ambiente=ambiente)
                if certificado is None or chave is None:
                    raise ValueError('Envie o ZIP ou o certificado e a chave privada.')
                if certificado.size > 131072 or chave.size > 131072:
                    raise ValueError('Cada arquivo deve ter no máximo 128 KB.')
                return salvar_credencial_upload(repo, empresa, usuario, valores, certificado.getvalue(), chave.getvalue(), ambiente=ambiente)
            if _acao(salvar):
                if ambiente == 'producao':
                    st.success('Chaves salvas para consultas reais. Clique em Acessar conta real e depois em Atualizar agora. Pagamentos continuam bloqueados; nenhuma chamada ao banco foi feita ao salvar.')
                else:
                    st.success('Chaves sandbox salvas com segurança. Nenhuma operação enviada ao banco.')


def renderizar_banco_inter(ctx=None):
    usuario = dict(st.session_state)
    if not usuario.get('autenticado') or not usuario_tem_permissao('inter.view', usuario):
        st.error('Acesso bancário exige permissão explícita inter.view.')
        return
    st.title('Banco Inter')
    with st.expander('Configuração da conta e ambientes de teste', expanded=False):
        st.caption('Saldo e extrato são somente leitura. Boletos e pagamentos reais exigem habilitação, permissões e confirmação. Sandbox exige chaves próprias.')
        st.button('Acessar conta real — saldo e extrato', key='inter_abrir_producao',
              on_click=_abrir_conta_real, type='primary')
        if usuario_tem_permissao('inter.configurar', usuario):
            st.button('Configurar conta real', key='inter_configurar_producao',
                  on_click=_abrir_conta_real, kwargs={'configurar': True})
        modo = st.radio('Ambiente / configuração', ['Produção — somente consultas', 'Produção — boletos e pagamentos', 'Simulação sem rede', 'Sandbox Inter', 'Configurar chaves (sem conexão bancária)'], key='inter_ambiente')
    ambiente_config = 'sandbox'
    if modo == 'Configurar chaves (sem conexão bancária)':
        ambiente_config = st.selectbox('Ambiente das chaves', ['producao', 'sandbox'], format_func=lambda v: 'Produção — conta real, somente consultas' if v == 'producao' else 'Sandbox — testes', key='inter_config_ambiente')
    if modo == 'Simulação sem rede':
        identidade = usuario.get('username', '')
        demo = st.session_state.get('_inter_demo')
        if not demo or demo['usuario'] != identidade:
            pasta = tempfile.TemporaryDirectory(prefix='dsystem_inter_')
            repo = criar_repositorio_demo(Path(pasta.name)/'demo.sqlite', identidade)
            demo = {'usuario': identidade, 'pasta': pasta, 'servico': FinanceiroInter(repo, InterSimulado(), os.urandom(32))}
            st.session_state['_inter_demo'] = demo
        servico = demo['servico']
        repo = servico.repo
        st.caption('Dados fictícios temporários desta sessão. Aprovação por duas pessoas é exercitada nos testes automatizados e na base compartilhada de homologação.')
    else:
        from dsystem_erp.services.inter_runtime import repositorio_teste, repositorio_configuracao, abrir_sandbox
        repo = _acao(repositorio_configuracao if modo.startswith('Produção') or ambiente_config == 'producao' else repositorio_teste)
        if repo is None:
            return
    empresas = _acao(lambda: repo.empresas(usuario['username']))
    if empresas is None:
        return
    if not empresas:
        st.info('Seu login não tem empresa bancária vinculada nesta instalação. O administrador precisa autorizar a empresa e seu acesso. A configuração local não é transferida automaticamente para o servidor.')
        return
    por_id = {e['id']: e for e in empresas}
    empresa = (next(iter(por_id)) if modo == 'Produção — somente consultas' and len(por_id) == 1 else
               st.selectbox('Empresa bancária', list(por_id), format_func=lambda i: por_id[i]['nome'], key='inter_empresa_'+modo))
    prefixo = f'inter_{modo}_{ambiente_config}_{empresa}_'
    if modo == 'Configurar chaves (sem conexão bancária)':
        _configurar_chaves(repo, empresa, usuario, prefixo, ambiente=ambiente_config,
                          conectar_erp=ctx.get('conectar_banco') if ctx else None)
        return
    if modo == 'Produção — boletos e pagamentos':
        from dsystem_erp.pages.banco_inter_operacoes import renderizar_operacoes
        renderizar_operacoes(repo, empresa, usuario, prefixo, _acao,
                             conectar_erp=ctx.get('conectar_banco') if ctx else None)
        return
    if modo == 'Produção — somente consultas':
        st.button('Boletos e pagamentos', key='inter_abrir_operacoes', on_click=_abrir_operacoes_reais)
        from dsystem_erp.services.inter_runtime import ConsultasInterProducao
        from dsystem_erp.pages.banco_inter_painel import renderizar_painel
        identidade = (usuario['username'], config_val('DSYSTEM_INTER_CONFIG_DATABASE', ''))
        cache = st.session_state.get('_inter_consultas_reais')
        if not cache or cache['identidade'] != identidade:
            if cache:
                cache['servico'].fechar()
            cache = {'identidade': identidade, 'servico': ConsultasInterProducao(repo)}
            st.session_state['_inter_consultas_reais'] = cache
        servico = cache['servico']
        renderizar_painel(repo, servico, empresa, por_id[empresa]['nome'], prefixo, _acao,
                         conectar_erp=ctx.get('conectar_banco') if ctx else None)
        return
    if modo == 'Sandbox Inter':
        st.caption('Para cadastrar credenciais sem conectar ao banco, selecione Configurar chaves acima.')
        servico = _acao(lambda: abrir_sandbox(repo, empresa, usuario))
        if servico is None:
            return
    painel, nova, avancado, historico = st.tabs(['Saldo e extrato', 'Nova operação', 'Folha e recorrências', 'Aprovação e histórico'])
    with painel:
        inicio = st.date_input('Início', date.today()-timedelta(days=7), key=prefixo+'inicio')
        fim = st.date_input('Fim', key=prefixo+'fim')
        pagina = st.number_input('Página do extrato', min_value=0, step=1, key=prefixo+'pagina')
        if st.button('Consultar saldo e extrato', key=prefixo+'saldo'):
            if inicio > fim:
                st.error('Início deve ser anterior ao fim.')
            else:
                st.json(_acao(lambda: servico.consultar(empresa, usuario, 'saldo')) or {})
                st.json(_acao(lambda: servico.consultar(empresa, usuario, 'extrato', params={'dataInicio': inicio.isoformat(), 'dataFim': fim.isoformat(), 'pagina': pagina, 'tamanhoPagina': 50})) or {})
        if repo.financeiro_teste and usuario_tem_permissao('inter.conciliar', usuario):
            if st.button('Sincronizar títulos vinculados (somente teste)', key=prefixo+'sincronizar'):
                from dsystem_erp.services.inter_conciliacao import sincronizar_vinculados
                st.write(_acao(lambda: sincronizar_vinculados(servico, empresa, usuario)))
    with nova:
        if usuario_tem_permissao('inter.preparar', usuario):
            if repo.financeiro_teste and usuario_tem_permissao('inter.conciliar', usuario):
                with st.expander('Preparar usando o financeiro e cadastro existentes (base de teste)'):
                    from dsystem_erp.services.inter_titulos import listar_titulos, dados_do_titulo, preparar_titulo
                    tabela = st.selectbox('Origem', ['contas_pagar','contas_receber'], key=prefixo+'origem')
                    titulos = _acao(lambda: listar_titulos(servico, empresa, usuario, tabela)) or []
                    if titulos:
                        titulo_id = st.selectbox('Título autorizado', [t['id'] for t in titulos], key=prefixo+'titulo')
                        modalidade = st.selectbox('Modalidade', ['pix_enviar','conta_pagar'] if tabela=='contas_pagar' else ['boleto_emitir'], key=prefixo+'modalidade')
                        pagamento = st.date_input('Pagamento do título', min_value=date.today(), key=prefixo+'pagamento_titulo')
                        previa = _acao(lambda: dados_do_titulo(servico, empresa, usuario, tabela, titulo_id, modalidade, pagamento))
                        if previa:
                            st.json(previa)
                            if st.button('Preparar título para aprovação', key=prefixo+'preparar_titulo'):
                                st.write(_acao(lambda: preparar_titulo(servico, empresa, usuario, tabela, titulo_id, modalidade, pagamento)))
                    else:
                        st.caption('Nenhum título aberto com empresa explicitamente validada.')
            _preparar(servico, empresa, usuario, prefixo)
    with avancado:
        if usuario_tem_permissao('inter.preparar', usuario):
            _avancado(servico, empresa, usuario, prefixo)
    with historico:
        _acao(lambda: _historico(servico, empresa, usuario, prefixo))
