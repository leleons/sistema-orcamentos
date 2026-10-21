"""Word editável: modelos DOCX originais ou conteúdo completo do PDF preenchido.

O formulário PDF continua sendo o original. Sua versão Word recompõe a ordem
de leitura e inclui os valores lógicos dos campos, não imagens de páginas.
"""
import io
import re
from pathlib import Path

MIME_WORD = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'


def texto_sem_paginacao_pdf(texto):
    """Retira somente contadores/chrome do PDF que ficariam falsos no Word."""
    linhas = []
    for linha in texto.splitlines():
        if re.fullmatch(r'Página\s+(?:\d+\s+de\s+\d+|adicional\s+\d+)',linha.strip(),re.I):
            continue
        if re.fullmatch(r'D-System Tecnologia\s*\|\s*(?:Documento (?:preenchível|controlado)(?:\s*\|\s*\d+ páginas)?|Contrato de Estágio)(?:\s+Página\s+\d+\s+de\s+\d+)?',linha.strip()):
            continue
        linhas.append(linha)
    return '\n'.join(linhas)


def nome_word(nome_pdf):
    return str(Path(nome_pdf).with_suffix('.docx'))


def word_do_pdf(pdf, titulo='Contrato'):
    from docx import Document
    from docx.shared import Pt, RGBColor
    from pypdf import PdfReader
    import pdfplumber

    leitor = PdfReader(io.BytesIO(bytes(pdf)))
    documento = Document()
    normal = documento.styles['Normal']
    normal.font.name = 'Arial'
    normal.font.size = Pt(10)
    normal.paragraph_format.space_after = Pt(2)
    normal.paragraph_format.line_spacing = 1.15
    documento.core_properties.title = titulo
    sec = documento.sections[0]
    sec.page_width, sec.page_height = Pt(float(leitor.pages[0].mediabox.width)), Pt(float(leitor.pages[0].mediabox.height))
    sec.left_margin = sec.right_margin = Pt(56.7)
    sec.top_margin = sec.bottom_margin = Pt(50)
    campos = leitor.get_fields() or {}
    # Coordenadas dos glifos evitam o defeito de visitor_text do pypdf: alguns
    # trechos são liberados com matriz (0,0) ao trocar a fonte/contexto gráfico.
    with pdfplumber.open(io.BytesIO(bytes(pdf))) as documento_pdf:
        palavras_paginas = [p.extract_words(extra_attrs=['fontname','size'], x_tolerance=2, y_tolerance=2)
                            for p in documento_pdf.pages]
    total_textos = 0
    for indice, pagina in enumerate(leitor.pages):
        if indice:
            documento.add_page_break()
        blocos = []

        linhas = {}
        for palavra in palavras_paginas[indice]:
            linhas.setdefault(round(palavra['bottom']/3)*3, []).append(palavra)
        for linha in linhas.values():
            linha.sort(key=lambda p:p['x0'])
            texto = texto_sem_paginacao_pdf(' '.join(p['text'] for p in linha))
            if texto.strip():
                blocos.append((float(pagina.mediabox.height)-min(p['top'] for p in linha),
                    min(p['x0'] for p in linha), texto.strip(), max(p['size'] for p in linha),
                    all('Bold' in p['fontname'] for p in linha)))
        for ref in pagina.get('/Annots', []):
            widget = ref.get_object()
            if widget.get('/Subtype') != '/Widget':
                continue
            campo = widget
            while campo.get('/Parent') and not campo.get('/T'):
                campo = campo['/Parent'].get_object()
            nome = str(campo.get('/T') or '')
            if not nome:
                continue
            logico = campos.get(nome, campo)
            valor = logico.get('/V', '')
            if logico.get('/FT') == '/Btn':
                valor = 'Marcado' if str(valor) not in ('', '/Off') else 'Não marcado'
            elif not str(valor).strip():
                if nome.startswith('assinatura_') or nome == 'data_assinatura':
                    valor = '________________________________'
                else:
                    continue
            rect = widget.get('/Rect')
            if rect:
                rotulo = nome.replace('_', ' ').capitalize()
                blocos.append((float(rect[3])-9, float(rect[0]), f'{rotulo}: {valor}', 10, False))
        # Linhas com a mesma altura são ordenadas da esquerda para a direita.
        blocos.sort(key=lambda b: (-round(b[0]/2)*2, b[1]))
        for _, _, texto, tamanho, negrito in blocos:
            p = documento.add_paragraph()
            if total_textos == 0:
                p.style = documento.styles['Title']
            p.paragraph_format.widow_control = True
            p.paragraph_format.keep_with_next = negrito and len(texto) < 150
            r = p.add_run(texto)
            r.bold = negrito
            r.font.size = Pt(max(10, min(tamanho, 18)))
            r.font.color.rgb = RGBColor(0, 0, 0)
            total_textos += 1
    if not total_textos:
        raise ValueError('Este PDF não contém texto editável. Anexe o arquivo Word original.')
    saida = io.BytesIO()
    documento.save(saida)
    return saida.getvalue()


def gerar_contrato_word(tipo, dados, *, valores=None, prazo='Determinado', impressao='Franquia', pdf=None):
    from dsystem_erp.services.contratos_modelos import WORD, gerar_word
    from dsystem_erp.services.contrato_pdf import gerar_contrato_pdf
    if tipo in WORD:
        return gerar_word(tipo, valores or {}, prazo, impressao)
    return word_do_pdf(pdf if pdf is not None else gerar_contrato_pdf(tipo, dados), tipo)
