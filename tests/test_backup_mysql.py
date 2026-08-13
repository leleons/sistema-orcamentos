import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import backup_mysql


class BackupMysqlTests(unittest.TestCase):
    def test_listar_backups_mostra_metadados(self):
        with tempfile.TemporaryDirectory() as tmp:
            backup_dir = Path(tmp)
            arquivo = backup_dir / "banco_dsystem_full_20260714_100000.sql.gz"
            arquivo.write_bytes(b"backup")
            arquivo.with_suffix(arquivo.suffix + ".json").write_text(
                json.dumps({"tipo": "full"}),
                encoding="utf-8",
            )

            saida = io.StringIO()
            with mock.patch.object(backup_mysql, "BACKUP_DIR", backup_dir), contextlib.redirect_stdout(saida):
                backup_mysql.listar_backups()

            texto = saida.getvalue()
            self.assertIn("full", texto)
            self.assertIn(str(arquivo), texto)


if __name__ == "__main__":
    unittest.main()
