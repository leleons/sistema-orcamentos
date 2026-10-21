import io
import unittest
from datetime import date, datetime
from zoneinfo import ZoneInfo
from pypdf import PdfReader
from streamlit.testing.v1 import AppTest
from dsystem_erp.services.contratos_modelos import WORD, slots_modelo
from dsystem_erp.services.contratos_vigencia import preencher_datas_word
from dsystem_erp.services.contrato_pdf import MODELOS_CONTRATO, gerar_contrato_pdf
from dsystem_erp.services.contratos_word import word_do_pdf
from tests.test_contratos_word import texto_word
from tests.test_funcionario_pj import BASE_TELA


class ContratosDataAssinaturaTests(unittest.TestCase):
    def test_fechamento_independente_da_vigencia_em_todos_word(self):
        for tipo in WORD:
            slots = slots_modelo(tipo)
            inicio, fim = date(2025, 5, 11), date(2026, 5, 11)
            padrao = preencher_datas_word(tipo, slots, inicio, fim)
            atual = preencher_datas_word(tipo, slots, inicio, fim, assinatura=date(2026, 10, 8))
            fechamento = 42 if 'Locação' in tipo else 25
            for s in slots:
                if s['paragrafo'] == fechamento:
                    self.assertEqual(atual.get(s['chave']), {'[Dia]':'8', '[Mês]':'outubro', '[Ano]':'2026'}.get(s['token']))
                else:
                    self.assertEqual(atual.get(s['chave']), padrao.get(s['chave']))

    def test_datas_nos_pdfs_nativos_e_word_sem_simular_assinaturas(self):
        for tipo in MODELOS_CONTRATO:
            pdf = gerar_contrato_pdf(tipo, dict(nome='Pessoa de teste', data_contrato='11/05/2025', data_assinatura='08/10/2026'))
            leitor = PdfReader(io.BytesIO(pdf))
            campos = leitor.get_fields()
            self.assertEqual(campos['data_emissao']['/V'], '08/10/2026')
            if 'data_assinatura' in campos:
                self.assertEqual(campos['data_assinatura']['/V'], '08/10/2026')
            for nome, campo in campos.items():
                if nome.startswith('assinatura_'):
                    self.assertFalse(campo.get('/V'))
            capa = leitor.pages[0].extract_text()
            self.assertIn('11/05/2025', capa)
            self.assertIn('11/05/2026', capa)
            self.assertIn('08/10/2026', texto_word(word_do_pdf(pdf)))

    def test_tela_assinatura_hoje_outra_e_inicio_sem_reusar_download(self):
        app = AppTest.from_string(BASE_TELA, default_timeout=15).run()
        prefixo = 'central_contrato_Prestação de Serviços PJ_1_pj'
        app.date_input(key=prefixo+'_inicio').set_value(date(2025,5,11)).run()
        app.radio(key=prefixo+'_assinatura_modo').set_value('Hoje').run()
        hoje = datetime.now(ZoneInfo('America/Sao_Paulo')).date()
        self.assertTrue(any(f'Data indicada para assinatura: {hoje:%d/%m/%Y}' in c.value for c in app.caption))
        app.radio(key=prefixo+'_assinatura_modo').set_value('Outra data').run()
        app.date_input(key=prefixo+'_assinatura_data').set_value(date(2026,10,8)).run()
        for campo in app.text_input:
            if not campo.value:
                campo.set_value('Dado de teste')
        app.run()
        next(b for b in app.button if b.label == 'Gerar e salvar na aba Contratos').click().run()
        self.assertFalse(app.exception)
        self.assertFalse(app.error)
        resultado = app.session_state['central_contrato_resultado']
        pdf = '\n'.join(p.extract_text() for p in PdfReader(io.BytesIO(resultado['arquivo'])).pages)
        for texto in (pdf, texto_word(resultado['word'])):
            texto = ' '.join(texto.split())
            self.assertIn('8 de outubro de 2026', texto)
            self.assertIn('11/05/2025 a 11/05/2026', texto)
            self.assertNotIn('entra em vigor na data de sua assinatura', texto)
        args = app.session_state['banco_teste'].cursor.return_value.execute.call_args.args[1]
        self.assertEqual(args[9:11], ('11/05/2025','11/05/2026'))
        app.radio(key=prefixo+'_assinatura_modo').set_value('Mesma data do início').run()
        self.assertEqual(len(app.get('download_button')), 1)  # somente modelo original
        self.assertTrue(any('Data indicada para assinatura: 11/05/2025' in c.value for c in app.caption))


if __name__ == '__main__':
    unittest.main()
