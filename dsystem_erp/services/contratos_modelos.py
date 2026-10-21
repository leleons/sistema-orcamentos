"""Catálogo central e preenchimento dos modelos originais, sem reescrever cláusulas."""
import io
import re
from pathlib import Path
from zipfile import ZipFile
from lxml import etree

from dsystem_erp.services.contrato_pdf import MODELOS_CONTRATO

WORD = {'Tecnologia e Infraestrutura': 'tecnologia_infraestrutura.docx',
        'Serviços e Locação de Equipamentos': 'servicos_locacao.docx',
        'Prestação de Serviços PJ': 'contrato_dsystem_pj.docx'}
RAIZ = Path(__file__).resolve().parents[2] / 'modelos_contratos' / 'WORD'
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'


def modelos_disponiveis():
    return list(MODELOS_CONTRATO) + list(WORD)


def abrir_modelo(tipo):
    if tipo not in WORD:
        raise ValueError('Modelo Word inválido.')
    return (RAIZ / WORD[tipo]).read_bytes()


def paragrafos_modelo(tipo):
    with ZipFile(io.BytesIO(abrir_modelo(tipo))) as arquivo:
        root = etree.fromstring(arquivo.read('word/document.xml'), etree.XMLParser(resolve_entities=False, no_network=True))
    paras = root.find(W + 'body').findall(W + 'p')
    if tipo in ('Prestação de Serviços PJ', 'Tecnologia e Infraestrutura'):
        substituir_texto(paras[21], 'entra em vigor na data de sua assinatura e terá validade de', 'terá vigência de')
    if tipo == 'Prestação de Serviços PJ':
        # Condições mensais solicitadas pela empresa; não altera o anexo guardado.
        p = paras[11]
        for filho in list(p):
            if filho.tag != W+'pPr':
                p.remove(filho)
        clausulas = (
            '4.1. Pela prestação dos serviços pactuados, a CONTRATANTE pagará à CONTRATADA o valor mensal de R$ [Valor mensal], com prestação de serviços de [Horas por dia] horas por dia.',
            '4.2. A CONTRATANTE pagará à CONTRATADA, separadamente da remuneração dos serviços, o valor mensal de R$ [Deslocamento mensal] em dinheiro, destinado ao deslocamento até a empresa.',
            '4.3. O pagamento mensal dos serviços e do valor de deslocamento será efetuado até o dia [Dia do pagamento] do mês subsequente à prestação do serviço, mediante a apresentação da respectiva Nota Fiscal emitida pela CONTRATADA, acompanhada dos relatórios de atendimento correspondentes.',
        )
        for i, texto in enumerate(clausulas):
            run = etree.SubElement(p, W+'r')
            if i:
                etree.SubElement(run, W+'br')
            etree.SubElement(run, W+'t').text = texto
    return root, paras


def slots_modelo(tipo, prazo='Determinado', impressao='Franquia'):
    _, paras = paragrafos_modelo(tipo)
    slots = []
    for indice, p in enumerate(paras):
        if indice in remover_paragrafos(tipo, prazo, impressao):
            continue
        texto = ''.join(t.text or '' for t in p.iter(W + 't'))
        tokens = list(dict.fromkeys(re.findall(r'\[[^\]]+\]', texto)))
        tokens.extend(re.findall(r'(?:Nome|CPF): _+', texto))
        if tipo == 'Tecnologia e Infraestrutura' and indice == 2:
            tokens.append('``')
        for numero, token in enumerate(tokens):
            if token in ('[1]', '[1, 2]', '[6.1]', '[6.2]'):
                continue  # referências do original, não campos de preenchimento
            if token.startswith('[OPÇÃO '):
                continue
            chave = f'p{indice}_mensal_{numero}' if tipo == 'Prestação de Serviços PJ' and indice == 11 else f'p{indice}_{numero}'
            slots.append(dict(chave=chave, paragrafo=indice, token=token,
                              rotulo=('CPF/CNPJ da contratada' if token == '``' else
                                      token.split(':')[0] + ' da testemunha' if ': _' in token else token[1:-1]), contexto=texto))
    return slots


def remover_paragrafos(tipo, prazo, impressao):
    if tipo != 'Serviços e Locação de Equipamentos':
        return set()
    if prazo not in ('Determinado', 'Indeterminado') or impressao not in ('Franquia', 'Fixo sem franquia', 'Contador'):
        raise ValueError('Selecione prazo e regime de impressão válidos.')
    manter = {'Franquia': 20, 'Fixo sem franquia': 21, 'Contador': 22}[impressao]
    return {13, 15 if prazo == 'Determinado' else 14} | ({20, 21, 22} - {manter})


def endereco(dados):
    return ', '.join(str(dados.get(k) or '').strip() for k in
                     ('endereco', 'numero', 'complemento', 'bairro', 'cidade_estado', 'cep') if dados.get(k))


