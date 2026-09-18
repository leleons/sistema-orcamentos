import unittest

from dsystem_erp.pages.financeiro import (
    lancamento_esta_conciliado,
    opcoes_contas_financeiras,
    renderizar_cadastros_financeiros,
    renderizar_conta_financeira,
    renderizar_lancamentos_financeiros,
    total_itens_fatura_cartao,
    validar_prestador_terceirizado,
)


class FakeStreamlit:
    def __init__(self):
        self.erros = []

    def error(self, mensagem):
        self.erros.append(mensagem)


class FinanceiroPageTests(unittest.TestCase):
    def test_conciliacao_reconhece_valores_persistidos(self):
        self.assertTrue(lancamento_esta_conciliado({"conciliado": "Sim"}))
        self.assertTrue(lancamento_esta_conciliado({"conciliado": 1}))
        self.assertFalse(lancamento_esta_conciliado({"conciliado": "Não"}))
        self.assertFalse(lancamento_esta_conciliado(None))

    def test_itens_da_fatura_compoem_valor_original(self):
        itens = [{"valor": 10.25}, {"valor": "20.10"}, {"valor": -5}, {"valor": None}]
        self.assertEqual(total_itens_fatura_cartao(itens), 30.35)

    def test_contas_financeiras_viram_opcoes_sem_repeticao(self):
        registros = [
            {"tipo": "Conta bancária", "nome": "Banco A"},
            {"tipo": "Conta bancária", "nome": "Banco A"},
            {"tipo": "Caixa físico", "nome": "Caixa Loja"},
            {"tipo": "Boleto", "nome": ""},
        ]
        self.assertEqual(
            opcoes_contas_financeiras(registros),
            ["Conta bancária — Banco A", "Caixa físico — Caixa Loja"],
        )

    def test_valida_dados_do_prestador_terceirizado(self):
        self.assertIsNone(validar_prestador_terceirizado(False, "", 0, ""))
        self.assertIn("prestador", validar_prestador_terceirizado(True, "", 100, "Serviço"))
        self.assertIn("valor", validar_prestador_terceirizado(True, "Maria", 0, "Serviço"))
        self.assertIn("histórico", validar_prestador_terceirizado(True, "Maria", 100, ""))
        self.assertIsNone(validar_prestador_terceirizado(True, "Maria", 100, "Instalação"))

    def test_bloqueia_contas_sem_permissao(self):
        st = FakeStreamlit()

        renderizar_conta_financeira(
            {"st": st, "tem_permissao": lambda permissao: False}, "receber"
        )

        self.assertEqual(st.erros, ["Você não tem permissão para acessar este módulo."])

    def test_bloqueia_cadastros_sem_permissao(self):
        st = FakeStreamlit()

        renderizar_cadastros_financeiros(
            {"st": st, "tem_permissao": lambda permissao: False}
        )

        self.assertEqual(st.erros, ["Você não tem permissão para acessar estes cadastros."])

    def test_bloqueia_lancamentos_sem_permissao(self):
        st = FakeStreamlit()

        renderizar_lancamentos_financeiros(
            {"st": st, "tem_permissao": lambda permissao: False}
        )

        self.assertEqual(
            st.erros,
            ["Você não tem permissão para acessar os lançamentos financeiros."],
        )


if __name__ == "__main__":
    unittest.main()
