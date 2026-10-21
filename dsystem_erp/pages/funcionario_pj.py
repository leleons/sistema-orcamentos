"""Campos da empresa prestadora no cadastro e edição de usuários."""
from dsystem_erp.services.contratos_pj import CAMPOS_EMPRESA_PJ, cadastro_empresa_pj, eh_pj


def campos_empresa_pj(st, tipo, prefixo, usuario=None):
    usuario = usuario or {}
    if not eh_pj(tipo):
        return {k: usuario.get(k) or '' for k in CAMPOS_EMPRESA_PJ}
    legado = cadastro_empresa_pj(dict(usuario,id=usuario.get('id',0)))
    st.markdown('#### Empresa do prestador PJ')
    st.caption('O CPF identifica a pessoa. Estes dados identificam a empresa contratada no contrato PJ.')
    return dict(funcionario_pj_razao_social=st.text_input('Razão social da empresa PJ:',value=legado['nome'],key=prefixo+'_pj_razao'),
                funcionario_pj_cnpj=st.text_input('CNPJ da empresa PJ:',value=legado['cnpj'],key=prefixo+'_pj_cnpj'),
                funcionario_pj_endereco=st.text_area('Endereço completo da empresa PJ:',value=legado['endereco'],key=prefixo+'_pj_endereco'))
