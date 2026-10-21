"""Preenchimento por sessão, sem gravar consultas de homologação no cadastro."""
import hashlib
import json
import time

from dsystem_erp.services.nfe_cadastro_automatico import completar_destinatario


def preparar_destinatario(st, cliente, faturamento_id, ambiente, cert_path, cert_password):
    identidade = hashlib.sha256(json.dumps(
        [cliente, ambiente, cert_path], sort_keys=True, default=str
    ).encode()).hexdigest()[:20]
    cache_key = f'nfe_consulta_destinatario_{identidade}'
    prefixo = f'nfe_dest_auto_{faturamento_id}_{identidade}'
    renovar = st.button('Consultar novamente os dados do destinatário', key=prefixo + '_consultar',
                        help='Consulta sem emitir nota. Preenche campos vazios e preserva suas edições.')
    cache = st.session_state.get(cache_key)
    atualizado = renovar or not cache or time.time() - cache['horario'] > 1800
    if atualizado:
        with st.spinner('Consultando dados cadastrais do destinatário…'):
            resultado = completar_destinatario(cliente, ambiente, cert_path, cert_password)
        cache = {'horario': time.time(), 'resultado': resultado}
        st.session_state[cache_key] = cache
    resultado = cache['resultado']
    for campo, valor in resultado['dados'].items():
        chave = prefixo + '_' + campo
        if chave not in st.session_state or (atualizado and not st.session_state[chave]):
            st.session_state[chave] = valor
    if resultado['fontes']:
        st.caption('Preenchimento automático: ' + '; '.join(resultado['fontes']) +
                   '. Confira os dados antes de emitir. O cadastro original não foi alterado.')
    for aviso in resultado['avisos']:
        st.warning(aviso)
    return resultado['dados'], prefixo
