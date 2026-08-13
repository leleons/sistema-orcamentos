import unittest

from dsystem_erp.migrations import garantir_coluna


class CursorFake:
    def __init__(self, existe=False):
        self.existe = existe
        self.comandos = []

    def execute(self, sql, params=None):
        self.comandos.append((sql, params))

    def fetchone(self):
        return {"Field": "boleto"} if self.existe else None


class MigrationTests(unittest.TestCase):
    def test_garantir_coluna_cria_quando_nao_existe(self):
        cursor = CursorFake(existe=False)
        criado = garantir_coluna(cursor, "faturamento", "boleto", "TEXT")

        self.assertTrue(criado)
        self.assertEqual(cursor.comandos[-1][0], "ALTER TABLE `faturamento` ADD COLUMN `boleto` TEXT")

    def test_garantir_coluna_nao_recria_quando_existe(self):
        cursor = CursorFake(existe=True)
        criado = garantir_coluna(cursor, "faturamento", "boleto", "TEXT")

        self.assertFalse(criado)
        self.assertEqual(len(cursor.comandos), 1)


if __name__ == "__main__":
    unittest.main()
