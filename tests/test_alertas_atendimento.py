import unittest
from datetime import datetime

from dsystem_erp.services.alertas_atendimento import agendamentos_proximos, chamado_esta_aberto, ids_novos
from dsystem_erp.utils.datas import data_extenso_br


class AlertasAtendimentoTests(unittest.TestCase):
    def test_chamado_aberto(self):
        self.assertTrue(chamado_esta_aberto({"status": "Novo"}))
        self.assertFalse(chamado_esta_aberto({"status": "Concluído"}))

    def test_ids_novos_nao_disparam_na_primeira_leitura(self):
        self.assertEqual(ids_novos([{"id": 2}, {"id": 4}], None), ([], 4))
        self.assertEqual(ids_novos([{"id": 2}, {"id": 4}, {"id": 5}], 4), ([5], 5))

    def test_agendamento_ate_trinta_minutos(self):
        itens = [{"id": 1, "data_visita": "2026-08-05", "hora_inicio": "10:20", "status": "Agendado"}]
        self.assertEqual(len(agendamentos_proximos(itens, datetime(2026, 8, 5, 10, 0))), 1)
        self.assertEqual(len(agendamentos_proximos(itens, datetime(2026, 8, 5, 9, 0))), 0)

    def test_data_por_extenso_em_portugues(self):
        self.assertEqual(data_extenso_br("2026-08-05"), "quarta-feira, 5 de agosto de 2026")


if __name__ == "__main__":
    unittest.main()
