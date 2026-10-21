import unittest
from dsystem_erp.services.estoque_qr import conteudo_qr_produto, gerar_qr_produto


class ProdutoQrTests(unittest.TestCase):
    def test_descricao_e_local_sem_dados_financeiros(self):
        produto = dict(id=11, codigo_entrada='02.01.6', nome_generico='Fonte para notebook',
                       modelo='65W', categoria='Informática', codigo='02 Usado', caixa='14',
                       tem_fonte='Sim', valor_custo=987.65, observacoes='privado', quantidade=9)
        texto = conteudo_qr_produto(produto)
        for valor in ['11', '02.01.6', 'Fonte para notebook', '65W', 'Informática', '14', 'Sim']:
            self.assertIn(valor, texto)
        for valor in ['987.65', 'privado', 'Quantidade']:
            self.assertNotIn(valor, texto)
        self.assertTrue(gerar_qr_produto(produto).startswith(b'\x89PNG'))

    def test_campos_ausentes_e_texto_longo(self):
        self.assertNotIn('None', conteudo_qr_produto({'id': 1}))
        produto = {'id': 1, 'nome_generico': 'á' * 10000}
        self.assertLess(len(conteudo_qr_produto(produto)), 250)
        self.assertTrue(gerar_qr_produto(produto))
