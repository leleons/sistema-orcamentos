import unittest

from dsystem_erp.pages.estoque import sincronizar_selecao_produto_estoque


class EstoqueSelecaoTests(unittest.TestCase):
    def test_selecao_alimenta_movimentacao_edicao_e_exclusao(self):
        estado = {}
        resultado = sincronizar_selecao_produto_estoque(estado, "3")
        self.assertEqual(resultado, 3)
        self.assertEqual(estado["estoque_produto_selecionado"], 3)
        self.assertEqual(estado["estoque_produto_movimentacao_id"], 3)
        self.assertEqual(estado["estoque_id_edicao"], 3)
        self.assertEqual(estado["estoque_id_exclusao"], 3)

    def test_ignora_id_invalido(self):
        estado = {"estoque_id_edicao": 2}
        self.assertIsNone(sincronizar_selecao_produto_estoque(estado, "invalido"))
        self.assertEqual(estado, {"estoque_id_edicao": 2})


if __name__ == "__main__":
    unittest.main()
