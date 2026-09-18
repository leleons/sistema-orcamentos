"""Prévia visual com dados fictícios; não acessa banco nem emite notas."""
from pathlib import Path
from dsystem_erp.services.nfse_pdf import gerar_pdf_nota_autorizada_simples

if __name__ == '__main__':
    nota = {'numero_nota':'2', 'status':'EXEMPLO VISUAL', 'cliente':'CLIENTE DE DEMONSTRAÇÃO',
        'valor_servicos':1, 'descricao':'Suporte técnico em informática. Atendimento de demonstração para avaliação do novo layout.',
        'xml_envio':'''<DPS><infDPS Id="DPS-DEMONSTRACAO"><tpAmb>2</tpAmb><dCompet>2026-09-15</dCompet>
        <prest><CNPJ>23524449000154</CNPJ><xNome>Dsystem Tecnologia - exemplo visual</xNome></prest>
        <cLocEmi>3106200</cLocEmi><cLocPrestacao>3106200</cLocPrestacao><cTribNac>010701</cTribNac><cTribMun>001</cTribMun>
        <vTotTribFed>0</vTotTribFed><vTotTribEst>0</vTotTribEst><vTotTribMun>0</vTotTribMun></infDPS></DPS>'''}
    destino = Path('output/pdf/previa_nota_servico.pdf')
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(gerar_pdf_nota_autorizada_simples(nota, {'mensagem':'EXEMPLO VISUAL - dados demonstrativos, não é uma nova emissão.'}))
    import fitz
    pdf = fitz.open(destino)
    for i, page in enumerate(pdf):
        page.get_pixmap().save(str(destino.with_suffix(f'.{i+1}.png')))
    print(f'{len(pdf)} página(s): {destino.resolve()}')
