import os
import gzip
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKUP_DIR = ROOT / "backups" / "mysql"
MAX_BACKUPS = 2
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dsystem_erp.config import load_environment

    load_environment()
except Exception:
    pass


def env(name, default=""):
    return os.environ.get(name, default)


def retention_days(kind):
    return {
        "full": 60,
        "pre-deploy": 30,
        "incremental": 14,
    }.get(kind, 14)


def cleanup_old_backups(db, kind=None):
    """Mantém somente os backups mais recentes do banco, com seus metadados."""
    backups = sorted(
        BACKUP_DIR.glob(f"{db}_*.sql.gz"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for old in backups[MAX_BACKUPS:]:
        old.unlink(missing_ok=True)
        old.with_suffix(old.suffix + ".json").unlink(missing_ok=True)


def encontrar_mysqldump():
    configurado = env("MYSQLDUMP_PATH", "").strip()
    candidatos = [
        configurado,
        shutil.which("mysqldump") or "",
        r"C:\xampp\mysql\bin\mysqldump.exe",
        r"C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqldump.exe",
        r"C:\Program Files\MySQL\MySQL Server 5.7\bin\mysqldump.exe",
        r"C:\Program Files\MariaDB 11.4\bin\mysqldump.exe",
        r"C:\Program Files\MariaDB 10.11\bin\mysqldump.exe",
    ]
    for candidato in candidatos:
        if candidato and Path(candidato).exists():
            return str(Path(candidato))
    return ""


def listar_backups():
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    arquivos = sorted(BACKUP_DIR.glob("*.sql.gz"), key=lambda p: p.stat().st_mtime, reverse=True)
    for arquivo in arquivos:
        meta_path = arquivo.with_suffix(arquivo.suffix + ".json")
        meta = {}
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except Exception:
                meta = {}
        tamanho_mb = arquivo.stat().st_size / (1024 * 1024)
        criado = datetime.fromtimestamp(arquivo.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        print(f"{criado} | {meta.get('tipo', '-'):10} | {tamanho_mb:8.2f} MB | {arquivo}")


def run_backup(kind):
    kind = (kind or "incremental").strip().lower()
    if kind not in {"incremental", "full", "pre-deploy"}:
        raise SystemExit("Use: incremental, full ou pre-deploy")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    db = env("MYSQL_DATABASE", "banco_dsystem")
    user = env("MYSQL_USER", "root")
    password = env("MYSQL_PASSWORD", "")
    host = env("MYSQL_HOST", "127.0.0.1")
    port = env("MYSQL_PORT", "3306")
    out_file = BACKUP_DIR / f"{db}_{kind}_{stamp}.sql.gz"
    mysqldump = encontrar_mysqldump()
    if not mysqldump:
        raise FileNotFoundError(
            "mysqldump não encontrado. Instale o MySQL/MariaDB client ou configure "
            "MYSQLDUMP_PATH no .env, por exemplo: MYSQLDUMP_PATH=C:\\xampp\\mysql\\bin\\mysqldump.exe"
        )

    cmd = [
        mysqldump,
        f"--host={host}",
        f"--port={port}",
        f"--user={user}",
        "--single-transaction",
        "--routines",
        "--triggers",
        db,
    ]
    env_vars = os.environ.copy()
    if password:
        env_vars["MYSQL_PWD"] = password

    with gzip.open(out_file, "wb") as fh:
        subprocess.run(cmd, check=True, stdout=fh, env=env_vars)

    metadata = {
        "arquivo": out_file.name,
        "tipo": kind,
        "database": db,
        "host": host,
        "port": port,
        "criado_em": datetime.now().isoformat(timespec="seconds"),
        "tamanho_bytes": out_file.stat().st_size,
        "retencao_dias": retention_days(kind),
        "maximo_backups": MAX_BACKUPS,
    }
    out_file.with_suffix(out_file.suffix + ".json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    cleanup_old_backups(db, kind)
    print(out_file)


if __name__ == "__main__":
    modo = sys.argv[1] if len(sys.argv) > 1 else "incremental"
    if modo == "list":
        listar_backups()
    else:
        run_backup(modo)
