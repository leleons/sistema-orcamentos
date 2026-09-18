import unittest
from datetime import date

from dsystem_erp.services.agenda_recorrencia import (
    gerar_datas_agenda_configurada,
    gerar_datas_recorrentes,
)


class AgendaRecorrenciaTests(unittest.TestCase):
    def test_dias_especificos_da_semana(self):
        datas = gerar_datas_recorrentes(date(2026, 8, 3), "Dias da semana", 2, {0, 2})
        self.assertEqual(datas, [date(2026, 8, 3), date(2026, 8, 5), date(2026, 8, 10), date(2026, 8, 12)])

    def test_mensal_ajusta_fim_do_mes(self):
        datas = gerar_datas_recorrentes(date(2026, 1, 31), "Mensalmente", 3)
        self.assertEqual(datas, [date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 31)])

    def test_anual_ajusta_ano_bissexto(self):
        datas = gerar_datas_recorrentes(date(2024, 2, 29), "Anualmente", 3)
        self.assertEqual(datas, [date(2024, 2, 29), date(2025, 2, 28), date(2026, 2, 28)])

    def test_semanal_permite_escolher_dia_da_semana(self):
        datas = gerar_datas_agenda_configurada(
            date(2026, 9, 10), "Semanalmente", quantidade=3, dia_semana=0
        )
        self.assertEqual(datas, [date(2026, 9, 14), date(2026, 9, 21), date(2026, 9, 28)])

    def test_mensal_permite_escolher_dia_e_ajusta_mes_curto(self):
        datas = gerar_datas_agenda_configurada(
            date(2026, 1, 10), "Mensalmente", quantidade=3, dia_mes=31
        )
        self.assertEqual(datas, [date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 31)])

    def test_anual_permite_escolher_data(self):
        datas = gerar_datas_agenda_configurada(
            date(2026, 9, 10), "Anualmente", quantidade=2,
            data_anual=date(2026, 12, 5),
        )
        self.assertEqual(datas, [date(2026, 12, 5), date(2027, 12, 5)])

    def test_indefinida_respeita_horizonte(self):
        datas = gerar_datas_agenda_configurada(
            date(2026, 9, 10), "Diariamente", horizonte=date(2026, 9, 12)
        )
        self.assertEqual(datas, [date(2026, 9, 10), date(2026, 9, 11), date(2026, 9, 12)])


if __name__ == "__main__":
    unittest.main()
