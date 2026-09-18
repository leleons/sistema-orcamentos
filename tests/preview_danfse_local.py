"""Prévia isolada e assets gráficos públicos extraídos do exemplo fornecido."""
from pathlib import Path
from dsystem_erp.services.danfse_local import gerar_danfse_local

CHAVE = '31062002223524449000154000000000000226090925398160'

def xml_exemplo():
    return f'''<NFSe xmlns="http://www.sped.fazenda.gov.br/nfse"><infNFSe Id="NFS{CHAVE}">
    <xLocEmi>Belo Horizonte - MG</xLocEmi><xLocPrestacao>Belo Horizonte / MG</xLocPrestacao><xLocIncid>Belo Horizonte / MG</xLocIncid><ambGer>2</ambGer><nNFSe>2</nNFSe><dhProc>2026-09-15T08:40:09-03:00</dhProc>
    <emit><CNPJ>23524449000154</CNPJ><xNome>D F PEREIRA INFORMATICA</xNome><enderNac><xLgr>RUA ALTO GUANDU</xLgr><nro>106</nro><xBairro>SAO PAULO</xBairro><cMun>3106200</cMun><CEP>31910230</CEP><UF>MG</UF></enderNac></emit>
    <valores><vBC>1.00</vBC><pAliqAplic>2.50</pAliqAplic><vISSQN>0.02</vISSQN><vLiq>1.00</vLiq></valores>
    <DPS><infDPS><tpAmb>2</tpAmb><tpEmit>1</tpEmit><dhEmi>2026-09-15T08:40:08-03:00</dhEmi><serie>1</serie><nDPS>1</nDPS><dCompet>2026-09-15</dCompet><prest><regTrib><opSimpNac>1</opSimpNac></regTrib></prest>
    <toma><CNPJ>15811502000170</CNPJ><xNome>CONDOMINIO RESIDENCIAL MIRANTE DA SERRA</xNome><fone>31333111753</fone></toma>
    <serv><locPrest><cLocPrestacao>3106200</cLocPrestacao></locPrest><cServ><cTribNac>010701</cTribNac><cTribMun>001</cTribMun><xDescServ>suporte - Qtd: 1 - Total: R$ 1,00</xDescServ></cServ></serv>
    <valores><vServPrest><vServ>1.00</vServ></vServPrest><trib><tribMun><tribISSQN>1</tribISSQN><tpRetISSQN>1</tpRetISSQN></tribMun><totTrib><vTotTrib><vTotTribFed>0.00</vTotTribFed><vTotTribEst>0.00</vTotTribEst><vTotTribMun>0.00</vTotTribMun></vTotTrib></totTrib></trib></valores>
    </infDPS></DPS></infNFSe></NFSe>'''

if __name__ == '__main__':
    import fitz
    ref = fitz.open(r'C:\Users\Leonel\Downloads\31062002223524449000154000000000000226090925398160 (1).pdf')
    asset = Path('dsystem_erp/services/assets/nfse_logo.png')
    asset.parent.mkdir(parents=True, exist_ok=True)
    # Extract only the public NFS-e logo; never carry QR or note data into assets.
    logo = next(im for im in ref[0].get_images() if im[2:4] == (540,107))
    pix = fitz.Pixmap(ref, logo[0])
    if logo[1]:
        pix = fitz.Pixmap(pix, fitz.Pixmap(ref, logo[1]))
    pix.save(asset)
    out = Path('output/pdf/previa_danfse_local.pdf')
    out.parent.mkdir(parents=True, exist_ok=True)
    real_xml = Path(r'C:\Users\Leonel\Downloads\nota_4_retorno.xml').read_bytes()
    out.write_bytes(gerar_danfse_local({'xml_autorizado':real_xml, 'chave_acesso':CHAVE}))
    pdf = fitz.open(out)
    pdf[0].get_pixmap(matrix=fitz.Matrix(1.5,1.5)).save('tmp/pdfs/danfse_local.png')
    print(out.resolve())
