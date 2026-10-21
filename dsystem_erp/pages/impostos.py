"""Aba de impostos e cadastro fiscal, sem chamadas fiscais/bancárias."""
import json
from datetime import date
import streamlit as st

from dsystem_erp.services.permissions import usuario_tem_permissao
from dsystem_erp.services.impostos_cadastro import empresa_cnpj, listar_regras, salvar_regra, chave_item
from dsystem_erp.services.impostos_notas import carregar_base, segregar, classificar_historica
from dsystem_erp.services.impostos_simples import (
    ZERO, valor_prolabore, encargos_prolabore, estimar_simples, totais,
)


def _contexto(ctx, acao):
    usuario = dict(st.session_state)
    if not usuario.get('autenticado') or not usuario_tem_permissao(acao, usuario):
        st.error('Sem permissão: ' + acao)
        return None
    try:
        empresa = empresa_cnpj(ctx.get('config_sistema_val')('NFSE_CNPJ', ''))
    except ValueError as erro:
        st.error(str(erro))
        return None
    st.caption('Emitente configurado: ' + empresa)
    return usuario, empresa, ctx.get('conectar_banco')


def _brl(v):
    return 'R$ ' + f'{v:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')


def _classificar_antigas(conectar, empresa, notas, snapshots, regras, usuario, chave):
    faltantes = [n for n in notas if str(n['id']) not in snapshots]
    if not faltantes or not usuario_tem_permissao('impostos.edit', usuario):
        return
    with st.expander('Classificar notas antigas sem histórico de impostos'):
        st.caption('Não altera nem reemite a nota. Distribua o total entre os itens cadastrados, conforme a classificação validada pela contabilidade para aquela competência.')
        n = st.selectbox('Nota antiga', faltantes, format_func=lambda n:f"#{n['id']} — {n['tipo']} — {_brl(n['total'])}", key=chave+'_antiga')
        disponiveis = [r['nome'] for r in regras if r['tipo']==n['tipo'] and r.get('ativo', True)]
        if not disponiveis:
            st.info('Cadastre primeiro os impostos dos itens desta nota.')
            return
        prefixo = chave+f'_class_{n["id"]}_'
        qtd = st.number_input('Quantidade de classificações', min_value=1,max_value=30,value=1,step=1,key=prefixo+'qtd')
        with st.form(prefixo+'form', enter_to_submit=False):
            linhas = []
            for i in range(qtd):
                nome = st.selectbox(f'Item {i+1}', ['']+disponiveis, key=prefixo+f'nome{i}')
                valor = st.number_input(f'Valor da classificação {i+1} (R$)', min_value=0.0,
                    value=float(n['total']) if qtd==1 else 0.0, key=prefixo+f'valor{i}')
                linhas.append(dict(nome=nome, valor=valor))
            confirmado = st.checkbox('Confirmei esta classificação histórica com a contabilidade',key=prefixo+'confirmado')
            salvar = st.form_submit_button('Salvar classificação histórica')
        if salvar:
            try:
                if not confirmado:
                    raise ValueError('Confirme a classificação histórica antes de salvar.')
                classificar_historica(conectar,empresa,n['id'],linhas,usuario)
            except (ValueError, PermissionError) as erro:
                st.error(str(erro))
            except Exception:
                st.error('Não foi possível salvar a classificação; nenhuma nota foi alterada.')
            else:
                st.rerun()


