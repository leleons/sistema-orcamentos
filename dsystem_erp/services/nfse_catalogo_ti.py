"""Catálogo de referência, não enquadramento fiscal automático da empresa.

Fonte consultada em 11/09/2026:
https://www.gov.br/nfse/pt-br/mei-e-demais-empresas/codigos-de-tributacao-nacional-nbs
Peças/partes não integram o catálogo de NFS-e (ver subitem 14.01).
"""

import re

FONTE_CATALOGO_TI = "https://www.gov.br/nfse/pt-br/mei-e-demais-empresas/codigos-de-tributacao-nacional-nbs"

# Descrições curtas próprias para o cadastro; código oficial de seis dígitos.
SERVICOS_TI_ADICIONAIS = (
    ("Processamento de dados", "01.03.01", "01.03"),
    ("Armazenamento e hospedagem de dados", "01.03.02", "01.03"),
    ("Elaboracao de programas de computador", "01.04.01", "01.04"),
    ("Licenciamento ou cessao de uso de software", "01.05.01", "01.05"),
    ("Assistencia tecnica", "14.02.01", "14.02"),
    ("Montagem de equipamentos com material do cliente", "14.06.01", "14.06"),
    ("Manutencao de notebooks e computadores", "14.01.01", "14.01"),
    ("Manutencao de impressoras e perifericos", "14.01.01", "14.01"),
)

def codigo_nacional_salvo(servico):
    """Não inventa desdobro '01' a partir de um item LC 116 de quatro dígitos."""
    codigo = re.sub(r"\D", "", str((servico or {}).get("codigo_servico") or ""))
    return codigo if len(codigo) == 6 else ""


def desdobramento_suporte_bh(servico, municipio, codigo_nacional, ambiente):
    """Referência confirmada na API municipal de homologação em 11/09/2026.

    Não extrapola para outras atividades, municípios ou para produção.
    GET /parametrizacao/3106200/01.07.01.001/2026-09-11/aliquota
    """
    if (str(municipio) == "3106200" and codigo_nacional == "010701"
            and ambiente == "homologacao"
            and (servico or {}).get("nome") == "Suporte tecnico em informatica"):
        return "001"
    return ""


def cadastrar_catalogo_ti(cursor, padroes_anteriores):
    """Corrige apenas sementes intactas; não modifica cadastros personalizados/notas.

    A transação e seu commit pertencem ao chamador. Reexecução não duplica registros.
    Não define alíquotas, regime tributário ou desdobramento municipal.
    """
    correcoes = {"01.01.02": "01.01.01", "01.07.02": "01.07.01", "01.07.03": "01.07.01"}
    padroes = []
    for anterior in padroes_anteriores:
        nome, codigo, item, aliquota, ativo, obs = anterior
        corrigido = correcoes.get(codigo, codigo)
        if corrigido != codigo:
            cursor.execute(
                "UPDATE nfse_bh_servicos SET codigo_servico=? "
                "WHERE nome=? AND codigo_servico=? AND item_lista_servico=? "
                "AND aliquota_iss=? AND ativo=? AND observacoes=?",
                (corrigido, nome, codigo, item, aliquota, ativo, obs),
            )
        padroes.append((nome, corrigido, item, aliquota, ativo, obs))
    padroes.extend(
        (nome, codigo, item, 0, "Sim",
         "Referencia nacional de TI. Conferir atividade, aliquota e desdobramento municipal antes de emitir. "
         "Pecas vendidas separadamente como produto. Fonte: " + FONTE_CATALOGO_TI)
        for nome, codigo, item in SERVICOS_TI_ADICIONAIS
    )
    for servico in padroes:
        cursor.execute("SELECT COUNT(*) AS total FROM nfse_bh_servicos WHERE codigo_servico=? AND nome=?", (servico[1], servico[0]))
        total = cursor.fetchone()
        if not (total.get("total") if isinstance(total, dict) else total[0]):
            cursor.execute(
                "INSERT INTO nfse_bh_servicos (nome, codigo_servico, item_lista_servico, aliquota_iss, ativo, observacoes) "
                "VALUES (?,?,?,?,?,?)", servico,
            )
