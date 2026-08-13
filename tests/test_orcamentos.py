import unittest
from datetime import date

from dsystem_erp.services.orcamentos import (
    aplicar_encargos_renegociacao,
    numero_renegociacao,
    orcamento_esta_vencido,
    total_geral_orcamento,
    total_item_orcamento,
)


class OrcamentosTests(unittest.TestCase):
    def test_totais(self):
        self.assertEqual(total_item_orcamento(12.5, 3), 37.5)
        self.assertEqual(total_geral_orcamento([{"v": 10, "q": 2}, {"t": 5.5}]), 25.5)

    def test_vencimento_dez_dias(self):
        orc = {"data_orc": "01/08/2026", "status": "Aberto"}
        self.assertFalse(orcamento_esta_vencido(orc, date(2026, 8, 11)))
        self.assertTrue(orcamento_esta_vencido(orc, date(2026, 8, 12)))
        self.assertFalse(orcamento_esta_vencido({**orc, "status": "Aprovado e lançado"}, date(2026, 9, 1)))

    def test_numero_renegociacao(self):
        self.assertEqual(numero_renegociacao("441", 1), "441-R2")
        self.assertEqual(numero_renegociacao("441-R2", 2), "441-R3")

    def test_encargos_opcionais(self):
        itens = aplicar_encargos_renegociacao([{"d": "Item", "v": 100, "q": 2}], 10, 25)
        self.assertEqual(itens[0]["t"], 220)
        self.assertEqual(itens[1]["t"], 25)


if __name__ == "__main__":
    unittest.main()
