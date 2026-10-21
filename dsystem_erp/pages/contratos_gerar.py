"""Geração em PDF e Word de todos os modelos na central de contratos."""
import hashlib
import json
from datetime import date
from dsystem_erp.services.contratos_vigencia import fim_vigencia, preencher_datas_word
from dsystem_erp.services.contratos_word_pdf import gerar_pdf_word
from dsystem_erp.services.contratos_word import gerar_contrato_word, nome_word, MIME_WORD

from dsystem_erp.services.contrato_pdf import gerar_contrato_pdf, caminho_modelo_contrato
from dsystem_erp.services.contratos import salvar_contrato_gerado
from dsystem_erp.services.contratos_modelos import (
    WORD, modelos_disponiveis, abrir_modelo, slots_modelo, preencher_cadastro,
)
from dsystem_erp.services.permissions import usuario_eh_gerencial
from dsystem_erp.services.contratos_pj import MODELO_PJ, eh_pj, cadastro_empresa_pj, cnpj_pj_valido, sincronizar_campo_cadastro


def escolher_data_assinatura(st, inicio, prefixo):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    hoje = datetime.now(ZoneInfo('America/Sao_Paulo')).date()
    modo = st.radio('Data para assinatura:', ['Mesma data do início', 'Hoje', 'Outra data'],
                    horizontal=True, key=prefixo+'_assinatura_modo')
    if modo == 'Hoje':
        assinatura = hoje
    elif modo == 'Outra data':
        assinatura = st.date_input('Data da assinatura:', value=hoje, key=prefixo+'_assinatura_data')
    else:
        assinatura = inicio
    st.caption(f'Data indicada para assinatura: {assinatura:%d/%m/%Y}. A vigência continua contando a partir de {inicio:%d/%m/%Y}. Informe a data correspondente à assinatura; gerar o arquivo não assina o contrato.')
    return assinatura


