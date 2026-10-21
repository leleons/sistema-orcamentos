import io
import unittest
from lxml import etree
from pypdf import PdfReader
from tests import test_nfe_produto as exemplos
from dsystem_erp.services.nfe_produto import gerar_xml_nfe_produto_400, NFE_NS
from dsystem_erp.services.nfe_documento import montar_nfe_processada, gerar_danfe_autorizado


def exemplo_processado():
    fat, itens, dados = exemplos.NFeProdutoTests().exemplo()
    dados.update(emitente_nome='EMITENTE DE DEMONSTRACAO', emitente_logradouro='Rua de Teste',
                 emitente_numero='1', emitente_bairro='Centro', emitente_cep='31000000',
                 emitente_municipio='Belo Horizonte', observacoes='TESTE LOCAL SIMULADO. NAO TRANSMITIDO A SEFAZ.')
    xml = gerar_xml_nfe_produto_400(fat, itens, dados)
    chave = etree.fromstring(xml).find(f'{{{NFE_NS}}}infNFe').get('Id')[3:]
    retorno = f'''<protNFe xmlns="{NFE_NS}" versao="4.00"><infProt><tpAmb>2</tpAmb>
        <chNFe>{chave}</chNFe><cStat>100</cStat><nProt>000000000000000</nProt>
        <dhRecbto>2026-09-24T12:00:00-03:00</dhRecbto><xMotivo>TESTE SIMULADO</xMotivo>
        </infProt></protNFe>'''.encode()
    return xml, retorno


class DocumentoNfeTests(unittest.TestCase):
    def test_danfe_com_xml_processado_e_marca_homologacao(self):
        xml, retorno = exemplo_processado()
        pdf = gerar_danfe_autorizado(montar_nfe_processada(xml, retorno))
        texto = '\n'.join(p.extract_text() for p in PdfReader(io.BytesIO(pdf)).pages)
        self.assertIn('SEM VALOR FISCAL', texto)
        self.assertIn('Mouse', texto)
        self.assertIn('TESTE LOCAL SIMULADO', texto)

    def test_rejeita_protocolo_incompativel(self):
        xml, retorno = exemplo_processado()
        for invalido in [retorno.replace(b'<tpAmb>2', b'<tpAmb>1'),
                         retorno.replace(b'<cStat>100', b'<cStat>204'),
                         retorno.replace(b'<chNFe>', b'<chNFe>9')]:
            with self.assertRaises(ValueError): montar_nfe_processada(xml, invalido)
