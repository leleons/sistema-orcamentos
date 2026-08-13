import unittest

from dsystem_erp.pages.infraestrutura import renderizar_infraestrutura_ti


class InfraestruturaPageTests(unittest.TestCase):
    def test_page_is_importable(self):
        self.assertTrue(callable(renderizar_infraestrutura_ti))


if __name__ == "__main__":
    unittest.main()
