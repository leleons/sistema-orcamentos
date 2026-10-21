"""PDF portátil para os dois modelos Word simples da central de contratos.

Mantém texto, ênfases e geometria dos originais. Não exige Word/LibreOffice
no servidor; a fonte Aptos é substituída pela família Vera incorporada.
"""
import io
from html import escape
from pathlib import Path
from zipfile import ZipFile
from lxml import etree
from dsystem_erp.services.contratos_modelos import W, gerar_word


def gerar_pdf_word(tipo, valores, prazo='Determinado', impressao='Franquia'):
    return pdf_do_word(gerar_word(tipo, valores, prazo, impressao), tipo)


def pdf_do_word(arquivo_docx, titulo='Contrato'):
    """Prévia portátil dos DOCX textuais suportados, sem conversor externo."""
    import reportlab
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, PageBreak

    fontes = Path(reportlab.__file__).parent / 'fonts'
    for nome, arquivo in [('ContratoWord','Vera.ttf'), ('ContratoWord-Bold','VeraBd.ttf'),
                          ('ContratoWord-Italic','VeraIt.ttf'), ('ContratoWord-BoldItalic','VeraBI.ttf')]:
        if nome not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(nome, str(fontes / arquivo)))
    pdfmetrics.registerFontFamily('ContratoWord', normal='ContratoWord', bold='ContratoWord-Bold',
                                  italic='ContratoWord-Italic', boldItalic='ContratoWord-BoldItalic')
    with ZipFile(io.BytesIO(arquivo_docx)) as docx:
        raiz = etree.fromstring(docx.read('word/document.xml'), etree.XMLParser(resolve_entities=False, no_network=True))
        numeracao = etree.fromstring(docx.read('word/numbering.xml'))
    sec = raiz.find('.//' + W + 'sectPr')
    tamanho, margens = sec.find(W+'pgSz'), sec.find(W+'pgMar')
    def medida(elemento, chave, padrao):
        return float(elemento.get(W+chave, padrao)) / 20
    saida = io.BytesIO()
    doc = SimpleDocTemplate(saida, pagesize=(medida(tamanho,'w',11906), medida(tamanho,'h',16838)),
        topMargin=medida(margens,'top',1417), bottomMargin=medida(margens,'bottom',1417),
        leftMargin=medida(margens,'left',1701), rightMargin=medida(margens,'right',1701), title=titulo)
    mapa_num = {n.get(W+'numId'): n.find(W+'abstractNumId').get(W+'val') for n in numeracao.findall(W+'num')}
    abstratos = {n.get(W+'abstractNumId'): n for n in numeracao.findall(W+'abstractNum')}
    contadores, fluxo = {}, []
    paragrafos = raiz.find(W+'body').findall(W+'p')
    rotulos_assinatura = {'CONTRATANTE','CONTRATADA','LOCADORA','LOCATÁRIA'}
    for indice, p in enumerate(paragrafos):
        trechos = []
        for run in p.iter(W+'r'):
            texto = ''.join(escape(n.text or '') if n.tag == W+'t' else '<br/>' if n.tag == W+'br' and n.get(W+'type') != 'page' else ' ' if n.tag == W+'tab' else '' for n in run)
            prop = run.find(W+'rPr')
            if prop is not None:
                if prop.find(W+'b') is not None and prop.find(W+'b').get(W+'val') != '0':
                    texto = '<b>' + texto + '</b>'
                if prop.find(W+'i') is not None and prop.find(W+'i').get(W+'val') != '0':
                    texto = '<i>' + texto + '</i>'
            trechos.append(texto)
        texto = ''.join(trechos)
        pp = p.find(W+'pPr')
        alinhamento, tamanho_fonte, antes, depois, leading = TA_LEFT, 12, 0, 8, 13.9
        recuo, pendente, marcador = 0, 0, None
        if pp is not None:
            jc, esp, ind, num = (pp.find(W+k) for k in ('jc','spacing','ind','numPr'))
            if jc is not None:
                alinhamento = {'center':TA_CENTER,'right':TA_RIGHT,'both':TA_JUSTIFY}.get(jc.get(W+'val'), TA_LEFT)
            if esp is not None:
                antes, depois = medida(esp,'before',0), medida(esp,'after',160)
                if esp.get(W+'line'):
                    leading = float(esp.get(W+'line')) / 240 * 12 if esp.get(W+'lineRule','auto') == 'auto' else medida(esp,'line',278)
            if ind is not None:
                recuo, pendente = medida(ind,'left',0), medida(ind,'hanging',0)
            if num is not None and num.find(W+'numId') is not None:
                nid = num.find(W+'numId').get(W+'val')
                nivel = num.find(W+'ilvl')
                nivel = nivel.get(W+'val') if nivel is not None else '0'
                abstrato = abstratos.get(mapa_num.get(nid))
                lvl = abstrato.find(W+f'lvl[@{W}ilvl="{nivel}"]') if abstrato is not None else None
                fmt = lvl.find(W+'numFmt').get(W+'val') if lvl is not None else 'bullet'
                chave = (nid, nivel)
                contadores[chave] = contadores.get(chave,0) + 1
                marcador = '•' if fmt == 'bullet' else f'{contadores[chave]}.'
                recuo = recuo or 18
        sz = p.find('.//' + W+'sz')
        if sz is not None:
            tamanho_fonte = float(sz.get(W+'val')) / 2
        if p.find('.//' + W+'br[@'+W+'type="page"]') is not None:
            fluxo.append(PageBreak())
        if not texto.strip():
            if p.find('.//' + W+'br[@'+W+'type="page"]') is not None:
                continue
            if p.find('.//{urn:schemas-microsoft-com:vml}rect') is not None:
                linha = HRFlowable(width='100%', thickness=.6, color='#a0a0a0', spaceAfter=8)
                seguinte = ''.join(t.text or '' for t in paragrafos[indice+1].iter(W+'t')).strip() if indice+1 < len(paragrafos) else ''
                linha.keepWithNext = seguinte.split(':')[0] in rotulos_assinatura
                fluxo.append(linha)
            else:
                fluxo.append(Spacer(1, leading + depois))
            continue
        style = ParagraphStyle('original', fontName='ContratoWord', fontSize=tamanho_fonte,
            leading=max(leading,tamanho_fonte*1.15), alignment=alinhamento, spaceBefore=antes, spaceAfter=depois,
            leftIndent=recuo, firstLineIndent=-pendente, bulletIndent=max(0,recuo-14),
            bulletFontName='ContratoWord', bulletFontSize=tamanho_fonte, keepWithNext=(indice == 0 or (len(texto)<180 and texto.startswith('<b>'))))
        style.allowOrphans = 0
        style.allowWidows = 0
        if pp is not None and pp.find(W+'keepNext') is not None:
            style.keepWithNext = pp.find(W+'keepNext').get(W+'val') != '0'
        if pp is not None and pp.find(W+'pBdr/'+W+'top') is not None:
            # Espaço para assinatura e linha permanecem junto ao rótulo.
            linha = HRFlowable(width='100%', thickness=.6, color='#000000', spaceBefore=antes, spaceAfter=4)
            linha.keepWithNext = True
            fluxo.append(linha)
            style.spaceBefore = 0
        if indice+2 < len(paragrafos) and paragrafos[indice+1].find('.//{urn:schemas-microsoft-com:vml}rect') is not None:
            seguinte = ''.join(t.text or '' for t in paragrafos[indice+2].iter(W+'t')).strip()
            if seguinte.split(':')[0] in rotulos_assinatura:
                style.keepWithNext = True
        fluxo.append(Paragraph(texto, style, bulletText=marcador))
    doc.build(fluxo)
    return saida.getvalue()
