import unittest
from datetime import date

from dsystem_erp.services.audit import (
    cliente_do_log,
    extrair_colunas_insert,
    extrair_colunas_update,
    extrair_tabela_sql,
    extrair_where_id,
    limpar_registro_log,
    montar_registro_params,
)


class AuditTests(unittest.TestCase):
    def test_extrai_tabela_por_tipo_sql(self):
        self.assertEqual(extrair_tabela_sql("INSERT INTO clientes (nome) VALUES (%s)", "insert"), "clientes")
        self.assertEqual(extrair_tabela_sql("UPDATE `orcamentos` SET cliente=%s WHERE orc_id=%s", "update"), "orcamentos")
        self.assertEqual(extrair_tabela_sql("DELETE FROM ordens_servico WHERE os_id=%s", "delete"), "ordens_servico")

    def test_extrai_colunas_insert_update(self):
        self.assertEqual(extrair_colunas_insert("INSERT INTO clientes (`nome`, cpf_cnpj) VALUES (%s,%s)"), ["nome", "cpf_cnpj"])
        self.assertEqual(extrair_colunas_update("UPDATE clientes SET nome=%s, telefone=%s WHERE id=%s"), ["nome", "telefone"])

    def test_where_id_usa_ultimo_parametro(self):
        self.assertEqual(extrair_where_id("UPDATE clientes SET nome=%s WHERE id=%s", ["Novo", 12]), ("id", 12))

    def test_monta_registro_e_mascara_campos_sensiveis(self):
        registro = montar_registro_params(["nome", "senha", "arquivo"], ["Cliente", "123", b"abc"])
        limpo = limpar_registro_log(registro)
        self.assertEqual(limpo["nome"], "Cliente")
        self.assertEqual(limpo["senha"], "***")
        self.assertEqual(limpo["arquivo"], "***")

    def test_limpa_data_para_iso(self):
        limpo = limpar_registro_log({"data": date(2026, 7, 14)})
        self.assertEqual(limpo["data"], "2026-07-14")

    def test_cliente_do_log(self):
        self.assertEqual(cliente_do_log("faturamento", {"cliente": "Empresa A"}), "Empresa A")
        self.assertEqual(cliente_do_log("clientes", {"nome": "Cliente B"}), "Cliente B")
        self.assertEqual(cliente_do_log("faturamento", {"nome": "Nao usar"}), "")


if __name__ == "__main__":
    unittest.main()
