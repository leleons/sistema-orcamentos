"""Preenchimento da NF-e com dados já cadastrados, sem consultas externas."""
import re


def destinatario_do_cadastro(cliente):
    cliente = cliente or {}
    municipio = str(cliente.get('municipio') or cliente.get('cidade_estado') or '').strip()
    uf = str(cliente.get('uf') or '').strip().upper()
    sufixo = re.match(r'^(.*?)\s*[/\-]\s*([A-Za-z]{2})$', municipio)
    if sufixo:
        municipio = sufixo.group(1).strip()
        uf = uf or sufixo.group(2).upper()
    # A abreviação cadastrada não deve ser enviada como nome do município.
    if municipio.upper() == 'BH' and uf == 'MG':
        municipio = 'Belo Horizonte'
    digitos = lambda valor: re.sub(r'\D', '', str(valor or ''))
    ie = str(cliente.get('estado_insc_estadual') or cliente.get('inscricao_estadual') or '').strip()
    indicador = str(cliente.get('indicador_ie') or '').strip()
    if indicador not in ('1', '2', '9'):
        # Ausência de IE não comprova que o cliente é não contribuinte.
        indicador = ''
    return dict(logradouro=str(cliente.get('endereco') or ''), numero=str(cliente.get('numero') or ''),
                complemento=str(cliente.get('complemento') or ''), bairro=str(cliente.get('bairro') or ''),
                municipio=municipio, uf=uf, codigo_municipio=digitos(cliente.get('codigo_ibge')),
                cep=digitos(cliente.get('cep')), telefone=digitos(cliente.get('telefone')),
                email=str(cliente.get('email') or ''), ie=ie, indicador_ie=indicador)
