"""Downloads do contrato salvo, sem regenerar suas cláusulas pelo modelo atual."""
import hashlib
from dsystem_erp.services.contratos_word import word_do_pdf, nome_word, MIME_WORD


def renderizar_downloads(st, contrato, prefixo='contrato'):
    arquivo = contrato.get('arquivo')
    if not arquivo:
        return
    nome = contrato.get('nome_arquivo') or f"contrato_{contrato['id']}.pdf"
    chave = f"{prefixo}_{contrato['id']}"
    st.download_button('Baixar contrato', bytes(arquivo), file_name=nome,
        mime=contrato.get('mime_type') or 'application/pdf', width='stretch', key=chave+'_original')
    word = contrato.get('arquivo_word')
    if word:
        st.download_button('Baixar contrato em Word (.docx)', bytes(word),
            file_name=contrato.get('nome_arquivo_word') or nome_word(nome),
            mime=MIME_WORD, key=chave+'_word')
    elif bytes(arquivo).startswith(b'%PDF'):
        chave += '_' + hashlib.sha256(bytes(arquivo)).hexdigest()
        if st.button('Preparar versão Word deste contrato', key=chave+'_preparar'):
            try:
                st.session_state[chave] = word_do_pdf(arquivo, contrato.get('tipo') or 'Contrato')
            except Exception as erro:
                st.error(f'Não foi possível preparar o Word: {erro}')
        if st.session_state.get(chave):
            st.download_button('Baixar contrato em Word (.docx)', st.session_state[chave],
                file_name=nome_word(nome), mime=MIME_WORD, key=chave+'_download')
            st.caption('Versão editável do documento salvo; a diagramação pode diferir do PDF. O original não foi alterado.')