def preencher_cadastro(tipo, slots, contratante, contratada):
    valores = {}
    for s in slots:
        p, token = s['paragrafo'], s['token']
        parte = None
        if tipo == 'Tecnologia e Infraestrutura':
            parte = contratante if p == 1 else contratada if p == 2 else None
        else:
            parte = contratada if p == 2 else contratante if p == 3 else None
        valor = ''
        if tipo == 'Prestação de Serviços PJ':
            parte = contratante if 'da DSystem' in token else contratada if 'do prestador PJ' in token else None
            if parte is not None:
                if token.startswith('[CNPJ'):
                    valor = parte.get('cnpj') or ''
                elif token.startswith('[Endereço'):
                    valor = endereco(parte)
                elif token.startswith('[Razão social'):
                    valor = parte.get('nome') or ''
                elif token.startswith('[Nome'):
                    valor = parte.get('responsavel_legal') or ''
                elif token.startswith('[CPF'):
                    valor = parte.get('cpf_responsavel') or ''
            valores[s['chave']] = str(valor)
            continue
        if parte is not None:
            if token.startswith(('[Nome da ', '[Nome do Prestador')):
                valor = parte.get('nome') or ''
            elif token.startswith('[Nome do Representante'):
                valor = parte.get('responsavel_legal') or ''
            elif token == '[000.000.000-00]':
                valor = parte.get('cpf_responsavel') or ''
            elif token in ('[00.000.000/0001-00]', '``'):
                valor = parte.get('cnpj') or ''
            elif token.startswith('[Endereço'):
                valor = endereco(parte)
            elif token == '[Cidade/Estado]':
                valor = parte.get('cidade_estado') or ''
        valores[s['chave']] = str(valor)
    return valores


def substituir_texto(paragrafo, antigo, novo):
    """Substitui tokens mesmo divididos entre runs; mantém propriedades e demais textos."""
    nodes = list(paragrafo.iter(W + 't'))
    texto = ''.join(n.text or '' for n in nodes)
    inicio = texto.find(antigo)
    while inicio >= 0:
        fim, pos = inicio + len(antigo), 0
        for node in nodes:
            value = node.text or ''
            a, b = pos, pos + len(value)
            if a < fim and b > inicio:
                node.text = value[:max(0, inicio-a)] + (str(novo) if a <= inicio < b else '') + value[max(0, fim-a):]
                node.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
            pos = b
        texto = ''.join(n.text or '' for n in nodes)
        inicio = texto.find(antigo, inicio + len(str(novo)))


def gerar_word(tipo, valores, prazo='Determinado', impressao='Franquia'):
    root, paras = paragrafos_modelo(tipo)
    slots = slots_modelo(tipo, prazo, impressao)
    faltantes = [s['rotulo'] for s in slots if not str(valores.get(s['chave']) or '').strip()]
    if faltantes:
        raise ValueError('Preencha: ' + ', '.join(faltantes))
    for slot in slots:
        valor = valores[slot['chave']]
        if ': _' in slot['token']:
            valor = slot['token'].split(':')[0] + ': ' + valor
        substituir_texto(paras[slot['paragrafo']], slot['token'], valor)
    if tipo == 'Prestação de Serviços PJ':
        # Somente a área de assinaturas da cópia gerada; o anexo original permanece intacto.
        for indice, rotulo in ((27, 'Assinatura da CONTRATANTE - representante legal da Dsystem'),
                               (29, 'Assinatura da CONTRATADA - titular ou representante legal'),
                               (31, 'Assinatura da testemunha 1'),
                               (32, 'Assinatura da testemunha 2')):
            dados = paras[indice]
            prop = dados.find(W+'pPr')
            if prop is None:
                prop = etree.Element(W+'pPr')
                dados.insert(0, prop)
            etree.SubElement(prop, W+'keepNext')
            etree.SubElement(prop, W+'keepLines')
            assinatura = etree.Element(W+'p')
            pp = etree.SubElement(assinatura, W+'pPr')
            etree.SubElement(pp, W+'spacing', {W+'before':'720', W+'after':'280'})
            bordas = etree.SubElement(pp, W+'pBdr')
            etree.SubElement(bordas, W+'top', {W+'val':'single', W+'sz':'6', W+'space':'4', W+'color':'000000'})
            etree.SubElement(etree.SubElement(assinatura, W+'r'), W+'t').text = rotulo
            dados.addnext(assinatura)
        # Substitui os separadores decorativos antigos pelas linhas identificadas acima.
        for p in paras[26:]:
            if p.find('.//{urn:schemas-microsoft-com:vml}rect') is not None and not ''.join(t.text or '' for t in p.iter(W+'t')):
                p.getparent().remove(p)
    if tipo == 'Serviços e Locação de Equipamentos':
        for p in paras:
            substituir_texto(p, '[OPÇÃO A - PRAZO DETERMINADO]: ', '')
            substituir_texto(p, '[OPÇÃO B - PRAZO INDETERMINADO]: ', '')
    for indice in remover_paragrafos(tipo, prazo, impressao):
        p = paras[indice]
        p.getparent().remove(p)
    # Os realces são instruções visuais do modelo, não do contrato preenchido.
    # Preserva negrito, cores de texto e sombreamentos que não sejam amarelos.
    for realce in list(root.iter(W+'highlight')):
        if realce.get(W+'val', '').lower() == 'yellow':
            realce.getparent().remove(realce)
    for sombra in list(root.iter(W+'shd')):
        if sombra.get(W+'fill', '').upper() == 'FFFF00':
            sombra.getparent().remove(sombra)
    saida = io.BytesIO()
    with ZipFile(io.BytesIO(abrir_modelo(tipo))) as origem, ZipFile(saida, 'w') as destino:
        for part in origem.infolist():
            data = etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True) if part.filename == 'word/document.xml' else origem.read(part.filename)
            destino.writestr(part, data)
    return saida.getvalue()
