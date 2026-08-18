import unittest

from dsystem_erp.services.estoque_fiscal import (
    COMPRADO_COM_NOTA,
    COMPRADO_SEM_NOTA,
    aplicar_regra_fiscal_item,
    normalizar_situacao_compra,
    tipo_fiscal_produto_estoque,
)
from dsystem_erp.services.faturamento import itens_faturamento_lista
from dsystem_erp.services.orcamento_pdf import itens_orcamento_normalizados


class EstoqueFiscalTests(unittest.TestCase):
    def test_produto_com_nota_sai_como_produto(self):
        produto = {"id": 1, "situacao_nota": COMPRADO_COM_NOTA}
        self.assertEqual(tipo_fiscal_produto_estoque(produto), "Produto")

    def test_produto_sem_nota_sai_como_servico(self):
        produto = {"id": 2, "situacao_nota": COMPRADO_SEM_NOTA}
        self.assertEqual(tipo_fiscal_produto_estoque(produto), "Serviço")

    def test_normaliza_valores_antigos_de_sem_nota(self):
        self.assertEqual(normalizar_situacao_compra("sem nota"), COMPRADO_SEM_NOTA)
        self.assertEqual(normalizar_situacao_compra(""), COMPRADO_COM_NOTA)

    def test_regra_preserva_vinculo_para_baixa_do_estoque(self):
        item = aplicar_regra_fiscal_item(
            {
                "estoque_id": 15,
                "situacao_nota": COMPRADO_SEM_NOTA,
                "tipo_item": "Produto",
            }
        )
        self.assertEqual(item["tipo_item"], "Serviço")
        self.assertEqual(item["estoque_id"], 15)

    def test_faturamento_corrige_item_antigo_inconsistente(self):
        item = itens_faturamento_lista(
            [{
                "desc": "Peça sem documento",
                "qtd": 1,
                "vunit": 80,
                "estoque_id": 7,
                "situacao_nota": COMPRADO_SEM_NOTA,
                "tipo_item": "Produto",
            }]
        )[0]
        self.assertEqual(item["tipo_item"], "Serviço")
        self.assertEqual(item["estoque_id"], 7)

    def test_orcamento_corrige_item_antigo_inconsistente(self):
        item = itens_orcamento_normalizados(
            [{
                "d": "Peça sem documento",
                "q": 1,
                "v": 80,
                "estoque_id": 7,
                "situacao_nota": COMPRADO_SEM_NOTA,
                "tipo_item": "Produto",
            }]
        )[0]
        self.assertEqual(item["tipo_item"], "Serviço")
        self.assertEqual(item["estoque_id"], 7)


if __name__ == "__main__":
    unittest.main()
