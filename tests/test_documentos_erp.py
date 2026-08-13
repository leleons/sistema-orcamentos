import unittest

from dsystem_erp.services.email_exports import (
    gerar_excel_emails,
    gerar_pdf_emails,
    preparar_tabela_emails,
)
from dsystem_erp.services.orcamento_pdf import (
    dados_orcamento_base,
    gerar_pdf_orcamento_empresa,
    itens_orcamento_normalizados,
    nome_arquivo_orcamento,
)


class OrcamentoPdfTests(unittest.TestCase):
    def test_normaliza_itens_e_calcula_total_ausente(self):
        itens = itens_orcamento_normalizados(
            '[{"descricao":"Teclado","qtd":"2","vunit":"R$ 25,50","tipo":"Produto"}]'
        )

        self.assertEqual(itens[0]["d"], "Teclado")
        self.assertEqual(itens[0]["q"], 2)
        self.assertEqual(itens[0]["t"], 51.0)
        self.assertEqual(itens[0]["tipo_item"], "Produto")

    def test_nome_do_arquivo_remove_caracteres_inseguros(self):
        nome = nome_arquivo_orcamento("10/2026", "LC Printer & Filhos")
        self.assertEqual(nome, "orcamento_10_2026_LC_Printer_Filhos.pdf")

    def test_gera_pdf_valido_de_orcamento(self):
        dados = dados_orcamento_base(
            "42",
            "Cliente Teste",
            "00.000.000/0001-00",
            [{"d": "Serviço técnico", "q": 1, "v": 100, "t": 100}],
            "PIX",
        )

        pdf = gerar_pdf_orcamento_empresa(dados, "Dsystem Tecnologia")

        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertGreater(len(pdf), 500)


class EmailExportsTests(unittest.TestCase):
    def setUp(self):
        self.rows = [
            {
                "id": 1,
                "cliente_vinculado": "Empresa",
                "funcionario": "Pessoa",
                "email": "pessoa@example.com",
                "senha": "segredo123",
            }
        ]

    def test_oculta_senha_por_padrao(self):
        tabela = preparar_tabela_emails(self.rows)
        self.assertNotEqual(tabela[0]["Senha"], "segredo123")

    def test_excel_escapa_titulo_html(self):
        arquivo = gerar_excel_emails(self.rows, "<script>alert(1)</script>")
        self.assertNotIn(b"<script>alert(1)</script>", arquivo)
        self.assertIn(b"&lt;script&gt;", arquivo)

    def test_pdf_tem_assinatura_e_nao_expoe_senha(self):
        arquivo = gerar_pdf_emails(self.rows, "Relatório")
        self.assertTrue(arquivo.startswith(b"%PDF-1.4"))
        self.assertNotIn(b"segredo123", arquivo)


if __name__ == "__main__":
    unittest.main()
