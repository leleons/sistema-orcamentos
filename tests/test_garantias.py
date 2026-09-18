import unittest
from datetime import date

from dsystem_erp.services.garantias import (
    gerar_pdf_garantia,
    proximo_numero_garantia,
    validade_item_garantia,
)


class GarantiasTests(unittest.TestCase):
    def test_numero_sequencial_por_ano(self):
        self.assertEqual(proximo_numero_garantia(14, 2026), "GAR-2026-00015")

    def test_validade_ajusta_ultimo_dia_do_mes(self):
        self.assertEqual(validade_item_garantia(date(2026, 1, 31), 1), date(2026, 2, 28))

    def test_pdf_contem_documento_valido(self):
        pdf = gerar_pdf_garantia(
            {
                "numero": "GAR-2026-00001", "cliente": "Cliente Teste",
                "cliente_documento": "123.456.789-00", "data_emissao": "2026-09-10",
                "origem": "Faturamento #10", "condicoes": "Condições de teste.",
                "historico": "Serviço concluído.", "criado_por": "teste",
            },
            [{
                "tipo": "Serviço", "descricao": "Instalação e configuração",
                "prazo_meses": 3, "validade": "2026-12-10",
            }],
        )
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertGreater(len(pdf), 1000)


if __name__ == "__main__":
    unittest.main()
