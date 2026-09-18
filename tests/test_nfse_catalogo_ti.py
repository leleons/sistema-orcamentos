import unittest
from unittest.mock import Mock

from dsystem_erp.services.nfse_catalogo_ti import (
    cadastrar_catalogo_ti, codigo_nacional_salvo, desdobramento_suporte_bh, SERVICOS_TI_ADICIONAIS,
)


class CatalogoTiTest(unittest.TestCase):
    def test_desdobramento_limitado_ao_caso_confirmado(self):
        servico = {"nome": "Suporte tecnico em informatica"}
        self.assertEqual(desdobramento_suporte_bh(servico, "3106200", "010701", "homologacao"), "001")
        self.assertEqual(desdobramento_suporte_bh(servico, "3106200", "010701", "producao"), "")
        self.assertEqual(desdobramento_suporte_bh(servico, "3550308", "010701", "homologacao"), "")
        self.assertEqual(desdobramento_suporte_bh(servico, "3106200", "140101", "homologacao"), "")
        self.assertEqual(desdobramento_suporte_bh({}, "3106200", "010701", "homologacao"), "")

    def test_codigo_salvo_preserva_desdobro(self):
        self.assertEqual(codigo_nacional_salvo({"codigo_servico": "01.03.02"}), "010302")
        self.assertEqual(codigo_nacional_salvo({"codigo_servico": "14.01.01"}), "140101")
        self.assertEqual(codigo_nacional_salvo({"item_lista_servico": "01.07"}), "")
        self.assertEqual(codigo_nacional_salvo({"codigo_servico": "0107"}), "")
        self.assertEqual(codigo_nacional_salvo(None), "")

    def test_corrige_somente_semente_intacta(self):
        cursor = Mock()
        cursor.fetchone.return_value = {"total": 0}
        anterior = ("Instalacao de Office e aplicativos", "01.07.02", "01.07", 0, "Sim", "observacao original")
        cadastrar_catalogo_ti(cursor, [anterior])
        sql, params = cursor.execute.call_args_list[0].args
        self.assertIn("AND observacoes=?", sql)
        self.assertIn("AND aliquota_iss=?", sql)
        self.assertEqual(params, ("01.07.01",) + anterior)
        inserts = [call.args[1] for call in cursor.execute.call_args_list if call.args[0].startswith("INSERT")]
        self.assertEqual(inserts[0][1], "01.07.01")
        self.assertEqual(len(inserts), 1 + len(SERVICOS_TI_ADICIONAIS))

    def test_nao_reinsere_cadastro_existente(self):
        cursor = Mock()
        cursor.fetchone.return_value = (1,)
        cadastrar_catalogo_ti(cursor, [])
        self.assertFalse(any(call.args[0].startswith("INSERT") for call in cursor.execute.call_args_list))


if __name__ == "__main__":
    unittest.main()
