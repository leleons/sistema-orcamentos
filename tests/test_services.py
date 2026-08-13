import unittest
from decimal import Decimal

from dsystem_erp.services.faturamento import decimal_brl, itens_faturamento_lista, resumo_itens_faturamento, total_itens_faturamento
from dsystem_erp.services.whatsapp import criar_url_whatsapp, normalizar_telefone_whatsapp
from dsystem_erp.utils.datas import data_para_banco_br, data_para_br, data_para_iso, parse_data_flex
from dsystem_erp.utils.formatadores import formatar_moeda_br, somente_digitos, tamanho_arquivo_legivel


class ServiceTests(unittest.TestCase):
    def test_whatsapp_normaliza_numero_brasil(self):
        self.assertEqual(normalizar_telefone_whatsapp("(31) 93502-3241"), "5531935023241")

    def test_whatsapp_url_codifica_mensagem(self):
        url = criar_url_whatsapp("31935023241", "Olá cliente")
        self.assertIn("5531935023241", url)
        self.assertIn("Ol%C3%A1%20cliente", url)

    def test_decimal_brl(self):
        self.assertEqual(decimal_brl("R$ 1.234,56"), Decimal("1234.56"))
        self.assertEqual(decimal_brl("12,30"), Decimal("12.30"))
        self.assertEqual(decimal_brl(12.3), Decimal("12.3"))

    def test_total_itens_faturamento(self):
        itens = [
            {"quantidade": 2, "valor_unitario": "10,50"},
            {"qtd": 1, "unitario": "R$ 5,00"},
        ]
        self.assertEqual(total_itens_faturamento(itens), Decimal("26.00"))

    def test_itens_faturamento_lista_normaliza_json(self):
        itens = itens_faturamento_lista('[{"descricao":"Servico A","quantidade":2,"valor_unitario":10,"tipo":"Outro"}]')
        self.assertEqual(itens[0]["desc"], "Servico A")
        self.assertEqual(itens[0]["qtd"], 2)
        self.assertEqual(itens[0]["vtotal"], 20.0)
        self.assertEqual(itens[0]["tipo_item"], "Serviço")

    def test_resumo_itens_faturamento(self):
        resumo = resumo_itens_faturamento([{"desc": "Item A", "qtd": 3, "vtotal": 10}])
        self.assertEqual(resumo, "3x Item A")

    def test_item_sem_nota_preserva_vinculo_com_estoque(self):
        itens = itens_faturamento_lista([{
            "desc": "Peça", "qtd": 1, "vunit": 50, "tipo_item": "Serviço",
            "estoque_id": 9, "origem_item": "Produto do estoque", "situacao_nota": "Comprado sem nota",
        }])
        self.assertEqual(itens[0]["tipo_item"], "Serviço")
        self.assertEqual(itens[0]["estoque_id"], 9)
        self.assertEqual(itens[0]["situacao_nota"], "Comprado sem nota")

    def test_somente_digitos(self):
        self.assertEqual(somente_digitos("23.524.449/0001-54"), "23524449000154")

    def test_datas_flexiveis(self):
        self.assertEqual(data_para_br("2026-07-14"), "14/07/2026")
        self.assertEqual(data_para_iso("14/07/2026"), "2026-07-14")
        self.assertEqual(data_para_banco_br("2026/07/14"), "14/07/2026")
        self.assertIsNone(parse_data_flex(""))

    def test_formatadores_arquivo_moeda(self):
        self.assertEqual(tamanho_arquivo_legivel(1024), "1.0 KB")
        self.assertEqual(formatar_moeda_br(1234.5), "R$ 1.234,50")


if __name__ == "__main__":
    unittest.main()
