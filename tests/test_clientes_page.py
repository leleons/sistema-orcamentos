import unittest

from dsystem_erp.pages.clientes import renderizar_cadastro_cliente_fornecedor


class ClientesPageTests(unittest.TestCase):
    def test_page_is_importable(self):
        self.assertTrue(callable(renderizar_cadastro_cliente_fornecedor))


if __name__ == "__main__":
    unittest.main()
