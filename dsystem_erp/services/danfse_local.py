"""DANFSe v2.0 local, composto exclusivamente a partir da NFS-e autorizada."""
import io
from datetime import datetime
from decimal import Decimal, InvalidOperation
from html import escape
from pathlib import Path

from lxml import etree
from reportlab.pdfgen import canvas
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.graphics import renderPDF

from dsystem_erp.services.danfse import conferir_xml_nacional, url_consulta_publica


def gerar_danfse_local(nota):
    xml = nota.get('xml_autorizado')
    dados = conferir_xml_nacional(xml, nota.get('chave_acesso') or '')
    root = etree.fromstring(xml.encode() if isinstance(xml, str) else xml,
                           etree.XMLParser(resolve_entities=False, no_network=True))
    ns = {'n': 'http://www.sped.fazenda.gov.br/nfse'}
    inf = root.find('n:infNFSe', ns)
    dps = inf.find('n:DPS/n:infDPS', ns)

    def get(path, node=None):
        return (node if node is not None else inf).findtext(
            '/'.join('n:' + p for p in path.split('/')), default='', namespaces=ns)

    def d(path):
        return get(path, dps)

    def money(value):
        if value == '':
            return '-'
        try:
            return ('R$ {:,.2f}'.format(Decimal(value))).replace(',', 'X').replace('.', ',').replace('X', '.')
        except InvalidOperation:
            raise ValueError('Valor monetário inválido no XML autorizado.')

    def pct(value):
        return (value.replace('.', ',') + ' %') if value else '-'

    def date(value):
        if not value:
            return '-'
        try:
            return datetime.fromisoformat(value).strftime('%d/%m/%Y %H:%M:%S' if 'T' in value else '%d/%m/%Y')
        except ValueError:
            return value

    def doc(value):
        if len(value) == 14:
            return f'{value[:2]}.{value[2:5]}.{value[5:8]}/{value[8:12]}-{value[12:]}'
        if len(value) == 11:
            return f'{value[:3]}.{value[3:6]}.{value[6:9]}-{value[9:]}'
        return value or '-'

    out = io.BytesIO()
    c = canvas.Canvas(out, pagesize=(595, 842), pageCompression=1)
    c.setTitle('DANFSe v2.0 - NFS-e ' + dados['numero'])
    c.setAuthor('Dsystem ERP - DANFSe gerado do XML autorizado')
    style = ParagraphStyle('valor', fontName='Helvetica', fontSize=6.75, leading=8.25)
    y = 48
    pending_title = None

    def text(value, x, top, width, size=6.75, bold=False, color='black'):
        s = ParagraphStyle('linha', parent=style, fontSize=size, leading=size+1,
                           fontName='Helvetica-Bold' if bold else 'Helvetica', textColor=color)
        p = Paragraph(escape(str(value or '-')).replace('\n', '<br/>'), s)
        _, h = p.wrap(width, 800)
        p.drawOn(c, x, 842-top-h)
        return h

    def line(top):
        c.setLineWidth(.5)
        c.line(13, 842-top, 578, 842-top)

    def row(fields, widths=None, height=20.25):
        nonlocal y, pending_title
        widths = [w * 565 / 585 for w in widths] if widths else [565/len(fields)] * len(fields)
        title = pending_title
        pending_title = None
        if title:
            widths = [423.75/len(fields)] * len(fields)
        # Measure before drawing so long names/descriptions never overwrite rows.
        heights = []
        for (label, value), w in zip(fields, widths):
            p = Paragraph(escape(str(value or '-')).replace('\n', '<br/>'), style)
            heights.append(p.wrap(w-8, 800)[1] + 10)
        h = max([height] + heights)
        x = 154.25 if title else 13
        if title:
            c.setFillColorRGB(.94, .94, .94)
            c.rect(13, 842-y-18, 140, 18, stroke=0, fill=1)
            c.setFillColorRGB(0, 0, 0)
            text(title, 13.5, y+2, 138, 6.75, True)
        for (label, value), w in zip(fields, widths):
            if label:
                text(label, x+.5, y+1, w-3, 6.25, True)
            text(value, x+.5, y+9, w-3)
            x += w
        y += h

    def section(title):
        nonlocal y, pending_title
        line(y)
        if 'NÃO IDENTIFICADO' in title:
            text(title, 195, y+2, 380, 6.75)
            y += 17
            return
        if title != 'INFORMAÇÕES COMPLEMENTARES':
            pending_title = title
            return
        c.setFillColorRGB(.94, .94, .94)
        c.rect(13, 842-y-12, 565, 12, stroke=0, fill=1)
        c.setFillColorRGB(0, 0, 0)
        text(title, 13.5, y+1, 560, 6.75, True)
        y += 13

    # Same compact monochrome structure and A4 proportions as the government sample.
    c.setFillColorRGB(.94, .94, .94)
    c.rect(13, 798, 565, 36, stroke=0, fill=1)
    c.setFillColorRGB(0, 0, 0)
    logo = Path(__file__).with_name('assets') / 'nfse_logo.png'
    if logo.exists():
        c.drawImage(str(logo), 14, 805, width=116, height=23, mask='auto')
    text('DANFSe v2.0', 282, 16, 140, 9, True)
    text('Documento Auxiliar da NFS-e', 247, 27, 180, 9, True)
    if dados['ambiente'] == '2':
        text('NFS-e SEM VALIDADE JURÍDICA', 224, 38, 210, 7, True, 'red')
    cidade = get('xLocEmi') or '-'
    uf_emitente = get('emit/enderNac/UF')
    if uf_emitente and not cidade.endswith(uf_emitente):
        cidade += ' / ' + uf_emitente
    text('Município: ' + cidade, 437, 16, 140, 7)
    text('Ambiente Gerador: ' + {'1':'Sistema Próprio do Município','2':'Sistema Nacional da NFS-e'}.get(get('ambGer'), get('ambGer') or '-'), 437, 27, 140, 6)
    text('Tipo de Ambiente: ' + {'1':'Produção','2':'Homologação'}.get(dados['ambiente'], '-'), 437, 35, 140, 6)
    line(y)
    row([('CHAVE DE ACESSO DA NFS-e', dados['chave'])], [435], 20.25)
    qr = QrCodeWidget(url_consulta_publica(dados['chave'], dados['ambiente']))
    bounds = qr.getBounds()
    drawing = Drawing(48, 48, transform=[48/(bounds[2]-bounds[0]), 0, 0, 48/(bounds[3]-bounds[1]), 0, 0])
    drawing.add(qr)
    renderPDF.draw(drawing, c, 485, 737)
    text('A autenticidade desta NFS-e pode ser verificada pela leitura deste código QR ou pela consulta da chave de acesso no portal nacional da NFS-e', 444, 108, 131, 6)
    row([('NÚMERO DA NFS-e', dados['numero']), ('COMPETÊNCIA DA NFS-e', date(d('dCompet'))), ('DATA E HORA DA EMISSÃO DA NFS-e', date(get('dhProc')))], [145,145,145])
    row([('NÚMERO DA DPS', d('nDPS')), ('SÉRIE DA DPS', d('serie')), ('DATA E HORA DA EMISSÃO DA DPS', date(d('dhEmi')))], [145,145,145])
    row([('EMITENTE DA NFS-e', {'1':'Prestador','2':'Tomador','3':'Intermediário'}.get(d('tpEmit'), '-')), ('SITUAÇÃO DA NFS-e', 'NFS-e Gerada'), ('FINALIDADE', d('finNFSe'))], [145,145,145], 21)

    def person(title, path, emitter=False):
        section(title)
        def p(field):
            return get('emit/'+field) if emitter else d(path+'/'+field)
        row([('CNPJ / CPF / NIF', doc(p('CNPJ') or p('CPF') or p('NIF'))), ('Indicador Municipal (Inscrição)', p('IM')), ('Telefone', p('fone'))], [292,146,147])
        address = 'enderNac' if emitter else 'end'
        city = p(address+'/xMun') or p(address+'/xLoc')
        uf = p(address+'/UF')
        if emitter:
            city = city or get('xLocEmi')
        cep = p(address+'/CEP') or p(address+'/endNac/CEP')
        ibge = p(address+'/cMun') or p(address+'/endNac/cMun')
        row([('Nome / Nome Empresarial', p('xNome')), ('Município / Sigla UF', ' / '.join(v for v in [city,uf] if v)), ('Código IBGE / CEP', ' / '.join(v for v in [ibge,cep] if v))], [292,146,147])
        address_text = ', '.join(p(address+'/'+v) for v in ['xLgr','nro','xCpl','xBairro'] if p(address+'/'+v))
        row([('Endereço',address_text),('E-mail',p('email'))], [292,293])
        if emitter:
            row([('Simples Nacional na Data de Competência', {'1':'Não optante','2':'Optante - MEI','3':'Optante - ME/EPP'}.get(d('prest/regTrib/opSimpNac'), '-')), ('Regime de Apuração Tributária pelo SN',d('prest/regTrib/regApTribSN'))], [292,293], 21)

    person('PRESTADOR / FORNECEDOR', 'prest', True)
    person('TOMADOR / ADQUIRENTE', 'toma')
    if dps.find('n:dest',ns) is not None:
        person('DESTINATÁRIO DA OPERAÇÃO', 'dest')
    else:
        section('DESTINATÁRIO DA OPERAÇÃO NÃO IDENTIFICADO NA NFS-e')
    if dps.find('n:interm',ns) is not None:
        person('INTERMEDIÁRIO DA OPERAÇÃO', 'interm')
    else:
        section('INTERMEDIÁRIO DA OPERAÇÃO NÃO IDENTIFICADO NA NFS-e')
    section('SERVIÇO PRESTADO')
    code = d('serv/cServ/cTribNac')
    code = '.'.join([code[:2],code[2:4],code[4:]]) if len(code)==6 else code
    row([('Código de Tributação Nacional/Municipal', code+' / '+(d('serv/cServ/cTribMun') or '-')), ('Código da NBS', d('serv/cServ/cNBS')), ('Local da Prestação / Sigla UF / País', get('xLocPrestacao') or d('serv/locPrest/cLocPrestacao'))])
    if get('xTribMun') or get('xTribNac'):
        row([('',get('xTribMun') or get('xTribNac'))], height=16)
    row([('Descrição do Serviço', d('serv/cServ/xDescServ'))])
    section('TRIBUTAÇÃO MUNICIPAL (ISSQN)')
    row([('Tipo de Tributação do ISSQN', {'1':'Operação Tributável','2':'Imunidade','3':'Exportação de Serviço','4':'Não incidência'}.get(d('valores/trib/tribMun/tribISSQN'), '-')), ('Município / Sigla UF / País de Incidência do ISSQN', get('xLocIncid') or get('cLocIncid'))])
    row([('BC ISSQN',money(get('valores/vBC'))), ('Alíquota Aplicada',pct(get('valores/pAliqAplic'))), ('Retenção do ISSQN', {'1':'Não Retido','2':'Retido pelo Tomador','3':'Retido pelo Intermediário'}.get(d('valores/trib/tribMun/tpRetISSQN'), '-')), ('ISSQN Apurado',money(get('valores/vISSQN')))])
    section('TRIBUTAÇÃO FEDERAL (EXCETO CBS)')
    fed = 'valores/trib/tribFed/'
    row([('IRRF',money(d(fed+'vRetIRRF'))),('Contribuição Previdenciária - Retida',money(d(fed+'vRetCP'))),('Contribuições Sociais - Retidas',money(d(fed+'vRetCSLL')))])
    row([('PIS - Débito Apuração Própria',money(d(fed+'piscofins/vPis'))),('COFINS - Débito Apuração Própria',money(d(fed+'piscofins/vCofins'))),('Descrição Contrib. Sociais - Retidas','-')])
    section('TRIBUTAÇÃO IBS/CBS')
    # Use explicit paths: similarly named tax amounts exist in several XML groups.
    rtc = 'IBSCBS/valores/trib/gIBSCBS/'
    row([('CST / cClassTrib', ' / '.join([d(rtc+'CST') or '-',d(rtc+'cClassTrib') or '-'])), ('Indicador de Operação / Código IBGE Incidência', ' / '.join([d('IBSCBS/cIndOp') or '-',get('IBSCBS/cLocalidadeIncid') or '-']))])
    row([('Exclusões e Reduções da Base de Cálculo', money(get('IBSCBS/valores/vCalcDR'))),('Base de Cálculo Após Exclusões e Reduções',money(get('IBSCBS/valores/vBC'))),('Red. Alíquota IBS / Red. Alíquota CBS', '-'),('Alíquota - IBS UF / IBS Mun', ' / '.join([get('IBSCBS/valores/uf/pIBSUF') or '-',get('IBSCBS/valores/mun/pIBSMun') or '-']))])
    row([('Alíq. Efetiva Municipal - IBS',pct(get('IBSCBS/valores/mun/pAliqEfetMun'))),('Valor Apurado Municipal - IBS',money(get('IBSCBS/totCIBS/gIBS/gIBSMun/vIBSMun'))),('Alíq. Efetiva Estadual - IBS',pct(get('IBSCBS/valores/uf/pAliqEfetUF'))),('Valor Apurado Estadual - IBS',money(get('IBSCBS/totCIBS/gIBS/gIBSUF/vIBSUF')))])
    row([('Valor Total Apurado - IBS',money(get('IBSCBS/totCIBS/gIBS/vIBSTot'))),('Alíquota - CBS',pct(get('IBSCBS/valores/fed/pCBS'))),('Alíquota Efetiva - CBS',pct(get('IBSCBS/valores/fed/pAliqEfetCBS'))),('Valor Total Apurado - CBS',money(get('IBSCBS/totCIBS/gCBS/vCBS')))])
    section('VALOR TOTAL DA NFS-e')
    row([('VALOR DA OPERAÇÃO / SERVIÇO',money(d('valores/vServPrest/vServ'))),('Desconto Incondicionado',money(d('valores/vDescCondIncond/vDescIncond'))),('Desconto Condicionado',money(d('valores/vDescCondIncond/vDescCond')))])
    row([('Total das Retenções (ISSQN / Federais)',money(get('valores/vTotalRet'))),('VALOR LÍQUIDO DA NFS-e',money(get('valores/vLiq'))),('Total do IBS/CBS',money(get('IBSCBS/totCIBS/vTotIBSCBS'))),('VALOR LÍQUIDO DA NFS-e + IBS/CBS',money(get('IBSCBS/totCIBS/vTotNF')))])
    section('INFORMAÇÕES COMPLEMENTARES')
    extra = d('serv/infoCompl/xInfComp')
    taxes = [d('valores/trib/totTrib/vTotTrib/'+v) for v in ['vTotTribFed','vTotTribEst','vTotTribMun']]
    if any(taxes):
        extra += '\nTotais aproximados dos Tributos cfe. Lei nº 12.741/2012: Federais: '+money(taxes[0])+'; Estaduais: '+money(taxes[1])+'; Municipais: '+money(taxes[2])+';'
    row([('',extra)],height=30)
    if y > 795:
        raise ValueError('Os dados desta nota excedem uma página A4 no DANFSe. Revise a extensão dos campos antes de gerar o PDF.')
    c.setLineWidth(1)
    c.rect(5,5,585,832,stroke=1,fill=0)
    c.showPage()
    c.save()
    return out.getvalue()
