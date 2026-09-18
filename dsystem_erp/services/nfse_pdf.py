"""Representação auxiliar própria da NFS-e, sem presumir dados fiscais."""
import io
from html import escape
from lxml import etree


def gerar_pdf_nota_autorizada_simples(nota, retorno_info, formatar_moeda=None):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    roots = []
    for campo in ('xml_autorizado', 'xml_retorno', 'xml_envio'):
        xml = nota.get(campo)
        if xml:
            try:
                roots.append(etree.fromstring(xml.encode() if isinstance(xml, str) else xml,
                    etree.XMLParser(resolve_entities=False, no_network=True)))
            except (etree.XMLSyntaxError, ValueError, TypeError):
                pass

    def buscar(path):
        for root in roots:
            valores = root.xpath(path)
            if valores:
                return str(valores[0])
        return ''

    def tag(nome):
        return buscar(f"//*[local-name()='{nome}']/text()")

    def pessoa(tipo, campo):
        return buscar(f"//*[local-name()='{tipo}']/*[local-name()='{campo}']/text()")

    def moeda(valor):
        if valor is None or valor == '':
            return 'Não informado'
        if formatar_moeda:
            return formatar_moeda(valor)
        try:
            return f'R$ {float(valor):,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
        except (ValueError, TypeError):
            return 'Não informado'

    aviso = {'2': 'HOMOLOGAÇÃO - SEM VALIDADE FISCAL', '1': 'AMBIENTE DE PRODUÇÃO'}.get(tag('tpAmb'), 'AMBIENTE NÃO IDENTIFICADO - CONFERIR XML')
    numero = tag('nNFSe') or retorno_info.get('numero_nfse') or nota.get('numero_nota') or '-'
    largura = A4[0] - 64
    normal = ParagraphStyle('campo', fontName='Helvetica', fontSize=9, leading=13, wordWrap='CJK')
    pequeno = ParagraphStyle('rotulo', parent=normal, fontSize=7, leading=10)
    titulo = ParagraphStyle('titulo', parent=normal, fontName='Helvetica-Bold', fontSize=17, leading=21)
    branco = ParagraphStyle('secao', parent=normal, fontName='Helvetica-Bold', textColor=colors.white)
    partes = []

    def p(valor, estilo=normal):
        return Paragraph(escape(str(valor if valor is not None else '')).replace('\n', '<br/>'), estilo)

    def quadro(campos, pesos=None):
        pesos = pesos or [1] * len(campos)
        celulas = [[p(rotulo.upper(), pequeno), p(valor or 'Não informado')] for rotulo, valor in campos]
        tabela = Table([celulas], colWidths=[largura*x/sum(pesos) for x in pesos])
        tabela.setStyle(TableStyle([('GRID',(0,0),(-1,-1),.5,colors.HexColor('#52606d')),
            ('VALIGN',(0,0),(-1,-1),'TOP'), ('LEFTPADDING',(0,0),(-1,-1),9),
            ('RIGHTPADDING',(0,0),(-1,-1),9), ('TOPPADDING',(0,0),(-1,-1),7),
            ('BOTTOMPADDING',(0,0),(-1,-1),8)]))
        partes.append(tabela)

    def secao(texto):
        partes.append(Spacer(1,12))
        t = Table([[p(texto, branco)]], colWidths=[largura])
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),colors.HexColor('#18364b')),
            ('LEFTPADDING',(0,0),(-1,-1),9), ('TOPPADDING',(0,0),(-1,-1),6),
            ('BOTTOMPADDING',(0,0),(-1,-1),6), ('KEEPWITHNEXT',(0,0),(-1,-1),True)]))
        t.keepWithNext = True
        partes.append(t)

    partes.extend([p('NFS-e | NOTA FISCAL DE SERVIÇO', titulo),
        p('Representação auxiliar gerada pelo Dsystem ERP. Não substitui o DANFSe oficial.', pequeno)])
    secao(aviso)
    quadro([('Número da NFS-e',numero), ('Situação',retorno_info.get('status') or nota.get('status')),
        ('Competência',tag('dCompet') or nota.get('data_competencia'))])
    quadro([('Chave de acesso',retorno_info.get('chave_acesso') or nota.get('chave_acesso'))])
    quadro([('Emissão da DPS',tag('dhEmi')), ('Processamento',tag('dhProc'))])
    secao('PRESTADOR DO SERVIÇO')
    quadro([('Nome / razão social',pessoa('emit','xNome') or pessoa('prest','xNome')),
        ('CPF/CNPJ',pessoa('prest','CNPJ') or pessoa('prest','CPF'))], [2,1])
    quadro([('Inscrição municipal enviada',pessoa('prest','IM') or 'Não informada no XML'),
        ('Município emissor (IBGE)',tag('cLocEmi'))])
    secao('TOMADOR DO SERVIÇO')
    quadro([('Nome / razão social',pessoa('toma','xNome') or nota.get('cliente')),
        ('CPF/CNPJ',pessoa('toma','CNPJ') or pessoa('toma','CPF') or nota.get('cpf_cnpj'))], [2,1])
    secao('SERVIÇOS PRESTADOS')
    quadro([('Código nacional',tag('cTribNac')), ('Desdobramento municipal',tag('cTribMun')),
        ('Município da prestação (IBGE)',tag('cLocPrestacao'))])
    partes.extend([Spacer(1,8),p(tag('xDescServ') or nota.get('descricao') or 'Não informada'),Spacer(1,8)])
    secao('VALORES DA NOTA')
    quadro([('Valor dos serviços',moeda(tag('vServ') or nota.get('valor_servicos'))),
        ('ISS',moeda(tag('vISSQN'))), ('Valor líquido',moeda(tag('vLiq')))])
    quadro([('Tributos aproximados federais',moeda(tag('vTotTribFed'))),
        ('Tributos aproximados estaduais',moeda(tag('vTotTribEst'))),
        ('Tributos aproximados municipais',moeda(tag('vTotTribMun')))])
    secao('IDENTIFICAÇÃO E INFORMAÇÕES COMPLEMENTARES')
    quadro([('Identificador da DPS',buscar("//*[local-name()='infDPS']/@Id"))])
    partes.extend([Spacer(1,8),p(retorno_info.get('mensagem') or nota.get('mensagem_retorno') or '',pequeno),
        p('Campos ausentes não foram presumidos. Confira os dados no XML autorizado e no documento oficial do emissor nacional.',pequeno)])

    def rodape(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor('#52606d'))
        canvas.line(32,34,A4[0]-32,34)
        canvas.setFont('Helvetica',7)
        canvas.drawString(32,23,aviso)
        canvas.drawRightString(A4[0]-32,23,f'Dsystem ERP | Página {doc.page}')
        canvas.restoreState()

    buffer = io.BytesIO()
    SimpleDocTemplate(buffer,pagesize=A4,leftMargin=32,rightMargin=32,topMargin=30,bottomMargin=48,
        title=f'NFS-e {numero} - Representação auxiliar',author='Dsystem ERP').build(partes,onFirstPage=rodape,onLaterPages=rodape)
    return buffer.getvalue()
