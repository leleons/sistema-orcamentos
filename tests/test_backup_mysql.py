import contextlib
import io
import json
import os
import tempfile
import time
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

    def test_limpeza_mantem_somente_dois_backups_mais_recentes(self):
        with tempfile.TemporaryDirectory() as tmp:
            backup_dir = Path(tmp)
            arquivos = []
            for indice, tipo in enumerate(("full", "incremental", "pre-deploy")):
                arquivo = backup_dir / f"banco_dsystem_{tipo}_20260714_10000{indice}.sql.gz"
                arquivo.write_bytes(b"backup")
                arquivo.with_suffix(arquivo.suffix + ".json").write_text("{}", encoding="utf-8")
                instante = time.time() + indice
                os.utime(arquivo, (instante, instante))
                arquivos.append(arquivo)

            with mock.patch.object(backup_mysql, "BACKUP_DIR", backup_dir):
                backup_mysql.cleanup_old_backups("banco_dsystem")

            self.assertFalse(arquivos[0].exists())
            self.assertFalse(arquivos[0].with_suffix(arquivos[0].suffix + ".json").exists())
            self.assertTrue(arquivos[1].exists())
            self.assertTrue(arquivos[2].exists())


if __name__ == "__main__":
    unittest.main()
