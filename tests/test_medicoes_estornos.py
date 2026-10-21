import unittest
from unittest.mock import MagicMock
from dsystem_erp.services.estoque_notas import cancelar_saida_manual
from dsystem_erp.services.faturamento_medicoes import registrar_medicao, resumo_medicoes


class MedicoesEstornosTests(unittest.TestCase):
    def test_percentuais_saldo_e_conclusao_ignoram_canceladas(self):
        principal = {"valor_total": 1000}
        medicoes = [{"valor_total": 250, "status": "Faturado"},
                    {"valor_total": 750, "status": "Aberto"},
                    {"valor_total": 100, "status": "Cancelado"}]
        resumo = resumo_medicoes(principal, medicoes)
        self.assertEqual(resumo["percentual"], 100)
        self.assertEqual(resumo["percentual_faturado"], 25)
        self.assertEqual(resumo["saldo"], 0)
        self.assertFalse(resumo["concluido"])
        medicoes[1]["status"] = "Faturado"
        self.assertTrue(resumo_medicoes(principal, medicoes)["concluido"])

    def test_estorno_devolve_quantidade_e_impede_repeticao(self):
        conn = MagicMock()
        c = conn.cursor.return_value
        mov = {"produto_id": 9, "tipo": "Saída para cliente", "origem": "Baixa manual", "quantidade": 2}
        c.fetchone.side_effect = [mov, None, {"quantidade": 3}]
        cancelar_saida_manual(conn, 10, "Baixa incorreta", "teste", "2026-09-21")
        self.assertTrue(any(call.args[1] == (5.0, 9) for call in c.execute.call_args_list))
        conn.commit.assert_called_once()
        conn.reset_mock()
        c.fetchone.side_effect = [mov, {"id": 11}]
        with self.assertRaisesRegex(ValueError, "já foi cancelada"):
            cancelar_saida_manual(conn, 10, "De novo", "teste", "2026-09-21")
        conn.commit.assert_not_called()
        conn.rollback.assert_called_once()

    def test_medicao_respeita_saldo_e_numero(self):
        conn = MagicMock()
        c = conn.cursor.return_value
        c.fetchone.return_value = {"modalidade_faturamento": "Por medição", "status": "Aberto", "valor_total": 1000, "cliente": "Teste"}
        c.fetchall.return_value = [{"valor_total": 600, "medicao_numero": "1"}]
        for numero, valor in [("1", 100), ("2", 401)]:
            with self.assertRaises(ValueError):
                registrar_medicao(conn, 4, numero, valor, "2026-09-01", "2026-09-21", "Etapa", "2026-09-30")
        conn.commit.assert_not_called()
        registrar_medicao(conn, 4, "2", 400, "2026-09-01", "2026-09-21", "Etapa", "2026-09-30")
        conn.commit.assert_called_once()
