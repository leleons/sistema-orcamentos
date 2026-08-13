import unittest
from decimal import Decimal

from dsystem_erp.services.compras import id_melhor_cotacao, total_cotacao


class ComprasTests(unittest.TestCase):
    def test_total_considera_quantidade(self):
        self.assertEqual(total_cotacao("12,50", 4), Decimal("50.00"))

    def test_identifica_menor_valor(self):
        cotacoes = [{"id": 1, "valor_item": 20}, {"id": 2, "valor_item": 18.5}]
        self.assertEqual(id_melhor_cotacao(cotacoes), 2)

    def test_ignora_valor_zero(self):
        self.assertEqual(id_melhor_cotacao([{"id": 1, "valor_item": 0}]), None)
