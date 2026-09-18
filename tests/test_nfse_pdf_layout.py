import io
import unittest
from pypdf import PdfReader
from dsystem_erp.services.nfse_pdf import gerar_pdf_nota_autorizada_simples


class PdfLayoutTests(unittest.TestCase):
    def nota(self):
        return {'status':'Autorizada','numero_nota':'2','cliente':'Cliente <teste> & Companhia','valor_servicos':1,
            'descricao':'Suporte técnico', 'xml_envio':'<DPS><infDPS Id="DPS123"><tpAmb>2</tpAmb><prest><CNPJ>23524449000154</CNPJ></prest></infDPS></DPS>'}

    def test_homologacao_campos_e_escape(self):
        pdf = PdfReader(io.BytesIO(gerar_pdf_nota_autorizada_simples(self.nota(), {})))
        texto = '\n'.join(p.extract_text() for p in pdf.pages)
        self.assertIn('HOMOLOGAÇÃO - SEM VALIDADE FISCAL', texto)
        self.assertIn('Cliente <teste> & Companhia', texto)
        self.assertIn('Não substitui o DANFSe oficial', texto)
        self.assertIn('DPS123', texto)

    def test_descricao_longa_pagina_e_ambiente_desconhecido(self):
        nota = self.nota()
        nota.pop('xml_envio')
        nota['descricao'] = 'Descrição de serviço longa. ' * 600
        pdf = PdfReader(io.BytesIO(gerar_pdf_nota_autorizada_simples(nota, {})))
        self.assertGreater(len(pdf.pages), 1)
        for pagina in pdf.pages:
            self.assertIn('AMBIENTE NÃO IDENTIFICADO', pagina.extract_text())

    def test_xml_autorizado_tem_prioridade(self):
        nota = self.nota()
        nota['xml_autorizado'] = '<NFSe><tpAmb>1</tpAmb><nNFSe>77</nNFSe></NFSe>'
        texto = PdfReader(io.BytesIO(gerar_pdf_nota_autorizada_simples(nota, {}))).pages[0].extract_text()
        self.assertIn('AMBIENTE DE PRODUÇÃO', texto)
        self.assertNotIn('HOMOLOGAÇÃO', texto)


if __name__ == '__main__':
    unittest.main()
