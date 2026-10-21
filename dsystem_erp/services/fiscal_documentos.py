"""Prontidão fiscal baseada nas notas autorizadas e nos PDFs efetivamente salvos."""
import io

from pypdf import PdfReader

from dsystem_erp.services.fiscal_automatico import tipos_fiscais
from dsystem_erp.services.pacote_faturamento import DocumentoFaturamento, decodificar_pdf_base64


def pdf_salvo_valido(valor):
    try:
        pdf = decodificar_pdf_base64(valor)
        if pdf.startswith(b'%PDF') and len(PdfReader(io.BytesIO(pdf)).pages):
            return pdf
    except Exception:
        pass
    return b''


def pdf_da_nota(nota):
    # PDFs auxiliares antigos de serviço não substituem o DANFSe do XML autorizado.
    if nota.get('tipo_nota') == 'Serviço' and not str(nota.get('link_nota') or '').startswith((
            'https://www.nfse.gov.br/ConsultaPublica/', 'https://www.producaorestrita.nfse.gov.br/ConsultaPublica/')):
        return b''
    return pdf_salvo_valido(nota.get('pdf_base64'))


def consultar_documentos_fiscais(conectar, fat_id):
    """Somente leitura; nunca emite/reemite nota nem usa espelho como nota fiscal."""
    conn = conectar()
    try:
        c = conn.cursor()
        c.execute('SELECT * FROM faturamento WHERE id=?', (fat_id,))
        fat = c.fetchone()
        if not fat:
            raise ValueError('Faturamento não encontrado.')
        c.execute('SELECT * FROM notas_fiscais WHERE faturamento_id=? ORDER BY id DESC', (fat_id,))
        notas = c.fetchall()
        c.execute('SELECT * FROM fiscal_emissoes_auto WHERE faturamento_id=?', (fat_id,))
        estados = {r['tipo']: r for r in c.fetchall()}
    finally:
        conn.close()
    documentos, pendencias = [], []
    esperados = tipos_fiscais(fat)
    # Preserva documentos históricos, inclusive registros antigos sem itens tipados.
    tipos = list(dict.fromkeys(esperados + [n['tipo_nota'] for n in notas if n.get('status') == 'Autorizada']))
    for tipo in tipos:
        candidatas = [n for n in notas if n.get('tipo_nota') == tipo]
        autorizadas = [n for n in candidatas if n.get('status') == 'Autorizada']
        if autorizadas:
            for nota in autorizadas:
                pdf = pdf_da_nota(nota)
                if not pdf:
                    pendencias.append(f"{tipo} #{nota['id']}: autorizada, mas o PDF ainda não está disponível")
                    continue
                numero = nota.get('numero_nota') or nota['id']
                documentos.append(DocumentoFaturamento(
                    codigo=f"nota:{nota['id']}", titulo=f"Nota {tipo} #{numero}", categoria='Nota fiscal',
                    arquivo=pdf, nome_arquivo=f"nota_{'produto' if tipo == 'Produto' else 'servico'}_{nota['id']}.pdf"))
        else:
            estado = estados.get(tipo) or (candidatas[0] if candidatas else {})
            detalhe = estado.get('mensagem') or estado.get('mensagem_retorno') or estado.get('estado') or estado.get('status') or 'aguardando preparação e autorização'
            pendencias.append(f'{tipo}: {detalhe}')
    return dict(pronto=bool(esperados) and bool(documentos) and not pendencias, documentos=documentos, pendencias=pendencias)


def resultado_emissao(conectar, fat_id):
    estado = consultar_documentos_fiscais(conectar, fat_id)
    mensagem = ('Notas autorizadas e PDFs prontos para baixar juntos.' if estado['pronto'] else
                'Notas ainda não estão prontas: ' + ' | '.join(estado['pendencias']))
    return dict(fiscal_pronto=estado['pronto'], mensagem=mensagem)
