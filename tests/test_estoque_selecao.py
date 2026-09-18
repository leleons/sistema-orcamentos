import unittest
from pathlib import Path

from dsystem_erp.pages.estoque import (
    codigo_item_estoque,
    nome_produto_estoque,
    sincronizar_selecao_produto_estoque,
    texto_pesquisa_produto_estoque,
)
from dsystem_erp.services.estoque_importacao import normalizar_tem_fonte


class EstoqueSelecaoTests(unittest.TestCase):
    def test_pesquisa_inclui_codigo_completo_sem_erro(self):
        texto = texto_pesquisa_produto_estoque(
            {"produto": "Caixa de passagem", "fornecedor": "Fornecedor A"},
            "01.02.01",
        )

        self.assertIn("caixa de passagem", texto)
        self.assertIn("01.02.01", texto)

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

    def test_codigo_item_e_a_terceira_parte_do_codigo(self):
        produto = {
            "id": 2639,
            "codigo_item": 918,
            "codigo_entrada": "01.01.918",
            "modelo": "KW202",
        }

        self.assertEqual(codigo_item_estoque(produto), 918)
        self.assertEqual(nome_produto_estoque(produto), "KW202")

    def test_codigo_legado_nao_confunde_nome_com_id_comercial(self):
        produto = {
            "id": 47,
            "codigo_entrada": "01.01.Gabinete",
            "produto": "Gabinete",
        }

        self.assertEqual(codigo_item_estoque(produto), 47)
        self.assertEqual(nome_produto_estoque(produto), "Gabinete")

    def test_normaliza_indicacao_de_fonte(self):
        self.assertEqual(normalizar_tem_fonte("sim"), "Sim")
        self.assertEqual(normalizar_tem_fonte("Com fonte"), "Sim")
        self.assertEqual(normalizar_tem_fonte("não"), "Não")

    def test_cadastro_permite_quantidade_inicial_e_registra_movimento(self):
        fonte = (Path(__file__).resolve().parents[1] / "dsystem_erp" / "pages" / "estoque.py").read_text(encoding="utf-8")
        inicio = fonte.index('"Quantidade inicial:"')
        fim = fonte.index("e_min =", inicio)
        self.assertNotIn("disabled=True", fonte[inicio:fim])
        self.assertIn('tipo="Entrada inicial"', fonte)
        self.assertIn('origem="Cadastro do produto"', fonte)


if __name__ == "__main__":
    unittest.main()
