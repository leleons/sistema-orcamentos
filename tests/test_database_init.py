import unittest

from dsystem_erp.services.database_init import garantir_tabela_nova


class TabelaCorrompidaError(Exception):
    errno = 1932


class CursorFake:
    def __init__(self, corrompida=False):
        self.corrompida = corrompida
        self.comandos = []

    def execute(self, sql):
        self.comandos.append(sql)
        if self.corrompida and sql.startswith("SELECT 1"):
            self.corrompida = False
            raise TabelaCorrompidaError()

    def fetchone(self):
        return {"ok": 1}


class ConnectionFake:
    def __init__(self):
        self.commits = 0

    def commit(self):
        self.commits += 1


class DatabaseInitTests(unittest.TestCase):
    def test_valida_tabela_existente_sem_recriar(self):
        conn = ConnectionFake()
        cursor = CursorFake()
        sql = "CREATE TABLE IF NOT EXISTS teste (id INT)"

        garantir_tabela_nova(conn, cursor, "teste", sql)

        self.assertEqual(cursor.comandos, [sql, "SELECT 1 FROM `teste` LIMIT 1"])
        self.assertEqual(conn.commits, 0)

    def test_recria_tabela_quando_mysql_indica_corrupcao(self):
        conn = ConnectionFake()
        cursor = CursorFake(corrompida=True)
        sql = "CREATE TABLE IF NOT EXISTS teste (id INT)"

        garantir_tabela_nova(conn, cursor, "teste", sql)

        self.assertIn("DROP TABLE IF EXISTS `teste`", cursor.comandos)
        self.assertEqual(cursor.comandos[-1], sql)
        self.assertEqual(conn.commits, 1)


if __name__ == "__main__":
    unittest.main()
