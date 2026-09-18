import unittest
from unittest.mock import MagicMock

from dsystem_erp.services.conciliacao import esta_baixado, instalar_protecao_conciliacao


class ConciliacaoTests(unittest.TestCase):
    def test_exige_baixa_integral_com_data(self):
        for status in ("Pago", "Recebido"):
            self.assertTrue(esta_baixado({"status": status, "data_baixa": "18/09/2026"}))
            self.assertFalse(esta_baixado({"status": status}))
        for status in ("Aberto", "Pago parcial", "Recebido parcial", "Cancelado", "Baixado por perda", "Renegociado"):
            self.assertFalse(esta_baixado({"status": status, "data_baixa": "18/09/2026"}))

    def test_instala_bloqueios_em_ambas_as_tabelas_sem_apagar_triggers(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = None
        instalar_protecao_conciliacao(cursor)
        sqls = [chamada.args[0] for chamada in cursor.execute.call_args_list]
        criacoes = [sql for sql in sqls if sql.startswith("CREATE TRIGGER")]
        self.assertEqual(len(criacoes), 6)
        for tabela, status in (("contas_pagar", "Pago"), ("contas_receber", "Recebido")):
            atualizacao = next(sql for sql in criacoes if f"BEFORE UPDATE ON `{tabela}`" in sql)
            self.assertIn(f"COALESCE(OLD.status,'') <> '{status}'", atualizacao)
            self.assertIn("OLD.data_baixa", atualizacao)
            self.assertIn("NEW.data_conciliacao", atualizacao)
            self.assertIn("OLD.conciliado", atualizacao)
            self.assertIn("SIGNAL SQLSTATE '45000'", atualizacao)

    def test_reinicio_nao_recria_protecoes_existentes(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = {"TRIGGER_NAME": "existente"}
        instalar_protecao_conciliacao(cursor)
        self.assertEqual(cursor.execute.call_count, 6)
        self.assertTrue(all(c.args[0].startswith("SELECT") for c in cursor.execute.call_args_list))
