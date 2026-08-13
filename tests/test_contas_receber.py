import unittest
from datetime import date

from dsystem_erp.services.contas_receber import calcular_impostos, calcular_margem_lucro, gerar_parcelas


class ContasReceberTests(unittest.TestCase):
    def test_margem_desconta_imposto_e_custo(self):
        margem = calcular_margem_lucro(1000, 100, 300, 2)
        self.assertEqual(float(margem["lucro_estimado"]), 300.0)
        self.assertEqual(float(margem["margem_percentual"]), 33.33)
    def test_impostos(self):
        itens, total = calcular_impostos(1000, {"ISS": 5, "IRRF": 1.5})
        self.assertEqual(total, 65)
        self.assertEqual(itens[0]["valor"], 50)

    def test_parcelas_fecham_o_total(self):
        parcelas = gerar_parcelas(100, 3, date(2026, 1, 31), "Boleto")
        self.assertEqual(sum(p["valor"] for p in parcelas), 100)
        self.assertEqual(parcelas[1]["vencimento"], "28/02/2026")


if __name__ == "__main__":
    unittest.main()
