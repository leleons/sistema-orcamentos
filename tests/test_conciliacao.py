import unittest
from unittest.mock import MagicMock

from dsystem_erp.services.conciliacao import esta_baixado, instalar_protecao_conciliacao


class ConciliacaoTests(unittest.TestCase):
    def test_adapter_bloqueia_conciliado_sem_trigger(self):
        from dsystem_erp.db import CompatCursor
        cursor = MagicMock()
        cursor.fetchall.return_value = [{"conciliado": "Sim", "status": "Pago", "data_baixa": "2026-09-21"}]
        with self.assertRaisesRegex(ValueError, "bloqueada"):
            CompatCursor(cursor).execute("UPDATE contas_pagar SET valor_total=? WHERE id=?", (100, 7))
        self.assertEqual(cursor.execute.call_count, 1)
        self.assertIn("FOR UPDATE", cursor.execute.call_args.args[0])
        self.assertEqual(cursor.execute.call_args.args[1], (7,))

    def test_adapter_exige_baixa_antes_de_conciliar(self):
        from dsystem_erp.db import CompatCursor
        cursor = MagicMock()
        cursor.fetchall.return_value = [{"conciliado": "Não", "status": "Aberto", "data_baixa": ""}]
        with self.assertRaisesRegex(ValueError, "baixa integral"):
            CompatCursor(cursor).execute("UPDATE contas_receber SET conciliado=?, data_conciliacao=? WHERE id=?", ("Sim", "2026-09-21", 8))
        self.assertEqual(cursor.execute.call_count, 1)

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
        sqls = [chamada.args[0] for chamada in cursor.execute.call_args_list]
        self.assertTrue(any("log_bin_trust_function_creators" in sql for sql in sqls))
        selects = [sql for sql in sqls if sql.startswith("SELECT")]
        self.assertEqual(len(selects), 6)
        self.assertFalse(any(sql.startswith("CREATE TRIGGER") for sql in sqls))

    def test_sem_super_nao_derruba_inicializacao(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = None

        def executar(sql, *args, **kwargs):
            if str(sql).startswith("CREATE TRIGGER"):
                erro = RuntimeError("1419 (HY000): You do not have the SUPER privilege")
                erro.errno = 1419
                raise erro

        cursor.execute.side_effect = executar
        instalar_protecao_conciliacao(cursor)
