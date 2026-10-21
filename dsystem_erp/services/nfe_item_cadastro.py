"""Reaproveita classificação vinculada ao produto, nunca impostos da compra."""
import re
import unicodedata


def nome_normalizado(value):
    value = unicodedata.normalize('NFKD', str(value or '').casefold())
    return ' '.join(''.join(c for c in value if not unicodedata.combining(c)).split())


def _ncm_valido(valor):
    codigo = str(valor or '').strip().replace('.', '')
    return codigo if len(codigo) == 8 and codigo.isdigit() else ''


def buscar_ncm_item(conectar, item, catalogo=None):
    if item.get('ncm'):
        codigo = _ncm_valido(item['ncm'])
        return {'ncm': codigo, 'mensagem': 'NCM informado no próprio item.' if codigo else 'O NCM informado no item é inválido; corrija o cadastro.'}
    conn = conectar()
    try:
        c = conn.cursor(dictionary=True)
        produto_id = item.get('estoque_id')
        if produto_id:
            c.execute('SELECT id FROM estoque WHERE id=%s', (produto_id,))
            produtos = c.fetchall()
        else:
            nome = nome_normalizado(item.get('desc'))
            if not nome:
                return {'ncm': '', 'mensagem': 'Informe a descrição ou vincule o produto do estoque.'}
            c.execute('SELECT id, produto, nome_generico, modelo FROM estoque')
            produtos = [p for p in c.fetchall() if any(
                nome_normalizado(p.get(campo)) == nome
                for campo in ('produto', 'nome_generico', 'modelo') if p.get(campo))]
        if len(produtos) > 1 or (produto_id and not produtos):
            return {'ncm': '', 'mensagem': 'Produto não identificado de forma única no estoque. Vincule o item ou confirme o NCM.'}
        if produtos:
            c.execute('SELECT ncm FROM estoque_nota_entrada_itens WHERE produto_id=%s', (produtos[0]['id'],))
            ncms = {_ncm_valido(r.get('ncm')) for r in c.fetchall() if str(r.get('ncm') or '').strip()}
            if len(ncms) == 1 and '' not in ncms:
                return {'ncm': next(iter(ncms)), 'mensagem': 'NCM preenchido a partir das entradas do produto vinculado. Confira a classificação.'}
            if ncms:
                return {'ncm': '', 'mensagem': 'Há NCMs divergentes ou inválidos nas entradas deste produto. Confirme a classificação.'}
        if catalogo is None:
            c.execute("SELECT nome,ncm FROM codigos_fiscais_produtos WHERE ativo='Sim'")
            catalogo = c.fetchall()
        nome = nome_normalizado(item.get('desc'))
        correspondentes = [r for r in catalogo if nome and nome_normalizado(r.get('nome')) == nome
                           and r.get('ativo', 'Sim') == 'Sim']
        if len(correspondentes) == 1 and _ncm_valido(correspondentes[0].get('ncm')):
            return {'ncm': _ncm_valido(correspondentes[0]['ncm']), 'mensagem': 'NCM preenchido automaticamente pelo nome exato no cadastro fiscal de produtos.'}
        return {'ncm': '', 'mensagem': 'Não há NCM único e válido para este nome. Cadastre/confirme o código uma vez para reutilizá-lo.'}
    finally:
        conn.close()


def sugestoes_por_nome(item, catalogo):
    palavras = set(re.findall(r'[a-z0-9]+', nome_normalizado(item.get('desc')))) - {'de', 'para', 'com', 'do', 'da', 'e'}
    if not palavras:
        return []
    return [r for r in catalogo if palavras.intersection(
        set(re.findall(r'[a-z0-9]+', nome_normalizado(r.get('nome')))))]
