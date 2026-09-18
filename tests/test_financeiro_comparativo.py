from datetime import datetime
import unittest

from dsystem_erp.pages.financeiro import montar_comparativo_pagar_receber


def _parse_data(valor):
    return datetime.strptime(valor, "%Y-%m-%d").date() if valor else None


class FinanceiroComparativoTests(unittest.TestCase):
    def test_comparativo_separa_pagar_receber_e_ignora_cancelados(self):
        registros = [
            {"origem": "Pagar", "data_vencimento": "2026-09-10", "valor_total": 100, "status": "Aberto"},
            {"origem": "Receber", "data_vencimento": "2026-09-15", "valor_total": 250, "status": "Aberto"},
            {"origem": "Pagar", "data_vencimento": "2026-10-01", "valor_total": 50, "status": "Pago"},
            {"origem": "Receber", "data_vencimento": "2026-10-01", "valor_total": 999, "status": "Cancelado"},
        ]

        comparativo = montar_comparativo_pagar_receber(registros, _parse_data)

        self.assertEqual(comparativo, [
            {"Período": "2026-09", "A pagar": 100.0, "A receber": 250.0},
            {"Período": "2026-10", "A pagar": 50.0, "A receber": 0.0},
        ])


if __name__ == "__main__":
    unittest.main()
