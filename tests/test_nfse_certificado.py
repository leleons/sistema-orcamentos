import unittest

from dsystem_erp.services.nfse_certificado import certificado_bate_com_cnpj


class NfseCertificadoTests(unittest.TestCase):
    def test_compara_cnpj_certificado_com_formatacao(self):
        info = {"documentos": ["23524449000154"]}

        self.assertTrue(certificado_bate_com_cnpj(info, "23.524.449/0001-54"))
        self.assertFalse(certificado_bate_com_cnpj(info, "00.000.000/0000-00"))


if __name__ == "__main__":
    unittest.main()
