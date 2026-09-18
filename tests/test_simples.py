import unittest
from unittest.mock import patch
from dsystem_erp.services.simples import situacao_da_consulta, validar_situacao
from dsystem_erp.pages.simples import atualizar_cadastros


class SimplesTests(unittest.TestCase):
    def test_busca_regime_atual_por_documento_sem_confundir_cliente_e_prestador(self):
        from unittest.mock import MagicMock
        from dsystem_erp.services.simples import buscar_situacao_salva
        conn = MagicMock()
        conn.cursor().fetchall.return_value = [{"situacao_simples_nacional": "2"}]
        self.assertEqual(buscar_situacao_salva(lambda: conn, "23.524.449/0001-54"), "2")
        self.assertEqual(conn.cursor().execute.call_args.args[1], ("23524449000154",))
        conn.cursor().fetchall.return_value = [{"situacao_simples_nacional": "3"}]
        self.assertEqual(buscar_situacao_salva(lambda: conn, "23524449000154"), "3")
        conn.cursor().fetchall.return_value = [{"situacao_simples_nacional": "2"}, {"situacao_simples_nacional": "3"}]
        self.assertEqual(buscar_situacao_salva(lambda: conn, "23524449000154"), "")

    def test_regimes_e_dados_incompletos(self):
        for simples, mei, esperado in [(False, False, "1"), (True, True, "2"), (True, False, "3"), (None, None, ""), (True, None, ""), (False, True, "")]:
            self.assertEqual(situacao_da_consulta({"opcao_pelo_simples": simples, "opcao_pelo_mei": mei}), esperado)

    def test_obrigatorio_apenas_empresa_emissora(self):
        for situacao in ("", "NA", "SIM"):
            with self.assertRaises(ValueError):
                validar_situacao("23.524.449/0001-54", "Sim", situacao)
        validar_situacao("12345678900", "Sim", "NA")
        validar_situacao("23524449000154", "Não", "")
        validar_situacao("23524449000154", "Sim", "2")

    def test_lote_preserva_desconhecido_e_consulta_cnpj_uma_vez(self):
        from unittest.mock import MagicMock
        st, conn = MagicMock(), MagicMock()
        clientes = [{"id": 1, "cnpj": "23524449000154"}, {"id": 2, "cnpj": "23.524.449/0001-54"}, {"id": 3, "cnpj": "12345678900"}]
        with patch("dsystem_erp.pages.simples.consultar_cnpj", return_value={"situacao_simples_nacional": ""}) as consulta:
            resultado = atualizar_cadastros(st, lambda: conn, clientes)
        self.assertEqual(consulta.call_count, 1)
        self.assertEqual(len(resultado), 3)
        self.assertEqual(conn.cursor().execute.call_count, 1)
        self.assertEqual(conn.cursor().execute.call_args.args[1], ("NA", "", 3, "12345678900"))


if __name__ == "__main__":
    unittest.main()
