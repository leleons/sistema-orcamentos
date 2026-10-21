"""Seleção dos cadastros ativos, preservando valores históricos."""
from dsystem_erp.services.permissions import usuario_eh_gerencial

CAMPOS = {"categoria": "Categoria / natureza financeira", "centro": "Centro de custo",
          "plano_contas": "Plano de contas", "conta_bancaria": "Conta financeira"}
CONTAS = {"Conta bancária", "Caixa físico", "Boleto", "Cartão de crédito", "Conta financeira"}


def carregar_opcoes(conectar):
    conn = conectar()
    try:
        c = conn.cursor()
        c.execute("SELECT * FROM financeiro_cadastros_aux WHERE ativo='Sim' ORDER BY tipo, nome")
        opcoes = {campo: [] for campo in CAMPOS}
        for row in c.fetchall():
            row = dict(row)
            if row.get('tipo_conta') == 'SINTETICA' or row.get('aceita_lancamento') == 'Não':
                continue
            for campo, tipo in CAMPOS.items():
                corresponde = (row['tipo'] == tipo or
                    (campo == 'categoria' and row['tipo'] in ('Categoria financeira', 'Natureza financeira')) or
                    (campo == 'conta_bancaria' and row['tipo'] in CONTAS))
                if corresponde:
                    valor = str(row['nome'] or '').strip()
                    if valor and row.get('importacao_origem') and row.get('codigo'):
                        valor = f"{row['codigo']} — {valor}"
                    if campo == 'conta_bancaria' and valor:
                        valor = f"{row['tipo']} — {valor}"
                    if valor and valor not in opcoes[campo]:
                        opcoes[campo].append(valor)
        return opcoes
    finally:
        conn.close()


def selecionar(coluna, campo, opcoes, chave, atual='', disabled=False):
    valores = [''] + list(opcoes.get(campo, []))
    atual = atual or ''
    if atual not in valores:
        valores.append(atual)
    return coluna.selectbox(CAMPOS[campo] + ':', valores, index=valores.index(atual),
                            format_func=lambda v: v or 'Selecione um cadastro',
                            key=chave, disabled=disabled)


def renderizar(st, conectar, prefixo, atual=None, disabled=False):
    atual = atual or {}
    opcoes = carregar_opcoes(conectar)
    valores = {}
    for coluna, campo in zip(st.columns(4), CAMPOS):
        if campo == 'conta_bancaria' and not usuario_eh_gerencial(st.session_state):
            coluna.caption('Conta da empresa: acesso restrito ao gerencial.')
            valores[campo] = atual.get(campo) or ''
        else:
            valores[campo] = selecionar(coluna, campo, opcoes, f'{prefixo}_{campo}', atual.get(campo), disabled)
    return valores


def salvar_faturamento(cursor, fat_id, valores):
    cursor.execute('UPDATE faturamento SET categoria=?, centro=?, plano_contas=?, conta_bancaria=? WHERE id=?',
                   tuple(valores.get(campo) or '' for campo in CAMPOS) + (fat_id,))
