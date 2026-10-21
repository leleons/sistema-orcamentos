"""Prévia e consulta dos cadastros estruturados da planilha D-System."""
import hashlib

from dsystem_erp.services.cadastros_planilha import (
    ABAS, CAMPOS, carregar_cadastros, ler_planilha, preparar_importacao, importar,
)
from dsystem_erp.services.permissions import usuario_tem_permissao


def renderizar(st, conectar):
    usuario = dict(st.session_state)
    if not usuario.get('autenticado') or not usuario_tem_permissao('financeiro.cadastros', usuario):
        return
    st.subheader('Plano de contas, naturezas financeiras e centros de custo')
    st.caption('Naturezas financeiras ficam disponíveis no campo Categoria / natureza dos lançamentos. Vínculos sugeridos são classificações, não lançamentos contábeis nem contas bancárias.')
    try:
        existentes = carregar_cadastros(conectar)
    except Exception:
        st.error('Não foi possível consultar os cadastros para importar. Nenhuma alteração foi feita.')
        return
    with st.expander('Importar planilha de cadastros (.xlsx)'):
        st.write('Lê somente Plano de contas, Centros de custo e Naturezas financeiras. Abas de exemplos e instruções são ignoradas. Os códigos devem estar como texto.')
        if usuario_tem_permissao('financeiro.cadastros.edit', usuario):
            arquivo = st.file_uploader('Planilha de cadastros', type=['xlsx'], key='cadastros_xlsx')
            if arquivo is not None:
                conteudo = arquivo.getvalue()
                try:
                    registros = ler_planilha(conteudo)
                    plano = preparar_importacao(registros, existentes)
                    resumo = [{
                        'Cadastro': tipo, 'Novos': sum(i['acao']=='Novo' and i['registro']['tipo']==tipo for i in plano['itens']),
                        'Atualizar': sum(i['acao']=='Atualizar' and i['registro']['tipo']==tipo for i in plano['itens']),
                        'Sem alteração': sum(i['acao']=='Sem alteração' and i['registro']['tipo']==tipo for i in plano['itens']),
                    } for tipo, _ in ABAS.values()]
                    st.dataframe(resumo, hide_index=True)
                    st.dataframe([{'Ação': i['acao'], **{k:i['registro'][k] for k in CAMPOS}} for i in plano['itens']], hide_index=True)
                    alterados = [i for i in plano['itens'] if i['acao']=='Atualizar']
                    if alterados:
                        with st.expander('Comparar alterações nos códigos existentes'):
                            st.dataframe([{'Tipo':i['registro']['tipo'],'Código':i['registro']['codigo'],
                                'Campo':k, 'Antes':str(i['anterior'].get(k) or ''),'Depois':str(i['registro'].get(k) or '')}
                                for i in alterados for k in CAMPOS if (i['anterior'].get(k) or '') != (i['registro'].get(k) or '')],hide_index=True)
                    # Confirmações expiram ao trocar o arquivo ou o estado visto no banco.
                    chave = hashlib.sha256((plano['assinatura']).encode()).hexdigest()[:20]
                    atualizar = st.checkbox('Autorizo atualizar os códigos existentes mostrados na prévia',key='cad_atualizar_'+chave) if alterados else False
                    confirmar = st.checkbox('Conferi os cadastros e autorizo esta importação',key='cad_confirmar_'+chave)
                    st.caption('Não exclui registros ausentes do arquivo. Não altera títulos, saldos, notas ou contas bancárias existentes.')
                    if st.button('Importar cadastros conferidos',key='cad_importar_'+chave,disabled=not confirmar or (bool(alterados) and not atualizar)):
                        resultado = importar(conectar,conteudo,plano['assinatura'],usuario,atualizar)
                        st.session_state['cadastros_importados_resultado'] = resultado
                        st.rerun()
                except (ValueError, PermissionError) as erro:
                    st.error(str(erro))
                except Exception:
                    st.error('Não foi possível concluir a importação. A transação foi cancelada; verifique o arquivo e o banco.')
        else:
            st.info('A importação exige permissão de edição de cadastros financeiros.')
    resultado = st.session_state.pop('cadastros_importados_resultado', None)
    if resultado:
        st.success(f"Importação concluída: {resultado['Novo']} novos, {resultado['Atualizar']} atualizados e {resultado['Sem alteração']} sem alteração.")
    for tab, (aba, (tipo, _)) in zip(st.tabs(list(ABAS)), ABAS.items()):
        with tab:
            registros = [r for r in existentes if r.get('tipo') == tipo]
            filtro = st.text_input('Pesquisar código, nome ou vínculo', key='cad_filtro_'+tipo).strip().casefold()
            registros = [r for r in registros if not filtro or filtro in ' '.join(str(r.get(k) or '') for k in CAMPOS).casefold()]
            if registros:
                st.dataframe([{k:r.get(k) for k in CAMPOS if k not in ('tipo','importacao_origem')} for r in registros], hide_index=True)
            else:
                st.info('Nenhum cadastro encontrado.')


def detalhes_importados(st, registro):
    """O editor simples não pode quebrar a hierarquia ou os vínculos importados."""
    st.info('Cadastro estruturado importado. Para alterar seus campos ou desativá-lo, ajuste a linha na planilha e reimporte; a prévia valida os vínculos e preserva o ID.')
    st.json({k:registro.get(k) for k in CAMPOS if k != 'importacao_origem'})
