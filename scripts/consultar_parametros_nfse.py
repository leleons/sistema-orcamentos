"""Consulta somente leitura da API oficial de homologação, com o A1 local."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import urllib.request
import urllib.error
import mysql.connector
from dsystem_erp.config import config_val, get_settings
from dsystem_erp.services.nfse_soap import contexto_ssl_certificado_pfx


def configuracao_local():
    keys = ['NFSE_CERT_PFX_PATH', 'NFSE_CERT_PASSWORD', 'NFSE_CODIGO_MUNICIPIO']
    values = {k: config_val(k, '') for k in keys}
    settings = get_settings().database
    if settings.host not in ('localhost', '127.0.0.1', '::1'):
        raise ValueError('Este diagnóstico usa somente a configuração do banco local.')
    conn = mysql.connector.connect(host=settings.host, port=settings.port, user=settings.user,
                                   password=settings.password, database=settings.database, connection_timeout=5)
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT chave,valor FROM configuracoes_sistema WHERE chave IN (%s,%s,%s)', tuple(keys))
        for key, value in cursor.fetchall():
            if value:
                values[key] = value
        cursor.close()
    finally:
        conn.close()
    return values


def consultar(caminho):
    if not caminho.startswith('/parametrizacao/') or '..' in caminho:
        raise ValueError('Use um caminho da API de parametrização.')
    values = configuracao_local()
    with contexto_ssl_certificado_pfx(values['NFSE_CERT_PFX_PATH'], values['NFSE_CERT_PASSWORD']) as ctx:
        request = urllib.request.Request('https://adn.producaorestrita.nfse.gov.br' + caminho, method='GET')
        try:
            with urllib.request.urlopen(request, context=ctx, timeout=25) as response:
                return response.read().decode('utf-8')
        except urllib.error.HTTPError as ex:
            raise RuntimeError(f'HTTP {ex.code}: {ex.read().decode("utf-8", errors="replace")}') from None


if __name__ == '__main__':
    print(consultar(sys.argv[1]))