def renderizar_cadastro_impostos(ctx):
    st.title('Cadastrar impostos')
    contexto = _contexto(ctx, 'impostos.view')
    if not contexto:
        return
    usuario, empresa, conectar = contexto
    try:
        regras = listar_regras(conectar, empresa)
    except Exception:
        st.error('Não foi possível carregar o cadastro fiscal. Nenhuma alteração foi salva.')
        return
    st.info('Cadastre pelo mesmo nome usado no faturamento. CNAE/nome não determinam sozinhos o enquadramento. Confira com sua contabilidade.')
    st.caption('Referências do documento: manutenção 9511-8/00; instalação 4321-5/00; suporte TI 6209-1/00. Comércio de informática: confira 4751-2/01 (no Word apareceu uma data).')
    if regras:
        st.dataframe([{k: r.get(k) for k in ('nome', 'tipo', 'cnae', 'anexo', 'ativo', 'atualizado_por')} for r in regras], hide_index=True)
    if not usuario_tem_permissao('impostos.edit', usuario):
        return
    por_chave = {chave_item(empresa, r['tipo'], r['nome']): r for r in regras}
    selecionado = st.selectbox('Editar cadastro', [''] + list(por_chave),
                              format_func=lambda k: 'Novo item' if not k else por_chave[k]['tipo']+' — '+por_chave[k]['nome'])
    r = por_chave.get(selecionado, {})
    tipo = st.selectbox('Tipo do item', ['Produto', 'Serviço'], index=int(r.get('tipo') == 'Serviço'),
                        key=f'imposto_tipo_{empresa}_{selecionado}', disabled=bool(selecionado))
    prefixo = f'imposto_{empresa}_{selecionado}_{tipo}_'
    with st.form(prefixo+'cadastro', enter_to_submit=False):
        regra = dict(tipo=tipo)
        regra['nome'] = st.text_input('Nome exato no faturamento', value=r.get('nome', ''), disabled=bool(selecionado))
        regra['cnae'] = st.text_input('CNAE da atividade', value=r.get('cnae', ''))
        anexos = ['I', 'III', 'V', 'Fator R', 'IV', 'Outro']
        regra['anexo'] = st.selectbox('Anexo confirmado pela contabilidade', anexos, index=anexos.index(r.get('anexo', 'I' if tipo == 'Produto' else 'III')))
        regra['operacao_especial'] = st.checkbox('Operação especial: ST, monofásica, isenção, exportação ou outro ajuste no DAS', value=r.get('operacao_especial', False))
        if tipo == 'Produto':
            regra['crt'] = st.selectbox('Regime do emitente (CRT)', ['1', '3'], index=int(r.get('crt') == '3'),
                                       format_func=lambda v: '1 — Simples Nacional' if v == '1' else '3 — Regime normal / ICMS 00')
            regra['ncm'] = st.text_input('NCM (8 dígitos)', value=r.get('ncm', ''))
            regra['cfop'] = st.text_input('CFOP da operação (4 dígitos)', value=r.get('cfop', ''))
            regra['unidade'] = st.text_input('Unidade', value=r.get('unidade', 'UN'))
            regra['origem'] = st.selectbox('Origem fiscal', list('012345678'), index=int(r.get('origem', 0)))
            regra['csosn'] = st.selectbox('CSOSN', ['102', '500'], index=int(r.get('csosn') == '500'))
            st.warning('Emissão implementada: CRT 1 / CSOSN 102 ou CRT 3 / ICMS 00; PIS/COFINS CST 01 e bases integrais. CSOSN 500 pode ser cadastrado, mas o envio ficará bloqueado até implementar ICMS-ST. Não há conversão automática para 102.')
            regra['icms'] = st.number_input('ICMS (%) — CST 00, somente CRT 3', min_value=0.0, max_value=100.0, value=float(r.get('icms', 0)), step=.01)
            for campo in ('pis', 'cofins'):
                regra[campo] = st.number_input(campo.upper()+' (%) — CST 01', min_value=0.0, max_value=100.0, value=float(r.get(campo, 0)), step=.01)
        else:
            regra['codigo_tributacao_nacional'] = st.text_input('Código nacional do serviço (6 dígitos)', value=r.get('codigo_tributacao_nacional', ''))
            regra['codigo_tributacao_municipal'] = st.text_input('Desdobramento municipal (3 dígitos ou vazio)', value=r.get('codigo_tributacao_municipal', ''))
            regra['aliquota_iss'] = st.number_input('ISS (%)', min_value=0.0, max_value=5.0, value=float(r.get('aliquota_iss', 0)), step=.01)
            regra['informar_aliquota'] = st.checkbox('Informar a alíquota de ISS no XML (pAliq), quando exigido pelo regime/município',
                value=r.get('informar_aliquota', False), help='Ter uma taxa cadastrada não significa que a API permite enviar pAliq. Confirme este parâmetro para a operação; o sistema não força o campo em todos os regimes.')
            regra['tipo_retencao_issqn'] = st.selectbox('Retenção do ISS', ['1', '2', '3'], index=['1','2','3'].index(r.get('tipo_retencao_issqn', '1')),
                format_func=lambda v: {'1':'Não retido', '2':'Retido pelo tomador', '3':'Retido pelo intermediário'}[v])
            regra['retencao_inss'] = st.number_input('Retenção de INSS no serviço (%)', min_value=0.0, max_value=100.0, value=float(r.get('retencao_inss', 0)), step=.01)
            st.caption('INSS retido no serviço não é o INSS sobre pró-labore. Retenção de INSS ou ISS por intermediário ainda exige tratamento específico no emissor e bloqueia o envio quando informada.')
        regra['observacoes'] = st.text_area('Orientação da contabilidade', value=r.get('observacoes', ''))
        regra['ativo'] = st.checkbox('Cadastro ativo', value=r.get('ativo', True))
        regra['confirmado'] = st.checkbox('Conferi os códigos, bases integrais, taxas e enquadramento com a contabilidade', value=False)
        salvar = st.form_submit_button('Salvar cadastro de impostos')
    if salvar:
        try:
            salvar_regra(conectar, empresa, regra, usuario)
            st.success('Impostos salvos para este emitente e item. Revise novamente preparações de notas já existentes.')
        except (ValueError, PermissionError) as erro:
            st.error(str(erro))
        except Exception:
            st.error('Falha ao salvar. O cadastro não foi confirmado.')


