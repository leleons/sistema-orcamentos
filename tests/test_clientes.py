import unittest

from dsystem_erp.services.clientes import dados_cliente_padrao, montar_endereco_cliente


class ClientesTests(unittest.TestCase):
    def test_montar_endereco_cliente_ignora_vazios(self):
        cliente = {
            "endereco": "Rua Gloria",
            "numero": "25",
            "bairro": "",
            "cidade_estado": "Sabara / MG",
            "cep": "34500-000",
        }
        self.assertEqual(montar_endereco_cliente(cliente), "Rua Gloria - 25 - Sabara / MG - 34500-000")

    def test_dados_cliente_padrao_usa_fallbacks(self):
        cliente = {
            "id": 7,
            "nome": "Empresa Teste",
            "cnpj": "12.345.678/0001-90",
            "telefone_secundario": "31999990000",
            "emails_cobranca": "financeiro@teste.com",
            "contato": "Maria",
            "endereco": "Rua A",
            "numero": "10",
        }
        dados = dados_cliente_padrao(cliente)
        self.assertEqual(dados["nome"], "Empresa Teste")
        self.assertEqual(dados["telefone"], "31999990000")
        self.assertEqual(dados["email"], "financeiro@teste.com")
        self.assertEqual(dados["contato"], "Maria")
        self.assertEqual(dados["endereco"], "Rua A - 10")


if __name__ == "__main__":
    unittest.main()
