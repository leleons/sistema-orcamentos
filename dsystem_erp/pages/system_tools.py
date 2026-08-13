from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Callable

import streamlit as st

from dsystem_erp.services.health import HealthCheck, health_to_row, resumo_checks, status_path


def renderizar_backups_sistema(
    eh_admin_master: Callable[[], bool],
    registrar_log_tecnico: Callable[..., None],
    tamanho_arquivo_legivel: Callable[[int], str],
    db_name: str,
) -> None:
    if not eh_admin_master():
        st.error("Acesso restrito ao Administrador Master.")
        return

    st.title("Backups do Sistema")
    st.caption("Gere e baixe backups do MySQL antes de atualizações ou quando precisar.")
    try:
        from scripts.backup_mysql import BACKUP_DIR, encontrar_mysqldump, run_backup
    except Exception as ex:
        st.error(f"Não foi possível carregar o script de backup: {ex}")
        return

    b1, b2, b3, b4 = st.columns(4)
    caminho_mysqldump = encontrar_mysqldump()
    if caminho_mysqldump:
        st.caption(f"mysqldump detectado: {caminho_mysqldump}")
    else:
        st.warning(
            "mysqldump não foi encontrado. No Windows, configure MYSQLDUMP_PATH no .env "
            "ou instale o client do MySQL/MariaDB."
        )

    if b1.button("Gerar backup pré-deploy", type="primary", width="stretch"):
        try:
            run_backup("pre-deploy")
            st.success("Backup pré-deploy gerado.")
            st.rerun()
        except Exception as ex:
            registrar_log_tecnico("ERROR", "backup_ui", "Falha ao gerar backup", {"erro": str(ex)})
            st.error(f"Erro ao gerar backup: {ex}")
    if b2.button("Gerar backup completo", width="stretch"):
        try:
            run_backup("full")
            st.success("Backup completo gerado.")
            st.rerun()
        except Exception as ex:
            st.error(f"Erro ao gerar backup: {ex}")
    if b3.button("Gerar incremental", width="stretch"):
        try:
            run_backup("incremental")
            st.success("Backup incremental gerado.")
            st.rerun()
        except Exception as ex:
            st.error(f"Erro ao gerar backup: {ex}")
    if b4.button("Atualizar lista", width="stretch"):
        st.rerun()

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backups = sorted(BACKUP_DIR.glob("*.sql.gz"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not backups:
        st.info("Nenhum backup encontrado.")
        return

    def ler_meta_backup(caminho_backup: Path) -> dict:
        meta_path = caminho_backup.with_suffix(caminho_backup.suffix + ".json")
        if not meta_path.exists():
            return {}
        try:
            return json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    total_bytes = sum(b.stat().st_size for b in backups)
    ultimo_backup = backups[0]
    m1, m2, m3 = st.columns(3)
    m1.metric("Backups salvos", len(backups))
    m2.metric("Espaço usado", tamanho_arquivo_legivel(total_bytes))
    m3.metric("Último backup", datetime.fromtimestamp(ultimo_backup.stat().st_mtime).strftime("%d/%m/%Y %H:%M"))

    linhas = []
    for caminho in backups:
        meta = ler_meta_backup(caminho)
        linhas.append(
            {
                "Arquivo": caminho.name,
                "Tipo": meta.get("tipo") or "-",
                "Banco": meta.get("database") or db_name,
                "Tamanho": tamanho_arquivo_legivel(caminho.stat().st_size),
                "Criado em": datetime.fromtimestamp(caminho.stat().st_mtime).strftime("%d/%m/%Y %H:%M"),
                "Retenção": f"{meta.get('retencao_dias')} dias" if meta.get("retencao_dias") else "-",
                "Caminho": str(caminho),
            }
        )
    st.dataframe(linhas, width="stretch", hide_index=True)
    escolhido = st.selectbox("Backup para baixar/ver detalhes:", [b.name for b in backups])
    caminho_sel = next((b for b in backups if b.name == escolhido), None)
    if caminho_sel:
        meta_sel = ler_meta_backup(caminho_sel)
        d1, d2 = st.columns([1, 2])
        with d1:
            st.download_button(
                "Baixar backup selecionado",
                data=caminho_sel.read_bytes(),
                file_name=caminho_sel.name,
                mime="application/gzip",
                width="stretch",
            )
        with d2:
            st.caption(
                "Comando de restauração manual no servidor. Use somente depois de gerar outro "
                "backup e confirmar que escolheu o arquivo certo."
            )
            comando_restore = (
                f"gunzip -c {str(caminho_sel)} | "
                f"mysql -h {meta_sel.get('host') or '127.0.0.1'} "
                f"-P {meta_sel.get('port') or '3306'} "
                f"-u $MYSQL_USER -p {meta_sel.get('database') or db_name}"
            )
            st.code(comando_restore, language="bash")
        with st.expander("Detalhes técnicos do backup", expanded=False):
            st.json(
                {
                    "arquivo": caminho_sel.name,
                    "caminho": str(caminho_sel),
                    "tamanho": tamanho_arquivo_legivel(caminho_sel.stat().st_size),
                    "metadata": meta_sel,
                }
            )


def renderizar_diagnostico_sistema(
    *,
    eh_admin_master: Callable[[], bool],
    conectar_banco: Callable[[], object],
    db_name: str,
    dsystem_static_dir: Path,
    whatsapp_oficial: str,
    smtp_host: str,
    smtp_from: str,
    gerar_excel_tabela: Callable[..., bytes],
    tamanho_arquivo_legivel: Callable[[int], str],
    app_dir: Path,
) -> None:
    if not eh_admin_master():
        st.error("Acesso restrito ao Administrador Master.")
        return

    st.title("Diagnóstico do Sistema")
    st.caption(
        "Checklist rápido para conferir banco, migrations, backups, integrações e armazenamento "
        "antes de atualizações."
    )

    checks = []
    try:
        conn = conectar_banco()
        c = conn.cursor()
        c.execute("SELECT 1 AS ok")
        c.fetchone()
        checks.append(HealthCheck("Banco de dados", "OK", "Conexão MySQL ativa", db_name))
        try:
            c.execute("SELECT nome, aplicado_em FROM schema_migrations ORDER BY aplicado_em DESC, id DESC LIMIT 1")
            ultima = c.fetchone()
            if ultima:
                ultima_nome = ultima.get("nome") if hasattr(ultima, "get") else ultima[0]
                checks.append(HealthCheck("Migrations", "OK", "Tabela de migrations encontrada", f"Última: {ultima_nome}"))
            else:
                checks.append(HealthCheck("Migrations", "AVISO", "Tabela existe, mas sem registros aplicados"))
        except Exception as ex:
            checks.append(HealthCheck("Migrations", "AVISO", "Tabela schema_migrations ainda não disponível", str(ex)))
        conn.close()
    except Exception as ex:
        checks.append(HealthCheck("Banco de dados", "ERRO", "Falha ao conectar no MySQL", str(ex)))

    try:
        from scripts.backup_mysql import BACKUP_DIR, encontrar_mysqldump

        mysqldump_path = encontrar_mysqldump()
        checks.append(
            HealthCheck(
                "mysqldump",
                "OK" if mysqldump_path else "ERRO",
                "mysqldump detectado" if mysqldump_path else "mysqldump não encontrado",
                mysqldump_path or "Configure MYSQLDUMP_PATH",
            )
        )
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        backups = list(BACKUP_DIR.glob("*.sql.gz"))
        checks.append(HealthCheck("Backups", "OK" if backups else "AVISO", f"{len(backups)} backup(s) encontrado(s)", str(BACKUP_DIR)))
    except Exception as ex:
        checks.append(HealthCheck("Backups", "ERRO", "Falha ao verificar backups", str(ex)))

    checks.append(status_path(dsystem_static_dir, "Pasta Dsystem", "Pasta de arquivos existe", "Pasta de arquivos não encontrada"))
    checks.append(
        HealthCheck(
            "WhatsApp",
            "OK" if whatsapp_oficial else "AVISO",
            "Número oficial configurado" if whatsapp_oficial else "Número oficial não configurado",
            whatsapp_oficial,
        )
    )
    smtp_ok = bool(smtp_host and smtp_from)
    checks.append(
        HealthCheck(
            "E-mail SMTP",
            "OK" if smtp_ok else "AVISO",
            "SMTP básico configurado" if smtp_ok else "SMTP incompleto",
            f"{smtp_host} / {smtp_from}",
        )
    )

    try:
        uso = shutil.disk_usage(app_dir)
        livre_pct = (uso.free / uso.total) * 100 if uso.total else 0
        status_disco = "OK" if livre_pct >= 15 else ("AVISO" if livre_pct >= 8 else "ERRO")
        checks.append(
            HealthCheck(
                "Disco",
                status_disco,
                f"{livre_pct:.1f}% livre",
                f"Livre: {tamanho_arquivo_legivel(uso.free)} / Total: {tamanho_arquivo_legivel(uso.total)}",
            )
        )
    except Exception as ex:
        checks.append(HealthCheck("Disco", "AVISO", "Não foi possível medir o disco", str(ex)))

    resumo = resumo_checks(checks)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Checks", resumo["total"])
    m2.metric("OK", resumo["ok"])
    m3.metric("Avisos", resumo["avisos"])
    m4.metric("Erros", resumo["erros"])

    linhas = [health_to_row(check) for check in checks]
    st.dataframe(linhas, width="stretch", hide_index=True)
    st.download_button(
        "Exportar diagnóstico",
        data=gerar_excel_tabela(linhas, "Diagnóstico do Sistema"),
        file_name="diagnostico_sistema.xls",
        mime="application/vnd.ms-excel",
        width="stretch",
    )
