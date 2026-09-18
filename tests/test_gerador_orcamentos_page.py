import unittest

from dsystem_erp.pages.gerador_orcamentos import (
    abandonar_edicao_orcamento,
    deve_carregar_orcamento_da_grade,
    manter_orcamento_salvo_em_edicao,
    renderizar_gerador_orcamentos,
)


class GeradorOrcamentosPageTests(unittest.TestCase):
    def test_page_is_importable(self):
        self.assertTrue(callable(renderizar_gerador_orcamentos))

    def test_grade_nao_recarrega_orcamento_durante_edicao(self):
        estado = {
            "orc_em_edicao": {"orc_id": 18},
            "orc_aba_ativa": "Gerar/Editar Orçamento",
        }

        self.assertFalse(deve_carregar_orcamento_da_grade(estado, 18))
        self.assertTrue(deve_carregar_orcamento_da_grade({"orc_em_edicao": None}, 18))

    def test_historico_permite_substituir_orcamento_em_edicao(self):
        estado = {
            "orc_em_edicao": {"orc_id": 18},
            "orc_aba_ativa": "Histórico de Orçamentos",
        }

        self.assertTrue(deve_carregar_orcamento_da_grade(estado, 51))

    def test_salvamento_mantem_orcamento_atualizado_em_edicao(self):
        estado = {"orc_em_edicao": None, "orc_aba_ativa": "Histórico de Orçamentos"}

        manter_orcamento_salvo_em_edicao(
            estado,
            {"orc_id": 18, "numero": "18", "itens": "[]"},
        )

        self.assertEqual(estado["orc_em_edicao"]["orc_id"], 18)
        self.assertEqual(estado["orc_aba_ativa"], "Histórico de Orçamentos")
        self.assertNotIn("orc_aba_destino", estado)

    def test_cancelar_edicao_libera_formulario_novo_e_limpa_grade(self):
        estado = {
            "orc_em_edicao": {"orc_id": 52},
            "orc_form_reset": 3,
            "orc_grade_versao": 7,
        }

        abandonar_edicao_orcamento(estado)

        self.assertIsNone(estado["orc_em_edicao"])
        self.assertEqual(estado["orc_form_reset"], 4)
        self.assertEqual(estado["orc_grade_versao"], 8)
        self.assertTrue(estado["orc_ignorar_grade_uma_vez"])
        self.assertEqual(estado["orc_aba_destino"], "Gerar/Editar Orçamento")


if __name__ == "__main__":
    unittest.main()
