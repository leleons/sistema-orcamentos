"""Regras de conciliação e bloqueio permanente dos títulos financeiros."""


def esta_baixado(registro):
    return (registro.get("status") in {"Pago", "Recebido"}
            and bool(str(registro.get("data_baixa") or "").strip()))


def _erro_sem_privilegio_trigger(ex):
    errno = getattr(ex, "errno", None)
    if errno in (1419, 1227, 1370, 1044, 1142):
        return True
    texto = str(ex).lower()
    return "super privilege" in texto or "log_bin_trust_function_creators" in texto


def instalar_protecao_conciliacao(cursor):
    """Triggers protegem rotas de escrita; se o MySQL recusar, o app segue com o bloqueio em Python."""
    try:
        cursor.execute("SET SESSION log_bin_trust_function_creators = 1")
    except Exception:
        pass
    for tabela in ("contas_pagar", "contas_receber"):
        pago = "Pago" if tabela == "contas_pagar" else "Recebido"
        bloqueado = "LOWER(TRIM(COALESCE(OLD.conciliado, ''))) IN ('sim','1','true','yes')"
        marcado = "LOWER(TRIM(COALESCE(NEW.conciliado, ''))) IN ('sim','1','true','yes')"
        regras = {
            "update": f"""
                IF {bloqueado} THEN
                    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Lançamento conciliado: alteração bloqueada.';
                END IF;
                IF {marcado} AND (COALESCE(OLD.status,'') <> '{pago}'
                    OR TRIM(COALESCE(OLD.data_baixa,''))=''
                    OR COALESCE(NEW.status,'') <> '{pago}'
                    OR TRIM(COALESCE(NEW.data_baixa,''))=''
                    OR TRIM(COALESCE(NEW.data_conciliacao,''))='') THEN
                    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Conciliação exige baixa integral anterior e data da conciliação.';
                END IF;
            """,
            "delete": f"""IF {bloqueado} THEN
                SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Lançamento conciliado: exclusão bloqueada.';
                END IF;""",
            "insert": f"""IF {marcado} THEN
                SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Cadastre e baixe o lançamento antes de conciliar.';
                END IF;""",
        }
        for evento, regra in regras.items():
            nome = f"trg_{tabela}_conciliacao_{evento}_v1"
            cursor.execute("SELECT TRIGGER_NAME FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA=DATABASE() AND TRIGGER_NAME=?", (nome,))
            if cursor.fetchone():
                continue
            try:
                cursor.execute(
                    f"CREATE TRIGGER `{nome}` BEFORE {evento.upper()} ON `{tabela}` FOR EACH ROW BEGIN {regra} END"
                )
            except Exception as ex:
                if _erro_sem_privilegio_trigger(ex):
                    return
                raise
