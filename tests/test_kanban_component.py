import copy
import unittest

from dsystem_erp.kanban_component import evento_da_revisao, resultado_da_revisao, revisao_quadro
from dsystem_erp.services.recepcao_kanban import alteracoes_do_quadro, montar_quadro_equipamentos


class KanbanComponentTests(unittest.TestCase):
    def setUp(self):
        self.itens = [
            {"id": 1, "os_id": 1, "kanban_status": "Recebido", "kanban_ordem": 0},
            {"id": 2, "os_id": 1, "kanban_status": "Recebido", "kanban_ordem": 1},
        ]
        self.quadro, self.mapa = montar_quadro_equipamentos(self.itens)

    def test_revisao_muda_com_filtro_ou_movimento(self):
        original = revisao_quadro(self.quadro)
        novo = copy.deepcopy(self.quadro)
        novo[1]["items"].append(novo[0]["items"].pop())
        self.assertNotEqual(original, revisao_quadro(novo))
        self.assertEqual(original, revisao_quadro(copy.deepcopy(self.quadro)))

    def test_descarta_evento_antigo_e_retorno_invalido(self):
        for valor in (None, [], {"revisao": "antiga", "colunas": self.quadro}, {"revisao": "atual", "colunas": "invalido"}):
            self.assertIsNone(resultado_da_revisao(valor, "atual"))
        self.assertEqual(resultado_da_revisao({"revisao": "atual", "colunas": self.quadro}, "atual"), self.quadro)

    def test_valida_clique_e_movimento_da_revisao_atual(self):
        self.assertEqual(
            evento_da_revisao({"revisao": "atual", "acao": "abrir", "cartao": "Chamado #1", "evento_id": "1"}, "atual"),
            {"acao": "abrir", "cartao": "Chamado #1", "evento_id": "1"},
        )
        self.assertEqual(
            evento_da_revisao({"revisao": "atual", "acao": "mover", "colunas": self.quadro, "evento_id": "2"}, "atual"),
            {"acao": "mover", "colunas": self.quadro, "evento_id": "2"},
        )
        self.assertIsNone(
            evento_da_revisao({"revisao": "antiga", "acao": "abrir", "cartao": "Chamado #1"}, "atual")
        )

    def test_rejeita_quadro_parcial_duplicado_e_malformado(self):
        duplicado = copy.deepcopy(self.quadro)
        duplicado[1]["items"].append(duplicado[0]["items"][0])
        for valor in (None, {}, [None] * 7, self.quadro[:-1], duplicado):
            self.assertEqual(alteracoes_do_quadro(valor, self.itens, self.mapa), [])

    def test_movimento_e_reordenacao_sao_salvos_uma_vez(self):
        novo = copy.deepcopy(self.quadro)
        novo[1]["items"].append(novo[0]["items"].pop(0))
        mudancas = alteracoes_do_quadro(novo, self.itens, self.mapa)
        self.assertEqual(len(mudancas), 2)
        for mudanca in mudancas:
            item = next(x for x in self.itens if x["id"] == mudanca["id"])
            item.update(kanban_status=mudanca["status"], kanban_ordem=mudanca["ordem"])
        self.assertEqual(alteracoes_do_quadro(novo, self.itens, self.mapa), [])
