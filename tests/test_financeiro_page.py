import unittest
import ast
import inspect

from dsystem_erp.pages.financeiro import (
    abrir_lancamento_no_historico,
    preparar_abertura_financeira,
    limpar_novo_recebimento,
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
    def test_status_do_cadastro_e_da_baixa_possuem_chaves_distintas(self):
        arvore = ast.parse(inspect.getsource(renderizar_conta_financeira))
        chaves = {}
        for node in ast.walk(arvore):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            rotulo = node.args[0]
            if isinstance(rotulo, ast.Constant) and rotulo.value in ("Status:", "Novo status:"):
                chave = next(k.value for k in node.keywords if k.arg == "key")
                chaves[rotulo.value] = ast.unparse(chave)
        self.assertEqual(len(chaves), 2)
        self.assertNotEqual(chaves["Status:"], chaves["Novo status:"])
        self.assertIn("id_baixa", chaves["Novo status:"])

    def test_limpa_recebimento_apos_sucesso_preservando_historico(self):
        estado = {"contas_receber_novo_cliente": "Cliente", "rec_terceiro_valor": 100,
                  "contas_receber_anexo_novo": b"anexo", "contas_receber_busca": "filtro",
                  "financeiro_historico_selecionado_contas_receber": 7}
        self.assertFalse(limpar_novo_recebimento(estado))
        self.assertEqual(estado["rec_terceiro_valor"], 100)
        estado["limpar_novo_recebimento"] = True
        self.assertTrue(limpar_novo_recebimento(estado))
        self.assertEqual(estado, {"contas_receber_busca": "filtro",
                                 "financeiro_historico_selecionado_contas_receber": 7})

    def test_abre_lancamento_exato_e_limpa_filtros_que_o_esconderiam(self):
        estado = {
            "contas_pagar_status": "Pago",
            "contas_pagar_busca": "outro fornecedor",
            "contas_pagar_venc": "2026-01-01",
            "contas_pagar_filtro_conciliacao": "Conciliados",
        }

        pagina = abrir_lancamento_no_historico(estado, "Pagar", 27)

        self.assertEqual(pagina, "Contas a Pagar")
        self.assertEqual(estado["financeiro_historico_selecionado_contas_pagar"], 27)
        self.assertNotIn("contas_pagar_aba_ativa", estado)
        self.assertEqual(estado["contas_pagar_aba_destino"], "Histórico e baixa")
        self.assertEqual(estado["contas_pagar_status"], "Pago")
        preparar_abertura_financeira(estado, "contas_pagar")
        self.assertEqual(estado["contas_pagar_status"], "Todos")
        self.assertEqual(estado["contas_pagar_busca"], "")
        self.assertIsNone(estado["contas_pagar_venc"])
        self.assertEqual(estado["contas_pagar_dashboard_versao"], 1)
        self.assertEqual(estado["contas_pagar_historico_versao"], 1)
        estado["contas_pagar_busca"] = "nova busca"
        preparar_abertura_financeira(estado, "contas_pagar")
        self.assertEqual(estado["contas_pagar_busca"], "nova busca")
        self.assertEqual(estado["contas_pagar_historico_versao"], 1)

    def test_abre_conta_a_receber(self):
        estado = {}

        pagina = abrir_lancamento_no_historico(estado, "Receber", 8)

        self.assertEqual(pagina, "Contas a Receber")
        self.assertEqual(estado["financeiro_historico_selecionado_contas_receber"], 8)

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
