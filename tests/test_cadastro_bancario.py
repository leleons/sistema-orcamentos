import unittest
from unittest.mock import MagicMock, patch
from dsystem_erp.pages import financeiro


class CadastroBancarioTests(unittest.TestCase):
    def test_comum_nao_recebe_opcoes_ou_conta_atual(self):
        st = MagicMock(session_state={"is_admin": 0, "modulo_gerencial": 0})
        coluna = MagicMock()
        with patch.object(financeiro, "st", st, create=True):
            valor = financeiro.selecionar_conta(coluna, "Conta", ["Banco privado"], "Conta existente", "conta")
        self.assertEqual(valor, "Conta existente")
        coluna.selectbox.assert_not_called()
        self.assertNotIn("Conta existente", str(coluna.mock_calls))
        self.assertNotIn("Banco privado", str(coluna.mock_calls))

    def test_gerencial_seleciona_ativos_e_preserva_historico(self):
        st = MagicMock(session_state={"modulo_gerencial": 1})
        coluna = MagicMock()
        with patch.object(financeiro, "st", st, create=True):
            financeiro.selecionar_conta(coluna, "Conta", ["Banco ativo"], "Banco antigo", "conta", True)
        args, kwargs = coluna.selectbox.call_args
        self.assertEqual(args[1], ["", "Banco ativo", "Banco antigo"])
        self.assertTrue(kwargs["disabled"])
