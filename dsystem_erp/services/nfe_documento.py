"""Documento auxiliar gerado somente com XML e protocolo compatíveis."""
from lxml import etree
from dsystem_erp.services.nfe_produto import NFE_NS


def montar_nfe_processada(xml_assinado, retorno):
    parser = etree.XMLParser(resolve_entities=False, no_network=True)
    nfe = etree.fromstring(xml_assinado, parser)
    resposta = etree.fromstring(retorno, parser)
    ns = {'n': NFE_NS}
    inf = nfe.find('n:infNFe', ns)
    if nfe.tag != f'{{{NFE_NS}}}NFe' or inf is None:
        raise ValueError('XML enviado não contém NF-e.')
    chave = inf.get('Id', '').removeprefix('NFe')
    protocolo = resposta if resposta.tag == f'{{{NFE_NS}}}protNFe' else resposta.find('.//n:protNFe', ns)
    if (protocolo is None or protocolo.findtext('n:infProt/n:cStat', namespaces=ns) != '100'
            or protocolo.findtext('n:infProt/n:chNFe', namespaces=ns) != chave
            or protocolo.findtext('n:infProt/n:tpAmb', namespaces=ns) != inf.findtext('n:ide/n:tpAmb', namespaces=ns)):
        raise ValueError('Protocolo de autorização não corresponde à chave e ao ambiente da NF-e enviada.')
    raiz = etree.Element(f'{{{NFE_NS}}}nfeProc', nsmap={None: NFE_NS}, versao='4.00')
    raiz.append(nfe)
    raiz.append(protocolo)
    return etree.tostring(raiz, encoding='UTF-8', xml_declaration=True)


def gerar_danfe_autorizado(xml_processado):
    from brazilfiscalreport.danfe import Danfe
    raiz = etree.fromstring(xml_processado, etree.XMLParser(resolve_entities=False, no_network=True))
    ns = {'n': NFE_NS}
    nfe = raiz.find('n:NFe', ns)
    protocolo = raiz.find('n:protNFe', ns)
    if nfe is None or protocolo is None:
        raise ValueError('DANFE requer XML processado com autorização.')
    montar_nfe_processada(etree.tostring(nfe), etree.tostring(protocolo))
    return bytes(Danfe(xml_processado.decode('utf-8')).output())
