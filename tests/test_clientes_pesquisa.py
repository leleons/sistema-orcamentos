import unittest

from dsystem_erp.pages.clientes import (
    buscar_cliente_cadastrado_por_cpf,
    filtrar_clientes_cadastrados,
)


class PesquisaClientesTests(unittest.TestCase):
    def setUp(self):
        self.clientes = [
            {"id": 1, "nome": "João Silva", "codigo_cliente": "CLI001",
             "cnpj": "123.456.789-00", "documento_chave": "12345678900",
             "portal_username": "12345678900"},
            {"id": 2, "nome": "Empresa Azul", "codigo_cliente": "CLI002",
             "cnpj": "12.345.678/0001-90", "documento_chave": "12345678000190"},
            {"id": 3, "nome": "Cadastro antigo", "codigo_cliente": "CLI003",
             "cnpj": "", "documento_chave": "98765432100"},
        ]

    def ids(self, termo):
        return [item["id"] for item in filtrar_clientes_cadastrados(self.clientes, termo)]

    def test_pesquisa_cpf_formatado_ou_apenas_numeros(self):
        self.assertEqual(self.ids("123.456.789-00"), [1])
        self.assertEqual(self.ids("12345678900"), [1])

    def test_pesquisa_cpf_parcial(self):
        self.assertEqual(self.ids("987.654"), [3])

    def test_pesquisa_cnpj_nome_e_codigo_continuam_funcionando(self):
        self.assertEqual(self.ids("12.345.678/0001-90"), [2])
        self.assertEqual(self.ids("empresa azul"), [2])
        self.assertEqual(self.ids("cli001"), [1])

    def test_pesquisa_vazia_mostra_todos(self):
        self.assertEqual(self.ids(""), [1, 2, 3])

    def test_consulta_separada_localiza_cpf_exato(self):
        encontrado = buscar_cliente_cadastrado_por_cpf(self.clientes, "123.456.789-00")
        self.assertEqual(encontrado["id"], 1)
        self.assertIsNone(buscar_cliente_cadastrado_por_cpf(self.clientes, "111.222.333-44"))

    def test_consulta_separada_rejeita_cnpj_e_cpf_incompleto(self):
        for documento in ("123.456", "12.345.678/0001-90"):
            with self.subTest(documento=documento), self.assertRaises(ValueError):
                buscar_cliente_cadastrado_por_cpf(self.clientes, documento)


if __name__ == "__main__":
    unittest.main()
