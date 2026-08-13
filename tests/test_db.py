import unittest

from dsystem_erp.db import CompatConnection, CompatCursor, CompatRow


class RawCursorFake:
    def __init__(self, antes=None, lastrowid=15):
        self.antes = antes
        self.lastrowid = lastrowid
        self.comandos = []
        self.fechado = False

    def execute(self, sql, params=None):
        self.comandos.append((sql, params))
        return "ok"

    def executemany(self, sql, params=None):
        self.comandos.append((sql, params))

    def fetchone(self):
        return self.antes

    def fetchall(self):
        return [self.antes] if self.antes else []

    def close(self):
        self.fechado = True


class RawConnectionFake:
    def __init__(self, cursor):
        self.cursor_fake = cursor
        self.kwargs_cursor = None

    def cursor(self, **kwargs):
        self.kwargs_cursor = kwargs
        return self.cursor_fake

    def commit(self):
        return "commit"

    def rollback(self):
        return "rollback"

    def close(self):
        return "close"


class DatabaseCompatibilityTests(unittest.TestCase):
    def test_linha_permite_acesso_por_nome_e_posicao(self):
        linha = CompatRow({"id": 10, "nome": "Cliente"})

        self.assertEqual(linha[0], 10)
        self.assertEqual(linha["nome"], "Cliente")

    def test_cursor_adapta_placeholder_e_registra_insert(self):
        raw = RawCursorFake(lastrowid=31)
        logs = []
        cursor = CompatCursor(raw, registrar_log=lambda *args: logs.append(args))

        cursor.execute("INSERT INTO clientes (nome) VALUES (?)", ("Empresa",))

        self.assertIn("VALUES (%s)", raw.comandos[0][0])
        self.assertEqual(cursor.lastrowid, 31)
        self.assertEqual(logs[0][1:4], ("insert", "clientes", 31))
        self.assertEqual(logs[0][-1]["novo"]["nome"], "Empresa")

    def test_update_captura_estado_anterior(self):
        raw = RawCursorFake(antes={"id": 4, "nome": "Antigo"})
        logs = []
        cursor = CompatCursor(raw, registrar_log=lambda *args: logs.append(args))

        cursor.execute("UPDATE clientes SET nome=? WHERE id=?", ("Novo", 4))

        self.assertTrue(raw.comandos[0][0].startswith("SELECT * FROM `clientes`"))
        self.assertTrue(raw.comandos[1][0].startswith("UPDATE clientes"))
        self.assertEqual(logs[0][-1]["antes"]["nome"], "Antigo")
        self.assertEqual(logs[0][-1]["alterado"]["nome"], "Novo")

    def test_conexao_solicita_cursor_em_formato_dicionario(self):
        raw_cursor = RawCursorFake()
        raw_conn = RawConnectionFake(raw_cursor)

        cursor = CompatConnection(raw_conn).cursor()

        self.assertIsInstance(cursor, CompatCursor)
        self.assertEqual(raw_conn.kwargs_cursor, {"dictionary": True})


if __name__ == "__main__":
    unittest.main()
