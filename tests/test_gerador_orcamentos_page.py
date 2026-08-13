import unittest

from dsystem_erp.pages.gerador_orcamentos import renderizar_gerador_orcamentos


class GeradorOrcamentosPageTests(unittest.TestCase):
    def test_page_is_importable(self):
        self.assertTrue(callable(renderizar_gerador_orcamentos))


if __name__ == "__main__":
    unittest.main()