def renderizar_gerador(ctx, prestador_pj=None):
    st = ctx['st']
    if not ctx['tem_permissao']('contratos.edit'):
        if prestador_pj is not None:
            st.info('Para gerar contratos, solicite a permissão de edição de contratos.')
        return
    pj = prestador_pj is not None
    if pj and (not eh_pj(prestador_pj.get('funcionario_tipo_contrato')) or not usuario_eh_gerencial(st.session_state)):
        st.warning('Este contrato exige um cadastro PJ/terceirizado e acesso gerencial.')
        return
    with st.expander('Preencher contrato de prestação de serviços PJ' if pj else 'Gerar contrato — todos os modelos', expanded=pj):
        tipo = MODELO_PJ if pj else st.selectbox('Modelo de contrato:', modelos_disponiveis(), key='central_contrato_modelo')
        try:
            original = abrir_modelo(tipo) if tipo in WORD else caminho_modelo_contrato(tipo).read_bytes()
        except (OSError, ValueError) as erro:
            st.error(f'Modelo indisponível. Confira a instalação dos arquivos de contratos: {erro}')
            return
        st.download_button('Baixar modelo original', original, file_name=(WORD[tipo] if tipo in WORD else caminho_modelo_contrato(tipo).name), key='central_modelo_original_pj' if pj else 'central_modelo_original')
        clientes = [cadastro_empresa_pj(prestador_pj)] if pj else [dict(c) for c in ctx['buscar_clientes']()]
        funcionario = pj or tipo in ('Corporativo CLT', 'Estágio', MODELO_PJ)
        if funcionario and not pj:
            if not usuario_eh_gerencial(st.session_state):
                st.info('Os dados dos funcionários exigem acesso gerencial.')
                return
            conn = ctx['conectar_banco']()
            try:
                cur = conn.cursor()
                cur.execute('SELECT id, username, funcionario_nome, funcionario_cpf, funcionario_rj, funcionario_endereco, funcionario_telefone, funcionario_email, funcionario_tipo_contrato, funcionario_pj_razao_social, funcionario_pj_cnpj, funcionario_pj_endereco FROM usuarios ORDER BY funcionario_nome')
                registros = cur.fetchall()
                clientes = [dict(cadastro_empresa_pj(r), pessoa_nome=r.get('funcionario_nome') or r.get('username')) for r in registros if eh_pj(r.get('funcionario_tipo_contrato'))] if tipo == MODELO_PJ else [dict(id=r['id'], nome=r.get('funcionario_nome'), cnpj=r.get('funcionario_cpf'),
                                 rg_mei=r.get('funcionario_rj'), endereco=r.get('funcionario_endereco'),
                                 telefone=r.get('funcionario_telefone'), email=r.get('funcionario_email'))
                            for r in registros if r.get('funcionario_nome')]
            finally:
                conn.close()
        por_id = {str(c['id']): c for c in clientes}
        def escolher(label, chave, padrao=''):
            if chave not in st.session_state or st.session_state[chave] not in [''] + list(por_id):
                st.session_state[chave] = padrao if padrao in por_id else ''
            escolhido = st.selectbox(label, [''] + list(por_id),
                format_func=lambda k: f"{por_id[k].get('pessoa_nome') or por_id[k].get('nome')} — {por_id[k].get('cnpj') or ''} (#{k})" if k else 'Selecione um cadastro', key=chave)
            return por_id.get(escolhido, {})
        parte = clientes[0] if pj else escolher('Funcionário:' if funcionario else 'Cliente/fornecedor vinculado ao contrato:', f'central_parte_{tipo}')
        if not parte:
            return
        prefixo = f"central_contrato_{tipo}_{parte['id']}" + ('_pj' if pj else '')
        dados = dict(parte)
        classificacao = 'Funcionário' if funcionario else st.selectbox('Vínculo do documento:', ['Cliente', 'Fornecedor'], key=prefixo+'_vinculo')
        inicio = st.date_input('Data de início do contrato:', value=date.today(), key=prefixo+'_inicio')
        fim = fim_vigencia(inicio)
        dados['data_contrato'] = inicio.strftime('%d/%m/%Y')
        data_assinatura = escolher_data_assinatura(st, inicio, prefixo)
        dados['data_assinatura'] = data_assinatura.strftime('%d/%m/%Y')
        valores = {}
        config = ctx.get('config_sistema_val', lambda chave, padrao='': padrao)
        empresa = dict(id='empresa', nome=config('DSYSTEM_NOME','Dsystem Tecnologia'),
            cnpj=config('NFSE_CNPJ','23524449000154'), endereco=config('DSYSTEM_ENDERECO','Rua Glória, 25'), cidade_estado=config('DSYSTEM_CIDADE_UF','Sabará / MG'),
            responsavel_legal=config('DSYSTEM_REPRESENTANTE_LEGAL',''), cpf_responsavel=config('DSYSTEM_REPRESENTANTE_CPF',''))
        prazo, impressao = 'Determinado', 'Franquia'
        if tipo in WORD:
            por_id['empresa'] = empresa
            st.caption('Selecione as partes nos papéis corretos. Confira representantes e condições; dados ausentes ficam para preenchimento, sem alterar o cadastro.')
            if tipo == MODELO_PJ:
                contratante, contratada = empresa, parte
                st.info(f"Contratante: DSystem | Prestador: {parte.get('responsavel_legal') or parte.get('pessoa_nome') or ''}. Confira abaixo a razão social, o CNPJ e o endereço da empresa contratada, além dos dados de seu representante legal.")
            else:
                contratante = escolher('Contratante / locatária (quem contrata ou aluga):', prefixo + '_contratante', str(parte['id']) if classificacao == 'Cliente' else 'empresa')
                contratada = escolher('Contratada / locadora (quem presta ou fornece):', prefixo + '_contratada', 'empresa' if classificacao == 'Cliente' else str(parte['id']))
            if not contratante or not contratada:
                return
            if contratante['id'] == contratada['id']:
                st.warning('Escolha cadastros diferentes para as duas partes.')
                return
            if parte['id'] not in (contratante['id'], contratada['id']):
                st.warning('O cliente/fornecedor vinculado deve ser uma das partes do contrato.')
                return
            prefixo += f"_{contratante['id']}_{contratada['id']}"
            meses = 12
            if tipo == 'Serviços e Locação de Equipamentos':
                prazo = st.selectbox('Prazo do contrato:', ['Determinado', 'Indeterminado'], key=prefixo+'_prazo')
                if prazo == 'Determinado':
                    meses = int(st.number_input('Prazo em meses:', min_value=1, max_value=1200, value=12, key=prefixo+'_meses'))
                    fim = fim_vigencia(inicio, meses)
                else:
                    fim = None
                impressao = st.selectbox('Regime de impressão:', ['Franquia', 'Fixo sem franquia', 'Contador'], key=prefixo+'_impressao')
                st.caption('O regime selecionado vale para os equipamentos deste contrato; para regimes diferentes, revise as condições antes de assinar.')
            slots = slots_modelo(tipo, prazo, impressao)
            padroes = preencher_cadastro(tipo, slots, contratante, contratada)
            automaticos = preencher_datas_word(tipo, slots, inicio, fim, meses, assinatura=data_assinatura)
            padroes.update(automaticos)
            for slot in slots:
                if slot['token'] in ('[Sua Cidade - Estado]','[Nome da Cidade/Estado]','[Cidade - UF]'):
                    padroes[slot['chave']] = empresa['cidade_estado']
            ultimo = None
            repetidos = {}
            testemunhas = {}
            for slot in slots:
                testemunha = ': _' in slot['token']
                if testemunha:
                    testemunhas.setdefault(slot['paragrafo'], len(testemunhas) + 1)
                if ultimo != slot['paragrafo']:
                    st.caption(slot['contexto'])
                    ultimo = slot['paragrafo']
                if tipo == MODELO_PJ and not testemunha and slot['token'] in repetidos:
                    valores[slot['chave']] = repetidos[slot['token']]
                    st.caption(f"{slot['rotulo']}: {valores[slot['chave']]} (mesmo valor informado acima)")
                elif slot['chave'] in automaticos:
                    valores[slot['chave']] = automaticos[slot['chave']]
                    st.caption(f"{slot['rotulo']}: {automaticos[slot['chave']]}")
                else:
                    rotulo = 'CNPJ da empresa prestadora' if tipo == MODELO_PJ and slot['token'] == '[CNPJ da empresa do prestador PJ]' else slot['rotulo']
                    if testemunha:
                        rotulo += f" {testemunhas[slot['paragrafo']]}"
                    chave_campo = prefixo+'_'+slot['chave']
                    sincronizar_campo_cadastro(st.session_state, chave_campo, padroes[slot['chave']])
                    valores[slot['chave']] = st.text_input(rotulo, key=chave_campo,
                        help='Preenchido pelo cadastro; confira ou ajuste apenas para este contrato.' if padroes[slot['chave']] else 'Informação ainda não disponível no cadastro. Complete este campo.')
                repetidos[slot['token']] = valores[slot['chave']]
                if slot['paragrafo'] == (11 if tipo in ('Tecnologia e Infraestrutura', MODELO_PJ) else 18) and slot['token'] in ('[Valor]', '[Valor mensal]', '[0.000,00]'):
                    dados['valor_contrato'] = valores[slot['chave']]
            st.caption('No contrato PJ, a remuneração e o deslocamento são mensais, e as horas por dia são informadas separadamente. Este preenchimento não representa revisão jurídica.' if tipo == MODELO_PJ else 'As cláusulas originais, referências entre colchetes e valores fixos são preservados. Este preenchimento não representa revisão jurídica.')
            faltam = [s['rotulo'] for s in slots if not valores[s['chave']].strip()]
            if tipo == MODELO_PJ:
                doc = next(s for s in slots if s['token'] == '[CNPJ da empresa do prestador PJ]')
                if not cnpj_pj_valido(valores[doc['chave']]):
                    faltam.append('CNPJ da empresa prestadora com 14 posições (não o CPF da pessoa)')
        else:
            campos = [('nome','Nome / razão social'), ('cnpj','CPF/CNPJ'), ('endereco','Endereço'), ('numero','Número'),
                      ('complemento','Complemento'), ('bairro','Bairro'), ('cidade_estado','Cidade / UF'), ('cep','CEP'),
                      ('telefone','Telefone'), ('email','E-mail')]
            if tipo == 'Suporte Tecnológico':
                campos += [('responsavel_legal','Representante legal'), ('cpf_responsavel','CPF do representante'),
                           ('valor_contrato','Valor mensal R$'), ('dia_vencimento','Dia do vencimento'), ('forma_pagamento','Forma de pagamento')]
            elif tipo == 'Corporativo CLT':
                campos += [('rg_mei','RG'), ('cargo','Cargo / função'), ('valor_contrato','Salário R$')]
            else:
                campos += [('instituicao_ensino','Instituição de ensino'), ('curso','Curso')]
                dados['jornada'] = st.selectbox('Jornada semanal:', ['20 horas', '30 horas'], key=prefixo+'_jornada')
            for campo, rotulo in campos:
                dados[campo] = st.text_input(rotulo, value=str(parte.get(campo) or ''), key=prefixo+'_'+campo)
            opcionais = {'complemento', 'numero', 'bairro', 'cep'}
            faltam = [r for k, r in campos if k not in opcionais and not dados[k].strip()]
            # Campos adicionais vêm do próprio formulário oficial do modelo,
            # para nenhum campo preenchível ficar inacessível na central.
            from pypdf import PdfReader
            mapeados = {
                'nome_contratante','cnpj_contratante','endereco_contratante','responsavel_contratante','cpf_responsavel',
                'telefone_contratante','email_contratante','data_inicio','vigencia','dia_vencimento','valor_mensal','forma_pagamento',
                'nome_colaborador','cpf_colaborador','rg_colaborador','cargo_colaborador','endereco_colaborador','telefone_colaborador',
                'email_colaborador','salario_colaborador','nome_estagiario','cpf_estagiario','endereco_estagiario','telefone_estagiario',
                'email_estagiario','instituicao_ensino','curso','jornada_20','jornada_30','data_emissao'}
            with st.expander('Empresa, condições e campos adicionais do contrato', expanded=True):
                st.caption('Preencha o que se aplica. Assinaturas ficam em branco para assinatura das partes; declarações não são marcadas automaticamente.')
                for nome, campo in PdfReader(str(caminho_modelo_contrato(tipo))).get_fields().items():
                    if nome in mapeados or nome.startswith('assinatura_') or nome == 'data_assinatura':
                        continue
                    rotulo = nome.replace('_',' ').capitalize()
                    if campo.get('/FT') == '/Btn':
                        dados[nome] = st.checkbox(rotulo, key=prefixo+'_nativo_'+nome)
                    else:
                        valor_padrao = {'razao_social':empresa['nome'],'cnpj_empresa':empresa['cnpj'], 'cnpj_concedente':empresa['cnpj'],
                            'endereco_empresa':', '.join(v for v in (empresa['endereco'],empresa['cidade_estado']) if v),
                            'endereco_concedente':', '.join(v for v in (empresa['endereco'],empresa['cidade_estado']) if v),
                            'representante_legal':empresa['responsavel_legal'], 'cpf_representante':empresa['cpf_responsavel']}.get(nome,'')
                        dados[nome] = st.text_area(rotulo, value=valor_padrao, key=prefixo+'_nativo_'+nome) if int(campo.get('/Ff',0)) & 4096 else st.text_input(rotulo, value=valor_padrao, key=prefixo+'_nativo_'+nome)
                    if nome in {'razao_social','cnpj_empresa','endereco_empresa','representante_legal','cpf_representante',
                                'cnpj_concedente','endereco_concedente','supervisor','cpf_supervisor','jornada_colaborador'} and not str(dados[nome]).strip():
                        faltam.append(rotulo)
        dados['data_vencimento'] = fim.strftime('%d/%m/%Y') if fim else ''
        st.info(f'Vigência: {inicio:%d/%m/%Y} a {fim:%d/%m/%Y}' + (' — 1 ano' if tipo != 'Serviços e Locação de Equipamentos' else '') if fim else f'Vigência por prazo indeterminado, a partir de {inicio:%d/%m/%Y}.')
        if faltam:
            st.info('Preencha antes de gerar: ' + ', '.join(faltam))
        assinatura = hashlib.sha256(json.dumps([tipo, parte, classificacao, dados, valores, prazo, impressao], sort_keys=True, default=str).encode()).hexdigest()
        resultado = st.session_state.get('central_contrato_resultado')
        ja_salvo = resultado and resultado['assinatura'] == assinatura
        if st.button('Gerar e salvar na aba Contratos', disabled=bool(faltam) or bool(ja_salvo), key=prefixo+'_gerar'):
            try:
                arquivo = gerar_pdf_word(tipo, valores, prazo, impressao) if tipo in WORD else gerar_contrato_pdf(tipo, dados)
                word = gerar_contrato_word(tipo, dados, valores=valores, prazo=prazo, impressao=impressao, pdf=arquivo)
                extensao = 'pdf'
                mime = 'application/pdf'
                nome = f"contrato_{parte['id']}_{assinatura[:10]}.{extensao}"
                conn = ctx['conectar_banco']()
                try:
                    contrato_id = salvar_contrato_gerado(conn, tipo=tipo, parte_tipo=classificacao,
                        parte_id=parte['id'], parte_nome=(prestador_pj.get('funcionario_nome') or prestador_pj.get('username')) if pj else (parte.get('pessoa_nome') or dados.get('nome') or parte['nome']), nome_arquivo=nome,
                        arquivo=arquivo, mime_type=mime, arquivo_word=word, nome_arquivo_word=nome_word(nome),
                        valor=dados.get('valor_contrato',''), inicio=dados.get('data_contrato',''), vencimento=dados['data_vencimento'],
                        criado_por=st.session_state.get('username',''), criado_em=ctx['agora_br']())
                finally:
                    conn.close()
                st.session_state['central_contrato_resultado'] = dict(assinatura=assinatura, arquivo=arquivo, nome=nome, mime=mime, word=word, id=contrato_id)
                st.success(f'Contrato #{contrato_id} salvo na central. Revise o documento antes de assinar.')
            except Exception as erro:
                st.error(f'Não foi possível gerar o contrato: {erro}')
        resultado = st.session_state.get('central_contrato_resultado')
        if resultado and resultado['assinatura'] == assinatura:
            st.download_button('Baixar contrato preenchido', resultado['arquivo'], file_name=resultado['nome'], mime=resultado['mime'], key=prefixo+'_download')
            if resultado.get('word'):
                st.download_button('Baixar contrato em Word (.docx)', resultado['word'], file_name=nome_word(resultado['nome']), mime=MIME_WORD, key=prefixo+'_download_word')
            if tipo not in WORD:
                st.caption('O Word contém o texto e os campos preenchidos em formato editável. A diagramação difere do formulário PDF.')
