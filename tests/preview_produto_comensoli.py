"""Prévia local, sem transmissão, numeração fiscal ou movimentação de estoque."""
from pathlib import Path
from datetime import date
from dsystem_erp.services.nfe_produto import gerar_xml_nfe_produto_rascunho


if __name__ == '__main__':
    faturamento = {'cliente': 'Organização Educacional João XXIII (O. E Catarina Comensoli)',
                   'cnpj': '16.518.821/0002-35'}
    itens = [{'desc': 'Mouse USB — PRODUTO DE TESTE', 'tipo_item': 'Produto',
              'qtd': 1, 'vunit': 10, 'vtotal': 10}]
    dados = {'competencia': date(2026, 9, 23), 'ambiente': 'homologacao', 'unidade': 'UN'}
    destino = Path('output/testes')
    destino.mkdir(parents=True, exist_ok=True)
    (destino / 'produto_comensoli_rascunho.xml').write_bytes(
        gerar_xml_nfe_produto_rascunho(faturamento, itens, dados))
