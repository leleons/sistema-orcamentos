import unittest

from dsystem_erp.pages.financeiro import (
    renderizar_cadastros_financeiros,
    renderizar_conta_financeira,
    renderizar_lancamentos_financeiros,
)


class FakeStreamlit:
    def __init__(self):
        self.erros = []

    def error(self, mensagem):
        self.erros.append(mensagem)


class FinanceiroPageTests(unittest.TestCase):
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
