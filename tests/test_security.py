import unittest

from dsystem_erp.services.security import chave_parece_segredo, limpar_segredos_dict, mascarar_segredo


class SecurityTests(unittest.TestCase):
    def test_mascara_segredo_sem_expor_valor_inteiro(self):
        self.assertEqual(mascarar_segredo("abcdef123456"), "ab********56")
        self.assertEqual(mascarar_segredo("123"), "***")
        self.assertEqual(mascarar_segredo(None), "")

    def test_detecta_chaves_sensiveis(self):
        self.assertTrue(chave_parece_segredo("senha_certificado"))
        self.assertTrue(chave_parece_segredo("api_token"))
        self.assertFalse(chave_parece_segredo("cliente"))

    def test_limpa_dict_preservando_campos_normais(self):
        dados = limpar_segredos_dict({"cliente": "Empresa", "senha": "abcdef"})

        self.assertEqual(dados["cliente"], "Empresa")
        self.assertNotEqual(dados["senha"], "abcdef")


if __name__ == "__main__":
    unittest.main()
