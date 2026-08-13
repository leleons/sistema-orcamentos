import unittest

from dsystem_erp.services.recepcao_kanban import dados_qr_equipamento, gerar_etiqueta_equipamento, proximo_status


class RecepcaoKanbanTests(unittest.TestCase):
    def test_avanca_e_recua_status(self):
        self.assertEqual(proximo_status("Recebido"), "Triagem / Diagnóstico")
        self.assertEqual(proximo_status("Recebido", -1), "Recebido")

    def test_qr_contem_vinculos(self):
        texto = dados_qr_equipamento({"os_id": 7, "numero_item": "00007-A", "cliente": "ACME", "chamado_id": 3})
        self.assertIn("00007-A", texto)
        self.assertIn("CHAMADO: 3", texto)

    def test_etiqueta_pdf(self):
        pdf = gerar_etiqueta_equipamento({"os_id": 7, "numero_item": "00007-A", "cliente": "ACME", "equipamento": "Notebook"})
        self.assertTrue(pdf.startswith(b"%PDF"))
