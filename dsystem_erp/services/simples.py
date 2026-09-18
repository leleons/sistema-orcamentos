"""Situação cadastral do Simples, sem presumir regime a partir de dados ausentes."""

OPCOES_SIMPLES = {
    "": "Selecione a situação",
    "1": "Não optante pelo Simples Nacional",
    "2": "Optante — MEI",
    "3": "Optante — ME/EPP",
    "NA": "Não se aplica — pessoa física",
}


def situacao_da_consulta(dados):
    simples, mei = dados.get("opcao_pelo_simples"), dados.get("opcao_pelo_mei")
    if mei is True and simples is not False:
        return "2"
    if simples is True and mei is False:
        return "3"
    if simples is False and mei is not True:
        return "1"
    return ""


def validar_situacao(documento, emite, situacao):
    digitos = "".join(c for c in str(documento or "") if c.isdigit())
    if len(digitos) == 14 and emite == "Sim" and situacao not in {"1", "2", "3"}:
        raise ValueError("Informe a situação no Simples Nacional da empresa que emite nota fiscal.")


def optante_legado(situacao):
    return {"1": "NÃO", "2": "SIM", "3": "SIM"}.get(situacao, "")


def buscar_situacao_salva(conectar_banco, documento):
    """Obtém somente o regime pelo documento exato, inclusive com pontuação."""
    documento = "".join(c for c in str(documento or "") if c.isdigit())
    if len(documento) == 11:
        return "NA"
    if len(documento) != 14:
        return ""
    conn = conectar_banco()
    try:
        cursor = conn.cursor()
        cursor.execute("""SELECT situacao_simples_nacional FROM clientes
            WHERE REPLACE(REPLACE(REPLACE(REPLACE(cnpj, '.', ''), '/', ''), '-', ''), ' ', '')=?""", (documento,))
        valores = {str(row.get("situacao_simples_nacional") or "") for row in cursor.fetchall()}
        valores.discard("")
        if len(valores) == 1:
            valor = valores.pop()
            return valor if valor in {"1", "2", "3"} else ""
        return ""
    finally:
        conn.close()
