import unittest
from datetime import date

from dsystem_erp.services.faturamento_parcelas import (
    data_primeiro_vencimento,
    gerar_parcelas_faturamento,
    quantidade_parcelas_faturamento,
)


class FaturamentoParcelasTests(unittest.TestCase):
    def test_interpreta_opcoes_da_tela(self):
        self.assertEqual(quantidade_parcelas_faturamento("Não"), 1)
        self.assertEqual(quantidade_parcelas_faturamento("6x"), 6)
        self.assertEqual(quantidade_parcelas_faturamento("12 parcelas"), 12)

    def test_interpreta_datas_brasileira_e_iso(self):
        self.assertEqual(data_primeiro_vencimento("31/01/2026"), date(2026, 1, 31))
        self.assertEqual(data_primeiro_vencimento("2026-02-15"), date(2026, 2, 15))

    def test_gera_titulos_individuais_sem_perder_centavos(self):
        parcelas = gerar_parcelas_faturamento({
            "id": 25,
            "valor_total": 100,
            "parcelas": "3x",
            "vencimento": "31/01/2026",
            "forma_pag": "Boleto",
        })
        self.assertEqual([p["documento"] for p in parcelas], [
            "FAT-25-P01-03", "FAT-25-P02-03", "FAT-25-P03-03",
        ])
        self.assertEqual([p["vencimento"] for p in parcelas], [
            "31/01/2026", "28/02/2026", "31/03/2026",
        ])
        self.assertEqual(sum(p["valor"] for p in parcelas), 100)

    def test_a_vista_mantem_documento_compativel(self):
        parcelas = gerar_parcelas_faturamento({
            "id": 8, "valor_total": 50, "parcelas": "Não", "vencimento": "01/04/2026"
        })
        self.assertEqual(len(parcelas), 1)
        self.assertEqual(parcelas[0]["documento"], "FAT-8")


if __name__ == "__main__":
    unittest.main()
