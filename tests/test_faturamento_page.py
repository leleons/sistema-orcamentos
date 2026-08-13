import unittest

from dsystem_erp.pages.faturamento import renderizar_a_faturar, renderizar_faturado


class FaturamentoPageTests(unittest.TestCase):
    def test_a_faturar_page_is_importable(self):
        self.assertTrue(callable(renderizar_a_faturar))

    def test_faturado_page_is_importable(self):
        self.assertTrue(callable(renderizar_faturado))


if __name__ == "__main__":
    unittest.main()
