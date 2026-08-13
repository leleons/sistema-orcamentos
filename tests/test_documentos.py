import unittest

from dsystem_erp.services.documentos import gerar_excel_tabela, gerar_pdf_tabela_simples


class DocumentosTests(unittest.TestCase):
    def test_gera_excel_html_com_titulo_e_dados_escapados(self):
        conteudo = gerar_excel_tabela([{"Cliente": "<Empresa>", "Valor": "10"}], "Relatorio")

        texto = conteudo.decode("utf-8")
        self.assertIn("<h2>Relatorio</h2>", texto)
        self.assertIn("&lt;Empresa&gt;", texto)

    def test_gera_pdf_simples(self):
        try:
            conteudo = gerar_pdf_tabela_simples([{"Cliente": "Empresa", "Valor": "10"}], "Relatorio")
        except RuntimeError as ex:
            self.skipTest(str(ex))

        self.assertTrue(conteudo.startswith(b"%PDF"))


if __name__ == "__main__":
    unittest.main()
