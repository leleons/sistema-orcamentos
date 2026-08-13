import unittest

from dsystem_erp.pages.system_tools import renderizar_backups_sistema, renderizar_diagnostico_sistema


class SystemToolsPageTests(unittest.TestCase):
    def test_system_tools_pages_are_importable(self):
        self.assertTrue(callable(renderizar_backups_sistema))
        self.assertTrue(callable(renderizar_diagnostico_sistema))


if __name__ == "__main__":
    unittest.main()
