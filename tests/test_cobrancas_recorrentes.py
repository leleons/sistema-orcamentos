import unittest
from datetime import date

from dsystem_erp.services.cobrancas_recorrentes import proximo_vencimento, vencimentos_no_periodo


class CobrancasRecorrentesTests(unittest.TestCase):
    def test_mensal_ajusta_fim_do_mes(self):
        self.assertEqual(proximo_vencimento(date(2026, 1, 31), "Mensal"), date(2026, 2, 28))

    def test_vencimentos_respeitam_vigencia(self):
        cobranca = {
            "data_cobranca": "10/08/2026",
            "vigencia_fim": "10/10/2026",
            "periodicidade": "Mensal",
        }
        self.assertEqual(
            vencimentos_no_periodo(cobranca, date(2026, 12, 31)),
            [date(2026, 8, 10), date(2026, 9, 10), date(2026, 10, 10)],
        )


if __name__ == "__main__":
    unittest.main()
