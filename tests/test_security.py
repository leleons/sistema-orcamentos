import unittest

from dsystem_erp.services.security import (
    chave_parece_segredo,
    codigo_totp,
    criar_hash_senha,
    limpar_segredos_dict,
    mascarar_segredo,
    senha_esta_com_hash,
    uri_totp_cliente,
    verificar_senha,
    verificar_totp,
)


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

    def test_hash_de_senha_e_compatibilidade_legada(self):
        senha_hash = criar_hash_senha("senha-forte", iteracoes=1_000)

        self.assertTrue(senha_esta_com_hash(senha_hash))
        self.assertTrue(verificar_senha("senha-forte", senha_hash))
        self.assertFalse(verificar_senha("incorreta", senha_hash))
        self.assertTrue(verificar_senha("senha-legada", "senha-legada"))

    def test_totp_deterministico_e_uri_do_autenticador(self):
        secret = "JBSWY3DPEHPK3PXP"
        momento = 1_700_000_000
        codigo = codigo_totp(secret, momento=momento)

        self.assertEqual(len(codigo), 6)
        self.assertTrue(verificar_totp(secret, codigo, janela=0, momento=momento))
        self.assertIn("otpauth://totp/", uri_totp_cliente("cliente@example.com", secret))


if __name__ == "__main__":
    unittest.main()
