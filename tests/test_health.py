import tempfile
import unittest
from pathlib import Path

from dsystem_erp.services.health import HealthCheck, health_to_row, resumo_checks, status_path


class HealthTests(unittest.TestCase):
    def test_resumo_checks(self):
        checks = [
            HealthCheck("Banco", "OK", "ok"),
            HealthCheck("Backup", "AVISO", "sem backup"),
            HealthCheck("Disco", "ERRO", "cheio"),
        ]
        self.assertEqual(resumo_checks(checks), {"total": 3, "ok": 1, "avisos": 1, "erros": 1})

    def test_status_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            check = status_path(Path(tmp), "Pasta", "existe", "nao existe")
            self.assertTrue(check.ok)
            self.assertEqual(check.status, "OK")

    def test_health_to_row(self):
        row = health_to_row(HealthCheck("Banco", "OK", "Conectado", "localhost"))
        self.assertEqual(row["Área"], "Banco")
        self.assertEqual(row["Status"], "OK")


if __name__ == "__main__":
    unittest.main()
