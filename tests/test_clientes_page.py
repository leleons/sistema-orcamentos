import unittest

from dsystem_erp.pages.clientes import renderizar_cadastro_cliente_fornecedor, validar_redefinicao_senha_portal


class ClientesPageTests(unittest.TestCase):
    def test_senha_vazia_preserva_atual(self):
        validar_redefinicao_senha_portal("", "")

    def test_senha_confirmada(self):
        validar_redefinicao_senha_portal("Teste-1234", "Teste-1234")

    def test_senhas_invalidas(self):
        for senha, confirmacao in [("Teste-1234", "outra"), ("", "Teste-1234"), ("123", "123"), ("        ", "        ")]:
            with self.subTest(senha=senha), self.assertRaises(ValueError):
                validar_redefinicao_senha_portal(senha, confirmacao)

    def test_page_is_importable(self):
        self.assertTrue(callable(renderizar_cadastro_cliente_fornecedor))


if __name__ == "__main__":
    unittest.main()
