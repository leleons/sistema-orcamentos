import unittest
from decimal import Decimal

from dsystem_erp.services.precificacao_estoque import calcular_preco_revenda, preco_revenda_produto


class PrecificacaoEstoqueTests(unittest.TestCase):
    def test_calculo_com_custos_percentuais(self):
        self.assertEqual(calcular_preco_revenda(100, 20, 10, 25), 165)

    def test_ajuste_pode_aumentar_ou_reduzir(self):
        self.assertEqual(calcular_preco_revenda(100, 0, 0, 20, -10), 108)

    def test_produto_antigo_preserva_valor_venda(self):
        self.assertEqual(preco_revenda_produto({"valor_venda": "35,90"}), Decimal("35.90"))
