import unittest
from unittest.mock import patch, MagicMock
from urllib.error import HTTPError
from dsystem_erp.services.danfse import (
    baixar_danfse_oficial,
    conferir_xml_nacional,
    link_eh_danfse_oficial,
    url_consulta_publica,
    url_danfse,
    validar_pdf_danfse_anexado,
)

CHAVE = '3' * 50


class DanfseTests(unittest.TestCase):
    def xml(self, ambiente='2'):
        return f'<NFSe xmlns="http://www.sped.fazenda.gov.br/nfse"><infNFSe Id="NFS{CHAVE}"><nNFSe>2</nNFSe><DPS><infDPS><tpAmb>{ambiente}</tpAmb><dCompet>2026-09-15</dCompet></infDPS></DPS></infNFSe></NFSe>'

    def test_ambiente_do_xml_e_chave(self):
        dados = conferir_xml_nacional(self.xml(), CHAVE)
        self.assertEqual(dados['ambiente'], '2')
        self.assertIn('adn.producaorestrita.nfse.gov.br', url_danfse(dados['chave'], dados['ambiente']))
        self.assertEqual(conferir_xml_nacional(self.xml('1'))['ambiente'], '1')

    def test_rejeita_xml_incompleto_ou_divergente(self):
        for xml, chave in [(self.xml(''), CHAVE), ('<DPS/>', ''), ('invalido',''), (self.xml(),'4'*50)]:
            with self.subTest(xml=xml), self.assertRaises(ValueError):
                conferir_xml_nacional(xml, chave)

    def test_rejeita_url_injetada_e_ambiente_desconhecido(self):
        for chave, ambiente in [('https://example.com', '2'), (CHAVE, ''), (CHAVE,'teste')]:
            with self.assertRaises(ValueError):
                url_danfse(chave, ambiente)

    def test_reconhece_somente_link_oficial_exato(self):
        oficial = url_consulta_publica(CHAVE, '2')
        self.assertTrue(link_eh_danfse_oficial(oficial, CHAVE, '2'))
        self.assertFalse(link_eh_danfse_oficial(oficial + '?arquivo=outro', CHAVE, '2'))
        self.assertFalse(link_eh_danfse_oficial('https://example.com/danfse/' + CHAVE, CHAVE, '2'))

    def test_consulta_publica_separa_ambientes(self):
        self.assertIn('www.nfse.gov.br/ConsultaPublica/', url_consulta_publica(CHAVE, '1'))
        self.assertIn('www.producaorestrita.nfse.gov.br/ConsultaPublica/', url_consulta_publica(CHAVE, '2'))

    def test_anexo_rejeita_pdf_auxiliar_do_dsystem(self):
        self.assertEqual(
            validar_pdf_danfse_anexado(b'%PDF-1.4\noficial\n%%EOF'),
            b'%PDF-1.4\noficial\n%%EOF',
        )
        with self.assertRaisesRegex(ValueError, 'antigo PDF auxiliar'):
            validar_pdf_danfse_anexado(b'%PDF-1.4\nDsystem ERP\n%%EOF')

    @patch('dsystem_erp.services.danfse.contexto_ssl_certificado_pfx')
    @patch('dsystem_erp.services.danfse.build_opener')
    def test_download_somente_get_pdf(self, build, cert):
        esperado = b'%PDF-1.4\nconteudo\n%%EOF'
        build.return_value.open.return_value.__enter__.return_value.read.return_value = esperado
        self.assertEqual(baixar_danfse_oficial(CHAVE,'2','teste.pfx','segredo'), esperado)
        req = build.return_value.open.call_args.args[0]
        self.assertEqual(req.get_method(),'GET')
        self.assertEqual(req.full_url, url_danfse(CHAVE,'2'))

    @patch('dsystem_erp.services.danfse.contexto_ssl_certificado_pfx')
    @patch('dsystem_erp.services.danfse.build_opener')
    def test_html_nao_e_pdf(self, build, cert):
        build.return_value.open.return_value.__enter__.return_value.read.return_value = b'<html>erro</html>'
        with self.assertRaisesRegex(ValueError, 'PDF completo'):
            baixar_danfse_oficial(CHAVE,'2','teste.pfx','segredo')

    @patch('dsystem_erp.services.danfse.contexto_ssl_certificado_pfx')
    @patch('dsystem_erp.services.danfse.build_opener')
    def test_404_nao_reemite(self, build, cert):
        build.return_value.open.side_effect = HTTPError('https://example.com',404,'erro',{},None)
        with self.assertRaisesRegex(ValueError,'não localizado'):
            baixar_danfse_oficial(CHAVE,'2','teste.pfx','segredo')
        self.assertEqual(build.return_value.open.call_count,1)


if __name__ == '__main__':
    unittest.main()
