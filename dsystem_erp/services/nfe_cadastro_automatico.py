"""Consultas somente leitura; ausência de cadastro nunca significa não contribuinte."""
import re
import unicodedata
from urllib.request import Request, build_opener, HTTPSHandler, HTTPRedirectHandler
from xml.etree import ElementTree as ET

from dsystem_erp.services.dados_publicos import cnpj_valido, consultar_cnpj, consultar_cep
from dsystem_erp.services.nfe_cliente import destinatario_do_cadastro
from dsystem_erp.services.nfse_soap import contexto_ssl_certificado_pfx

NS = 'http://www.portalfiscal.inf.br/nfe'
WS = NS + '/wsdl/CadConsultaCadastro4'


def digitos(value):
    return re.sub(r'\D', '', str(value or ''))


def normalizar(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(value or '').upper())
                   if not unicodedata.combining(c)).strip()


def interpretar_cadastro(xml, documento, uf):
    root = ET.fromstring(xml)
    info = root.find('.//{' + NS + '}infCons')
    if info is None:
        raise ValueError('A SEFAZ não retornou uma consulta cadastral válida.')
    text = lambda node, name: node.findtext('{' + NS + '}' + name, '').strip()
    if text(info, 'cStat') not in ('111', '112'):
        raise ValueError('Consulta SEFAZ: ' + text(info, 'cStat') + ' — ' + text(info, 'xMotivo'))
    if digitos(text(info, 'CNPJ')) != documento or text(info, 'UF') != uf:
        raise ValueError('Resposta SEFAZ não corresponde ao CNPJ/UF consultado.')
    ativos = [item for item in info.findall('{' + NS + '}infCad')
              if digitos(text(item, 'CNPJ')) == documento and text(item, 'UF') == uf
              and text(item, 'cSit') == '1' and digitos(text(item, 'IE'))]
    if len(ativos) != 1:
        raise ValueError('A SEFAZ não confirmou uma única inscrição ativa. Confirme a situação e a IE manualmente.')
    return {'ie': digitos(text(ativos[0], 'IE')), 'indicador_ie': '1'}


class SemRedirecionamento(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def consultar_ie(documento, uf, ambiente, cert_path, cert_password):
    if uf != 'MG':
        raise ValueError('Consulta automática de IE disponível para MG. Para esta UF, confirme o cadastro fiscal.')
    if ambiente not in ('homologacao', 'producao') or not cnpj_valido(documento):
        raise ValueError('CNPJ ou ambiente inválido para consulta SEFAZ.')
    if not cert_path:
        raise ValueError('Configure o certificado A1 para consultar a inscrição estadual.')
    host = 'hnfe' if ambiente == 'homologacao' else 'nfe'
    envelope = (
        f'<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope">'
        f'<s:Header><nfeCabecMsg xmlns="{WS}"><cUF>31</cUF>'
        '<versaoDados>2.00</versaoDados></nfeCabecMsg></s:Header>'
        f'<s:Body><nfeDadosMsg xmlns="{WS}"><ConsCad xmlns="{NS}" versao="2.00">'
        f'<infCons><xServ>CONS-CAD</xServ><UF>MG</UF><CNPJ>{documento}</CNPJ>'
        '</infCons></ConsCad></nfeDadosMsg></s:Body></s:Envelope>'
    )
    request = Request(f'https://{host}.fazenda.mg.gov.br/nfe2/services/CadConsultaCadastro4',
                      data=envelope.encode(), headers={
                          'Content-Type': f'application/soap+xml; charset=utf-8; action="{WS}/consultaCadastro"'})
    with contexto_ssl_certificado_pfx(cert_path, cert_password) as ctx:
        opener = build_opener(HTTPSHandler(context=ctx), SemRedirecionamento())
        with opener.open(request, timeout=12) as response:
            xml = response.read(2_000_001)
    if len(xml) > 2_000_000:
        raise ValueError('Resposta cadastral excedeu o tamanho permitido.')
    return interpretar_cadastro(xml, documento, uf)


def completar_destinatario(cliente, ambiente, cert_path='', cert_password=''):
    dados = destinatario_do_cadastro(cliente)
    avisos, fontes = [], []
    documento = digitos(cliente.get('cnpj'))
    if cnpj_valido(documento) and any(not dados[k] for k in ('logradouro', 'numero', 'municipio', 'uf', 'cep')):
        try:
            publico = destinatario_do_cadastro(consultar_cnpj(documento, timeout=8))
            for campo, valor in publico.items():
                if not dados.get(campo) and valor:
                    dados[campo] = valor
            fontes.append('BrasilAPI (dados cadastrais)')
        except Exception:
            avisos.append('Consulta de CNPJ indisponível. Os dados já cadastrados foram preservados.')
    if not dados['codigo_municipio'] and len(dados['cep']) == 8:
        try:
            cep = destinatario_do_cadastro(consultar_cep(dados['cep'], timeout=8))
            if ((not dados['uf'] or dados['uf'] == cep['uf']) and
                    (not dados['municipio'] or normalizar(dados['municipio']) == normalizar(cep['municipio']))
                    and len(cep['codigo_municipio']) == 7):
                for campo in ('codigo_municipio', 'municipio', 'uf'):
                    dados[campo] = dados[campo] or cep[campo]
                fontes.append('ViaCEP (código IBGE)')
            else:
                avisos.append('O CEP não confirmou o município cadastrado. Confira o código IBGE.')
        except Exception:
            avisos.append('Consulta de CEP indisponível. Confira o código IBGE.')
    if not dados['indicador_ie'] or (dados['indicador_ie'] == '1' and not dados['ie']):
        if cnpj_valido(documento):
            try:
                fiscal = consultar_ie(documento, dados['uf'], ambiente, cert_path, cert_password)
                if dados['ie'] and digitos(dados['ie']) != fiscal['ie']:
                    avisos.append('A IE consultada difere do cadastro. Confira antes de emitir.')
                else:
                    dados.update(fiscal)
                    fontes.append('SEFAZ/MG (inscrição ativa)')
            except ValueError as exc:
                avisos.append(str(exc))
            except Exception:
                avisos.append('Consulta SEFAZ indisponível. Confirme a situação do ICMS e a IE ou tente novamente.')
        else:
            avisos.append('Confirme a situação do ICMS: não é inferida somente pelo CPF ou por CNPJ inválido.')
    return {'dados': dados, 'avisos': avisos, 'fontes': fontes}
