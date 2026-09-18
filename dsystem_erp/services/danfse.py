"""Consulta somente leitura do DANFSe nas APIs oficiais do ADN.

Fonte: gov.br/nfse/pt-br/biblioteca/documentacao-tecnica/apis-prod-restrita-e-producao
Manual ADN, seção 1.5: GET /danfse/{chaveAcesso}.
"""
import re
from lxml import etree
from urllib.request import Request, build_opener, HTTPSHandler, HTTPRedirectHandler
from urllib.error import HTTPError, URLError
from dsystem_erp.services.nfse_soap import contexto_ssl_certificado_pfx


def conferir_xml_nacional(xml, chave_esperada=''):
    """Leitura estrutural, não valida assinatura, XSD ou situação fiscal atual."""
    if not xml:
        raise ValueError('Esta nota não possui XML autorizado salvo.')
    try:
        root = etree.fromstring(xml.encode() if isinstance(xml, str) else xml,
            etree.XMLParser(resolve_entities=False, no_network=True))
    except (etree.XMLSyntaxError, ValueError, TypeError) as erro:
        raise ValueError('XML autorizado inválido ou ilegível.') from erro
    ns = {'n':'http://www.sped.fazenda.gov.br/nfse'}
    if root.tag != '{http://www.sped.fazenda.gov.br/nfse}NFSe':
        raise ValueError('É necessário o XML NFS-e autorizado, não somente a DPS enviada.')
    infs = root.findall('n:infNFSe', ns)
    if len(infs) != 1:
        raise ValueError('XML sem identificação única da NFS-e.')
    inf = infs[0]
    chave = inf.get('Id', '').removeprefix('NFS')
    if not re.fullmatch(r'[0-9]{50}', chave):
        raise ValueError('Chave nacional inválida no XML: são necessários 50 dígitos.')
    if chave_esperada and str(chave_esperada).strip() != chave:
        raise ValueError('A chave do XML difere da chave salva na nota. Consulta bloqueada.')

    def texto(caminho):
        return inf.findtext(caminho, default='', namespaces=ns)

    ambiente = texto('n:DPS/n:infDPS/n:tpAmb')
    if ambiente not in ('1', '2'):
        raise ValueError('Ambiente ausente ou desconhecido no XML. Não será presumido.')
    return {'chave':chave, 'ambiente':ambiente, 'numero':texto('n:nNFSe'),
        'competencia':texto('n:DPS/n:infDPS/n:dCompet'),
        'valor':texto('n:DPS/n:infDPS/n:valores/n:vServPrest/n:vServ'),
        'codigo_nacional':texto('n:DPS/n:infDPS/n:serv/n:cServ/n:cTribNac'),
        'codigo_municipal':texto('n:DPS/n:infDPS/n:serv/n:cServ/n:cTribMun'),
        'emissao':texto('n:DPS/n:infDPS/n:dhEmi')}


def url_danfse(chave, ambiente):
    """Endpoint legado. A API v1 foi desativada pelo governo em 2026."""
    if not re.fullmatch(r'[0-9]{50}', str(chave)):
        raise ValueError('Chave nacional deve conter exatamente 50 dígitos.')
    hosts = {'1':'adn.nfse.gov.br', '2':'adn.producaorestrita.nfse.gov.br'}
    if ambiente not in hosts:
        raise ValueError('Ambiente inválido. Consulta bloqueada.')
    return f'https://{hosts[ambiente]}/danfse/{chave}'


def url_consulta_publica(chave, ambiente):
    if not re.fullmatch(r'[0-9]{50}', str(chave)):
        raise ValueError('Chave nacional deve conter exatamente 50 dígitos.')
    hosts = {
        '1': 'www.nfse.gov.br',
        '2': 'www.producaorestrita.nfse.gov.br',
    }
    if ambiente not in hosts:
        raise ValueError('Ambiente inválido. Consulta bloqueada.')
    return f'https://{hosts[ambiente]}/ConsultaPublica/?tpc=1&chave={chave}'


def link_eh_danfse_oficial(link, chave, ambiente):
    """Confirma a origem persistida sem aceitar outro host ou outra chave."""
    try:
        return str(link or '').strip() == url_consulta_publica(chave, ambiente)
    except ValueError:
        return False


def validar_pdf_danfse_anexado(pdf):
    """Valida o contêiner antes de guardar o PDF obtido na Consulta Pública."""
    dados = bytes(pdf or b'')
    if len(dados) > 20 * 1024 * 1024:
        raise ValueError('O PDF ultrapassa o limite de 20 MB.')
    if not dados.startswith(b'%PDF-') or b'%%EOF' not in dados[-2048:]:
        raise ValueError('O arquivo selecionado não é um PDF completo válido.')
    if b'Dsystem ERP' in dados:
        raise ValueError('Este é o antigo PDF auxiliar do Dsystem, não o DANFSe baixado do governo.')
    return dados


class _SemRedirecionamento(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def baixar_danfse_oficial(chave, ambiente, cert_path, cert_password, timeout=30):
    url = url_danfse(chave, ambiente)
    if not cert_path:
        raise ValueError('Configure o certificado A1/PFX para consultar o DANFSe.')
    try:
        with contexto_ssl_certificado_pfx(cert_path, cert_password) as contexto:
            opener = build_opener(HTTPSHandler(context=contexto), _SemRedirecionamento())
            req = Request(url, headers={'Accept':'application/pdf'}, method='GET')
            with opener.open(req, timeout=timeout) as resposta:
                limite = 20 * 1024 * 1024
                pdf = resposta.read(limite + 1)
                if len(pdf) > limite or not pdf.startswith(b'%PDF-') or b'%%EOF' not in pdf[-2048:]:
                    raise ValueError('O ADN não retornou um PDF completo válido. Nenhum arquivo foi substituído.')
                return pdf
    except HTTPError as erro:
        mensagens = {404:'DANFSe não localizado no ADN. A nota pode ainda não estar disponível para consulta.',
            401:'Acesso não autorizado: confira o certificado.', 403:'Acesso negado pelo ADN: confira o certificado.',
            429:'Limite de consultas atingido. Aguarde antes de tentar novamente.'}
        raise ValueError(mensagens.get(erro.code, f'ADN retornou HTTP {erro.code}. Não emita outra nota para tentar baixar o PDF.')) from erro
    except (URLError, TimeoutError) as erro:
        raise ValueError('Não foi possível conectar ao ADN. A nota não foi alterada; tente consultar mais tarde.') from erro