def renderizar_impostos(ctx):
    st.title('Impostos')
    contexto = _contexto(ctx, 'impostos.view')
    if not contexto:
        return
    usuario, empresa, conectar = contexto
    with st.tabs(['Impostos do Simples'])[0]:
        st.warning('Estimativa gerencial com notas autorizadas em produção. Não substitui PGDAS-D/DAS, folha ou conferência contábil. Receita sem nota também pode integrar a obrigação fiscal, mas não entra nesta visão solicitada.')
        if 'impostos_competencia' not in st.session_state:
            st.session_state['impostos_competencia'] = date.today()
        competencia = st.date_input('Competência (qualquer dia do mês)', key='impostos_competencia')
        chave = f'IMPOSTOS_MES_{empresa}_{competencia:%Y%m}'
        try:
            salvo = json.loads(ctx.get('config_sistema_val')(chave, '{}'))
            notas, snapshots, pendencias = carregar_base(conectar, empresa, competencia)
            regras = listar_regras(conectar, empresa)
        except Exception:
            st.error('Não foi possível carregar as notas/parâmetros. Nenhum total será presumido.')
            return
        total_notas = sum((n['total'] for n in notas), ZERO)
        st.metric('Total de notas autorizadas — produção', _brl(total_notas))
        st.caption('NF-e: mês da emissão. NFS-e: competência. Espelhos, homologação e notas não autorizadas não entram. Notas sem XML/protocolo verificável ficam pendentes.')
        if notas:
            st.dataframe([{k: str(n[k]) for k in ('id', 'tipo', 'competencia', 'total')} for n in notas], hide_index=True)
        _classificar_antigas(conectar,empresa,notas,snapshots,regras,usuario,chave)
        usar_atual = st.checkbox('Para NF-e antigas sem histórico fiscal, usar o cadastro atual somente nesta estimativa', key=chave+'_legado')
        receitas, pendencias_classificacao = segregar(notas, snapshots, regras, permitir_cadastro_atual=usar_atual)
        pendencias += pendencias_classificacao
        if pendencias:
            st.warning('Apuração incompleta. Os valores abaixo são parciais; não use para recolhimento.')
            with st.expander('Pendências de documentos/classificação', expanded=True):
                for p in pendencias:
                    st.write(p)
        st.caption('RBT12 é a receita bruta global dos 12 meses anteriores, inclusive de outras fontes. Início de atividade exige receita proporcional confirmada. FS12 é a folha/encargos elegíveis do período para Fator R.')
        rbt12 = st.number_input('RBT12 confirmada (R$)', min_value=0.0, value=float(salvo.get('rbt12', 0)), key=chave+'_rbt12')
        fs12 = st.number_input('FS12 confirmada (R$)', min_value=0.0, value=float(salvo.get('fs12', 0)), key=chave+'_fs12')
        confirmado = st.checkbox('Confirmei RBT12/FS12, regime de competência e ausência de ajustes/sublimites não contemplados', key=chave+'_confirmado')
        st.subheader('Pró-labore por beneficiário')
        st.caption('Escolha valor fixo mensal ou percentual do total de notas deste mês. O percentual é uma escolha de gestão, não uma exigência fiscal. Some os pagamentos do mês de cada pessoa em uma única linha.')
        anteriores = salvo.get('beneficiarios') or [{}]
        quantidade = st.number_input('Quantidade de beneficiários', min_value=1, max_value=20, value=len(anteriores), step=1, key=chave+'_qtd')
        beneficiarios, resultados, nomes = [], [], set()
        erro_prolabore = False
        for i in range(quantidade):
            b = anteriores[i] if i < len(anteriores) else {}
            p = chave+f'_p{i}_'
            with st.expander(f'Beneficiário {i+1}', expanded=True):
                nome = st.text_input('Nome/identificação do beneficiário', value=b.get('nome', ''), key=p+'nome')
                modo = st.radio('Forma de definir o pró-labore', ['fixo', 'percentual'], index=int(b.get('modo') == 'percentual'),
                                format_func=lambda m: 'Valor mensal fixo' if m == 'fixo' else 'Percentual do faturamento com nota', key=p+'modo')
                # Chaves distintas: mudar de modo não transforma reais em porcentagem.
                fixo = st.number_input('Valor mensal fixo (R$)', min_value=0.0, value=float(b.get('fixo', 0)), disabled=modo!='fixo', key=p+'fixo')
                percent = st.number_input('Percentual do faturamento com nota (%)', min_value=0.0, max_value=100.0, value=float(b.get('percentual', 0)), disabled=modo!='percentual', key=p+'percentual')
                dependentes = st.number_input('Dependentes para IRPF', min_value=0, value=int(b.get('dependentes', 0)), step=1, key=p+'dependentes')
                outros = st.number_input('Base de INSS já utilizada em outros vínculos no mês (R$)', min_value=0.0, value=float(b.get('outros', 0)), key=p+'outros')
                deducoes = st.number_input('Outras deduções legais de IRPF confirmadas (R$)', min_value=0.0, value=float(b.get('deducoes', 0)), key=p+'deducoes')
                beneficiarios.append(dict(nome=nome, modo=modo, fixo=fixo, percentual=percent, dependentes=dependentes, outros=outros, deducoes=deducoes))
                try:
                    bruto = valor_prolabore(modo, fixo if modo == 'fixo' else percent, total_notas)
                    if not nome.strip() or nome.strip().casefold() in nomes:
                        raise ValueError('Informe uma identificação única para cada beneficiário.')
                    nomes.add(nome.strip().casefold())
                    resultado = encargos_prolabore(bruto, ano=competencia.year, dependentes=dependentes,
                                                   base_inss_outros=outros, deducoes_legais_adicionais=deducoes)
                    resultados.append(resultado)
                    st.write({k: _brl(resultado[k]) for k in ('bruto', 'inss', 'irpf', 'liquido')})
                    if 0 < bruto < 1621:
                        st.caption('Pró-labore abaixo do mínimo de 2026: confira eventual complementação previdenciária individual.')
                except ValueError as erro:
                    st.info(str(erro))
                    erro_prolabore = True
        st.caption('INSS: 11% limitado ao teto restante. IRPF: tabela mensal 2026, dedução mais favorável e redução legal. CPP fora do DAS, múltiplas fontes/ajuste anual e situações especiais não estão incluídos.')
        if usuario_tem_permissao('impostos.edit', usuario) and st.button('Salvar parâmetros deste mês', key=chave+'_salvar'):
            if erro_prolabore or not confirmado:
                st.error('Confira os beneficiários e confirme os parâmetros antes de salvar.')
            else:
                try:
                    ctx.get('salvar_config_sistema')(chave, json.dumps(dict(rbt12=rbt12, fs12=fs12, beneficiarios=beneficiarios)), 'Parâmetros gerenciais de impostos por competência/emitente')
                    st.success('Preferências salvas para este mês e empresa; nenhuma nota, pagamento ou recolhimento foi executado.')
                except Exception:
                    st.error('Não foi possível salvar as preferências.')
        if confirmado and not erro_prolabore:
            try:
                linhas, das = estimar_simples(receitas, rbt12, fs12, ano=competencia.year)
                if linhas:
                    st.dataframe([{**{k:str(v) for k,v in l.items()}, 'aliquota_percentual':str(l['aliquota']*100)} for l in linhas], hide_index=True)
                total = totais(das, resultados)
                st.subheader('Resumo parcial' if pendencias else 'Resumo estimado')
                for campo, rotulo in (('simples','Simples Nacional'), ('prolabore_bruto','Pró-labore bruto'), ('inss','INSS sobre pró-labore'), ('irpf','IRPF sobre pró-labore'), ('impostos','Total de impostos (Simples + IRPF)'), ('encargos','Total de encargos (INSS retido)'), ('total_recolher','Total geral a recolher'), ('desembolso','Desembolso (Simples + pró-labore bruto)')):
                    st.metric(rotulo, _brl(total[campo]))
                st.caption('INSS e IRPF retidos já fazem parte do pró-labore bruto; não são adicionados novamente ao desembolso.')
            except ValueError as erro:
                st.error(str(erro))
        st.caption('Fontes: LC 123/2006, anexos I/III/V; Receita Federal, tabelas IRPF 2026; INSS, tabela de contribuição 2026. Regras futuras exigem atualização.')
