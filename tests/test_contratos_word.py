import io
import unittest
from unittest.mock import MagicMock
from zipfile import ZipFile
from datetime import date
from docx import Document
from pypdf import PdfReader, PdfWriter
from streamlit.testing.v1 import AppTest
from dsystem_erp.services.contrato_pdf import MODELOS_CONTRATO, gerar_contrato_pdf
from dsystem_erp.services.contratos import salvar_contrato_gerado
from dsystem_erp.services.contratos_modelos import WORD, abrir_modelo, slots_modelo, preencher_cadastro
from dsystem_erp.services.contratos_vigencia import preencher_datas_word
from dsystem_erp.services.contratos_pj import MODELO_PJ
from dsystem_erp.services.contratos_word import gerar_contrato_word, word_do_pdf, texto_sem_paginacao_pdf


def texto_word(b):
    return '\n'.join(p.text for p in Document(io.BytesIO(b)).paragraphs)


class ContratosWordTests(unittest.TestCase):
    def test_todos_modelos_word_preenchidos_editaveis_e_preservados(self):
        for tipo in WORD:
            slots = slots_modelo(tipo)
            valores = {s['chave']: 'José & Maria '+s['chave'] for s in slots}
            valores.update(preencher_datas_word(tipo,slots,date(2026,10,8),date(2027,10,8)))
            word = gerar_contrato_word(tipo,{},valores=valores)
            texto = texto_word(word)
            self.assertIn('José & Maria',texto)
            self.assertIn('08/10/2027',texto)
            self.assertNotIn('____',texto)
            with ZipFile(io.BytesIO(word)) as saida, ZipFile(io.BytesIO(abrir_modelo(tipo))) as origem:
                for nome in origem.namelist():
                    if nome != 'word/document.xml':
                        self.assertEqual(origem.read(nome),saida.read(nome))

    def test_pdf_nativos_word_com_clausulas_campos_checkbox_e_complementos(self):
        for tipo in MODELOS_CONTRATO:
            dados = dict(nome='José Destinatário',cnpj='11122233344',endereco='Rua Teste',data_contrato='08/10/2026',
                escopo_especifico='Atividade detalhada. '*120+'FIM ESCOPO', atendimento_remoto=True,
                curso='Computação',instituicao_ensino='Escola Exemplo',jornada='30 horas',
                clausulas=[dict(titulo='Cláusula confirmada',texto='Conteúdo completo da cláusula adicional.')])
            pdf = gerar_contrato_pdf(tipo,dados)
            word = gerar_contrato_word(tipo,dados,pdf=pdf)
            texto = texto_word(word)
            self.assertIn('José Destinatário',texto)
            self.assertIn('11122233344',texto)
            self.assertIn('08/10/2027',texto)
            self.assertIn('Conteúdo completo da cláusula adicional.',texto)
            self.assertNotIn('word/media/',str(ZipFile(io.BytesIO(word)).namelist()))
            # Cada trecho visível e cada valor lógico estão presentes; não é um
            # resumo de cláusulas nem imagem não editável do PDF.
            compacto = ' '.join(texto.split())
            leitor = PdfReader(io.BytesIO(pdf))
            for pagina in leitor.pages:
                for linha in pagina.extract_text().splitlines():
                    limpa = texto_sem_paginacao_pdf(linha)
                    if limpa.strip():
                        self.assertIn(' '.join(limpa.split()),compacto)
            self.assertNotRegex(texto,r'Página \d+ de \d+')
            self.assertIn('Assinatura',texto)
            self.assertIn('________________________________',texto)
            for nome,campo in leitor.get_fields().items():
                v = campo.get('/V','')
                if str(v).strip() and campo.get('/FT') != '/Btn':
                    self.assertIn(str(v),texto,nome)
            if tipo == 'Suporte Tecnológico':
                self.assertIn('Atendimento remoto: Marcado',texto)
                self.assertIn('FIM ESCOPO',compacto)

    def test_persistencia_salva_word_no_mesmo_registro_sem_apagar_original(self):
        conn = MagicMock()
        conn.cursor.return_value.lastrowid = 52
        id_ = salvar_contrato_gerado(conn,tipo=MODELO_PJ,parte_tipo='Funcionário',parte_id=3,parte_nome='Pessoa',
            nome_arquivo='contrato.pdf',arquivo=b'%PDF exemplo',arquivo_word=b'PK exemplo',nome_arquivo_word='contrato.docx')
        sql,args = conn.cursor.return_value.execute.call_args.args
        self.assertEqual(id_,52)
        self.assertEqual(args[6],b'%PDF exemplo')
        self.assertEqual(args[-2:],(b'PK exemplo','contrato.docx'))
        self.assertIn('arquivo_word',sql)
        conn.commit.assert_called_once()

    def test_downloads_word_novo_e_pdf_antigo_sem_gerar_outro_contrato(self):
        fonte = '''
import streamlit as st
from dsystem_erp.pages.contratos_download import renderizar_downloads
from dsystem_erp.services.contrato_pdf import gerar_contrato_pdf
from dsystem_erp.services.contratos_word import word_do_pdf
st.session_state.setdefault('pdf',gerar_contrato_pdf('Estágio',dict(nome='Pessoa do contrato salvo',cnpj='123',data_contrato='08/10/2026')))
c = dict(id=1,tipo='Estágio',nome_arquivo='historico.pdf',arquivo=st.session_state['pdf'])
if st.checkbox('Word salvo',key='word_salvo'):
    c['arquivo_word'] = word_do_pdf(c['arquivo'])
renderizar_downloads(st,c)
'''
        app = AppTest.from_string(fonte,default_timeout=15).run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.get('download_button')),1)
        app.button[0].click().run()
        self.assertFalse(app.error)
        self.assertEqual(len(app.get('download_button')),2)
        # Acesso público por chave: AppTest não expõe filtered_state em todas as versões.
        import hashlib
        chave = 'contrato_1_' + hashlib.sha256(app.session_state['pdf']).hexdigest()
        self.assertIn('Pessoa do contrato salvo',texto_word(app.session_state[chave]))
        app.checkbox(key='word_salvo').check().run()
        self.assertFalse(app.exception)
        self.assertFalse(app.button)
        self.assertEqual(len(app.get('download_button')),2)

    def test_pdf_sem_texto_nao_finge_word_editavel(self):
        escritor = PdfWriter()
        escritor.add_blank_page(width=595,height=842)
        pdf = io.BytesIO()
        escritor.write(pdf)
        with self.assertRaisesRegex(ValueError,'não contém texto editável'):
            word_do_pdf(pdf.getvalue())

    def test_estagio_ordem_trimestres_e_declaracoes_nao_muda(self):
        dados = dict(nome='Pessoa Teste',data_contrato='08/10/2026',jornada='30 horas')
        texto = texto_word(gerar_contrato_word('Estágio',dados))
        self.assertLess(texto.index('1º trimestre'),texto.index('Integração, suporte básico'))
        self.assertLess(texto.index('1º trimestre'),texto.index('2º trimestre'))
        self.assertLess(texto.index('2º trimestre'),texto.index('3º trimestre'))
        self.assertLess(texto.index('3º trimestre'),texto.index('4º trimestre'))
        self.assertLess(texto.index('Tratarei dados pessoais somente'),texto.index('Não compartilharei'))

    def test_pj_repetidos_assinatura_acompanham_edicao_e_download_duplo(self):
        from tests.test_funcionario_pj import BASE_TELA
        app = AppTest.from_string(BASE_TELA,default_timeout=15).run()
        for c in app.text_input:
            if c.label in ('Valor mensal', 'Horas por dia', 'Deslocamento mensal', 'Dia do pagamento'):
                c.set_value({'Valor mensal':'1.950,00','Horas por dia':'9','Deslocamento mensal':'300,00','Dia do pagamento':'10'}[c.label])
            elif c.label == 'Nome da testemunha 1':
                c.set_value('Testemunha Alfa')
            elif c.label == 'Nome da testemunha 2':
                c.set_value('Testemunha Beta')
            elif c.label == 'CPF da testemunha 1':
                c.set_value('11111111111')
            elif c.label == 'CPF da testemunha 2':
                c.set_value('22222222222')
            elif c.label == 'Razão social da empresa do prestador PJ':
                c.set_value('Empresa PJ Editada')
            elif not c.value:
                c.set_value('Dado confirmado')
        app.run()
        next(b for b in app.button if b.label == 'Gerar e salvar na aba Contratos').click().run()
        self.assertFalse(app.error)
        self.assertFalse(app.exception)
        resultado = app.session_state['central_contrato_resultado']
        from lxml import etree
        from dsystem_erp.services.contratos_modelos import W
        with ZipFile(io.BytesIO(resultado['word'])) as pacote:
            raiz = etree.fromstring(pacote.read('word/document.xml'))
        self.assertFalse([r for r in raiz.iter(W+'highlight') if r.get(W+'val') == 'yellow'])
        self.assertFalse([r for r in raiz.iter(W+'shd') if r.get(W+'fill', '').upper() == 'FFFF00'])
        self.assertTrue(list(raiz.iter(W+'b')))
        texto = texto_word(resultado['word'])
        from pypdf import PdfReader
        texto_pdf = '\n'.join(p.extract_text() for p in PdfReader(io.BytesIO(resultado['arquivo'])).pages)
        for documento in (texto, texto_pdf):
            normalizado = ' '.join(documento.split())
            self.assertIn('valor mensal de R$ 1.950,00', normalizado)
            self.assertIn('9 horas por dia', normalizado)
            self.assertIn('R$ 300,00 em dinheiro', normalizado)
            self.assertNotIn('R$ 200,00', normalizado)
            for rotulo in ('Assinatura da CONTRATANTE', 'Assinatura da CONTRATADA', 'Assinatura da testemunha 1', 'Assinatura da testemunha 2'):
                self.assertEqual(documento.count(rotulo), 1)
            for valor in ('Testemunha Alfa', 'Testemunha Beta', '11111111111', '22222222222'):
                self.assertEqual(documento.count(valor), 1)
        self.assertEqual(texto.count('CONTRATADA: Empresa PJ Editada'),2)
        self.assertEqual(texto.count('11.222.333/0001-44'),2)
        self.assertIn('CPF: 11122233344',texto)
        self.assertIn('CNPJ sob o nº 11.222.333/0001-44',texto)
        self.assertEqual(len(app.get('download_button')),3) # modelo, PDF, Word
        args = app.session_state['banco_teste'].cursor.return_value.execute.call_args.args[1]
        self.assertEqual(args[-2],resultado['word'])


if __name__ == '__main__':
    unittest.main()
