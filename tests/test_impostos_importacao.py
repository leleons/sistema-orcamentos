import io
import unittest
from unittest.mock import Mock, patch

from openpyxl import Workbook
from streamlit.testing.v1 import AppTest

from dsystem_erp.services.impostos_importacao import ler_catalogo, importar_catalogo
from dsystem_erp.services.impostos_cadastro import listar_regras, regras_disponiveis, validar_regra

EMPRESA = '23524449000154'
ADMIN = {'username': 'contador_teste', 'is_admin': 1}


def arquivo(duplicar=False, formula=False):
    w = Workbook()
    p = w.active
    p.title = 'Produtos'
    p.append(['Código SKU', 'Descrição do Item', 'Código Fiscal (NCM)', 'CNAE', 'Anexo Simples', 'CFOP Interno (MG)', 'CFOP Interestadual', 'Origem'])
    row = ['TI001', '=1+1' if formula else 'Produto importado', '8471.30.19', '4751-2/01', 'Anexo I', '5.405', '6.102 / 6.404', '0']
    p.append(row)
    if duplicar:
        p.append(row)
    s = w.create_sheet('Serviços')
    s.append(['Código SKU', 'Descrição do Serviço', 'Código Fiscal (LC 116)', 'CNAE', 'Anexo Simples', 'Alíquota ISS Simples Nacional'])
    s.append(['SRV001', 'Serviço importado', '01.07', '6209-1/00', 'Anexo III', '2,0% a 5,0%'])
    b = io.BytesIO()
    w.save(b)
    return b.getvalue()


class ImportacaoTests(unittest.TestCase):
    def test_mapeamento_sem_inventar_taxas_ou_escolher_cfop(self):
        p, s = ler_catalogo(arquivo(), EMPRESA)
        self.assertEqual(p['ncm'], '84713019')
        self.assertEqual(p['anexo'], 'I')
        self.assertEqual(p['origem_planilha']['CFOP Interestadual'], '6.102 / 6.404')
        self.assertNotIn('cfop', p)
        self.assertNotIn('pis', p)
        self.assertNotIn('aliquota_iss', s)
        self.assertNotIn('codigo_tributacao_nacional', s)
        self.assertEqual(regras_disponiveis([p, s], EMPRESA, 'Produto'), [])
        for r in (p, s):
            self.assertFalse(r['ativo'])
            self.assertFalse(r['confirmado'])
            with self.assertRaises(ValueError):
                validar_regra(r)

    def test_rejeita_duplicados_formulas_arquivo_invalido_e_tamanho(self):
        for b in (arquivo(duplicar=True), arquivo(formula=True), b'invalido', b'x' * (5*1024*1024+1)):
            with self.subTest(tamanho=len(b)), self.assertRaises(ValueError):
                ler_catalogo(b, EMPRESA)

    def test_permissao_antes_do_banco(self):
        conectar = Mock()
        with self.assertRaises(PermissionError):
            importar_catalogo(conectar, arquivo(), EMPRESA, {'username': 'sem_permissao'})
        conectar.assert_not_called()

    def test_importacao_repetida_preserva_existentes_e_isola_empresa(self):
        from tests.test_fiscal_automatico import AutomaticoTests
        f = AutomaticoTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        antes = listar_regras(f.conectar, EMPRESA)
        self.assertEqual(importar_catalogo(f.conectar, arquivo(), EMPRESA, ADMIN), (2, 0))
        self.assertEqual(importar_catalogo(f.conectar, arquivo(), EMPRESA, ADMIN), (0, 2))
        depois = listar_regras(f.conectar, EMPRESA)
        for r in antes:
            self.assertIn(r, depois)
        self.assertEqual(importar_catalogo(f.conectar, arquivo(), '23524449000235', ADMIN), (2, 0))
        self.assertEqual(len(listar_regras(f.conectar, EMPRESA)), len(antes)+2)

    def test_erro_de_gravacao_reverte_lote(self):
        conn = Mock()
        conn.cursor.return_value.fetchone.return_value = None
        conn.cursor.return_value.execute.side_effect = [None, None, None, RuntimeError('falha')]
        with self.assertRaises(RuntimeError):
            importar_catalogo(lambda: conn, arquivo(), EMPRESA, ADMIN)
        conn.rollback.assert_called_once()
        conn.commit.assert_not_called()
        conn.close.assert_called_once()

    def test_previa_interface_nao_grava_sem_confirmacao(self):
        def tela():
            from dsystem_erp.pages.impostos import renderizar_importacao_impostos
            renderizar_importacao_impostos(None, '23524449000154', {'username': 'admin', 'is_admin': 1}, [])
        with patch('streamlit.file_uploader', return_value=io.BytesIO(arquivo())), patch('dsystem_erp.pages.impostos.importar_catalogo') as gravar:
            app = AppTest.from_function(tela, default_timeout=20).run()
            self.assertFalse(app.exception)
            self.assertTrue(app.button[0].disabled)
            self.assertEqual(len(app.dataframe[0].value), 2)
            gravar.assert_not_called()
            app.checkbox[0].check().run()
            self.assertFalse(app.button[0].disabled)
            gravar.assert_not_called()


if __name__ == '__main__':
    unittest.main()
