"""Orientação e troca explícita de modo, sem disparar transmissão fiscal."""
from dsystem_erp.services.fiscal_automatico import desativar_emissao_automatica


def renderizar_modo_manual(st, fat, conectar, pode_editar):
    if not fat:
        return
    if fat.get('emitir_automaticamente'):
        st.info(f"Faturamento #{fat['id']}: emissão automática ativada. O envio manual está bloqueado enquanto esse modo estiver ativo.")
        if st.button('Usar emissão manual neste faturamento', key=f"nf_modo_manual_{fat['id']}", disabled=not pode_editar):
            try:
                desativar_emissao_automatica(conectar, fat['id'])
            except Exception as erro:
                st.error(str(erro))
            else:
                st.rerun()
    else:
        st.caption(f"Faturamento #{fat['id']}: modo manual. Não é necessário salvar preparação automática.")
    if fat.get('status') != 'Faturado':
        st.warning('Para enviar manualmente, primeiro marque o lançamento como Faturado em A faturar, com a emissão automática desmarcada. Assinar ou salvar na fila não transmite a nota.')


def exibir_resultado_manual(st, fat_id, tipo):
    resultado = st.session_state.get(f"nf_resultado_manual_{fat_id}_{tipo}")
    if not resultado:
        return
    nivel = resultado.get('nivel', 'info')
    getattr(st, nivel if nivel in ('success', 'warning', 'error', 'info') else 'info')(resultado['mensagem'])
    if resultado.get('xml_retorno'):
        with st.expander('Último retorno do envio manual', expanded=False):
            st.code(resultado['xml_retorno'], language='xml')
