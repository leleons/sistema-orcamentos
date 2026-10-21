"""Pré-cadastro local Windows, cifrado por DPAPI e restrito à conta do usuário.

Não concede permissões, não cria empresa e não vincula automaticamente uma conta
bancária. O vínculo requer usuário autorizado e confirmação explícita no ERP.
"""
import base64
import ctypes
import json
import os
from pathlib import Path


def pasta_local():
    from dsystem_erp.config import config_val
    configurada = config_val('DSYSTEM_INTER_VAULT_DIR', '')
    if os.name != 'nt':
        raise ValueError('Pré-cadastro local disponível somente neste usuário do Windows.')
    if configurada:
        pasta = Path(configurada)
        if not pasta.is_absolute():
            raise ValueError('DSYSTEM_INTER_VAULT_DIR deve ser um caminho absoluto fora do projeto.')
    elif os.environ.get('LOCALAPPDATA'):
        pasta = Path(os.environ['LOCALAPPDATA']) / 'DSystem' / 'Inter'
    else:
        raise ValueError('Configure DSYSTEM_INTER_VAULT_DIR para o cofre protegido deste usuário Windows.')
    pasta = pasta.resolve()
    if pasta.is_relative_to(Path(__file__).resolve().parents[2]):
        raise ValueError('O cofre local precisa ficar fora do projeto.')
    return pasta


def _dpapi(conteudo, *, decifrar=False):
    if os.name != 'nt':
        raise ValueError('DPAPI requer Windows.')
    from ctypes import wintypes
    class Blob(ctypes.Structure):
        _fields_ = [('tamanho', wintypes.DWORD), ('dados', ctypes.POINTER(ctypes.c_byte))]
    buffer = ctypes.create_string_buffer(conteudo)
    entrada = Blob(len(conteudo), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)))
    saida = Blob()
    crypt32 = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    func = crypt32.CryptUnprotectData if decifrar else crypt32.CryptProtectData
    func.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p,
                    ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    func.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    if not func(ctypes.byref(entrada), None, None, None, None, 1, ctypes.byref(saida)):
        raise ValueError('Não foi possível acessar o cofre protegido deste usuário Windows.')
    try:
        return ctypes.string_at(saida.dados, saida.tamanho)
    finally:
        kernel32.LocalFree(saida.dados)


def existe_pendente():
    try:
        return (pasta_local() / 'credenciais_pendentes.dpapi').is_file()
    except ValueError:
        return False


def preparar_pendente(client_id, client_secret, zip_bytes):
    from .inter_runtime import ler_zip_certificado, validar_par_certificado, _proteger_pasta_certificados
    for valor in (client_id, client_secret):
        if not isinstance(valor, str) or not 1 <= len(valor) <= 2048 or any(c.isspace() for c in valor):
            raise ValueError('Client ID/Secret inválidos; não foram salvos.')
    cert, chave = ler_zip_certificado(zip_bytes)
    validade = validar_par_certificado(cert, chave)
    pasta = pasta_local()
    pasta.mkdir(parents=True, exist_ok=True)
    _proteger_pasta_certificados(pasta)
    dados = {'ambiente': 'producao', 'dados': {'conta': '', 'client_id': client_id,
             'client_secret': client_secret, 'escopos': ['extrato.read']},
             'certificado': base64.b64encode(cert).decode(), 'chave': base64.b64encode(chave).decode()}
    cifrado = _dpapi(json.dumps(dados).encode())
    # Exclusivo: nunca sobrescrever configuração anterior silenciosamente.
    with (pasta / 'credenciais_pendentes.dpapi').open('xb') as arquivo:
        arquivo.write(cifrado)
    mestre = pasta / 'master.dpapi'
    if not mestre.exists():
        with mestre.open('xb') as arquivo:
            arquivo.write(_dpapi(os.urandom(32)))
    certificados = pasta / 'certificados'
    certificados.mkdir(exist_ok=True)
    _proteger_pasta_certificados(certificados)
    return {'preparada': True, 'validade_certificado': validade, 'pagamentos_bloqueados': True}


def ler_pendente():
    try:
        bruto = (pasta_local() / 'credenciais_pendentes.dpapi').read_bytes()
        if len(bruto) > 524288:
            raise ValueError
        dados = json.loads(_dpapi(bruto, decifrar=True))
        if dados['ambiente'] != 'producao' or dados['dados']['escopos'] != ['extrato.read']:
            raise ValueError
        cert = base64.b64decode(dados['certificado'], validate=True)
        chave = base64.b64decode(dados['chave'], validate=True)
        from .inter_runtime import validar_par_certificado
        validar_par_certificado(cert, chave)
        return dados['dados'], cert, chave
    except (KeyError, TypeError, ValueError, OSError):
        raise ValueError('Pacote local ausente, inválido ou pertencente a outro usuário Windows.') from None


def chave_mestra_local():
    try:
        chave = _dpapi((pasta_local() / 'master.dpapi').read_bytes(), decifrar=True)
        if len(chave) == 32:
            return chave
    except (ValueError, OSError):
        pass
    raise ValueError('Não foi possível abrir a chave mestra salva. Confira DSYSTEM_INTER_VAULT_DIR e execute o ERP com o mesmo usuário Windows que preparou o cofre. Não gere outra chave para credenciais já cadastradas.')


def importar_pendente(repo, empresa, usuario):
    from .permissions import usuario_tem_permissao
    if (not usuario.get('autenticado') or usuario.get('tipo_login') == 'cliente'
            or not usuario_tem_permissao('inter.configurar', usuario)):
        raise PermissionError('Sem permissão para configurar integração.')
    with repo.transacao() as c:
        repo.exigir_empresa(c, empresa, usuario['username'])
    dados, cert, chave = ler_pendente()
    from .inter_runtime import salvar_credencial_upload
    return salvar_credencial_upload(repo, empresa, usuario, dados, cert, chave, ambiente='producao')


def testar_consulta_pendente():
    """Somente chamada explícita do operador; saldo não é exibido nem armazenado."""
    import tempfile
    from .inter_runtime import _proteger_pasta_certificados
    from .inter_api import ClienteInter, CredencialInter
    dados, cert, chave = ler_pendente()
    # ID 0 representa apenas esta sondagem técnica, não cadastro de uma empresa.
    with tempfile.TemporaryDirectory(prefix='validacao-', dir=pasta_local()) as temporario:
        pasta = Path(temporario)
        _proteger_pasta_certificados(pasta)
        for nome, conteudo in (('cert.pem', cert), ('key.pem', chave)):
            with (pasta / nome).open('xb') as arquivo:
                arquivo.write(conteudo)
        cliente = ClienteInter(CredencialInter(empresa_id=0, **dados, ambiente='producao',
            certificado=str(pasta/'cert.pem'), chave=str(pasta/'key.pem')), permitir_producao_consulta=True)
        try:
            resposta = cliente.chamar('saldo', empresa_id=0)
            if not isinstance(resposta, dict) or 'disponivel' not in resposta:
                raise ValueError('Resposta de saldo sem o campo esperado; validação inconclusiva.')
            return {'oauth_mtls': 'OK', 'consulta_saldo': 'OK', 'pagamentos_bloqueados': True}
        finally:
            cliente.session.close()
