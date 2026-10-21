"""Configuração explícita, usando o conector e autenticação existentes do ERP."""
import base64
import os
import re
from pathlib import Path

from dsystem_erp.config import config_val
from dsystem_erp.db import conectar_mysql
from dsystem_erp.repositories.inter import RepositorioInter
from dsystem_erp.services.inter_api import CredencialInter, ClienteInter, OPERACOES, CONSULTAS_PRODUCAO, cifrar_credencial, decifrar_credencial

ESCOPOS_MOVIMENTACAO = frozenset({
    'extrato.read', 'boleto-cobranca.write', 'boleto-cobranca.read',
    'pagamento-boleto.write', 'pagamento-boleto.read',
    'pagamento-pix.write', 'pagamento-pix.read',
})


def movimentacao_producao_liberada():
    return str(config_val('DSYSTEM_INTER_PERMITIR_MOVIMENTACAO', '') or '') == '1'
from dsystem_erp.services.inter_financeiro import FinanceiroInter
from dsystem_erp.services.permissions import usuario_tem_permissao


def chave_mestra():
    configurada = config_val('DSYSTEM_INTER_MASTER_KEY', '')
    if not configurada and os.name == 'nt':
        from .inter_pendente import chave_mestra_local
        return chave_mestra_local()
    try:
        chave = base64.b64decode(configurada, validate=True)
        if len(chave) != 32:
            raise ValueError
        return chave
    except (KeyError, ValueError):
        raise ValueError('Configure DSYSTEM_INTER_MASTER_KEY com 32 bytes em base64, fora do repositório.') from None


def repositorio_teste():
    banco = config_val('DSYSTEM_INTER_TEST_DATABASE', '')
    if not banco.endswith('_inter_teste') or not banco.replace('_', '').isalnum():
        raise PermissionError('Use uma base separada com sufixo _inter_teste; produção bloqueada.')
    return _repositorio_isolado(banco, financeiro_teste=True)


def repositorio_configuracao():
    """Configuração/auditoria separadas; nunca usa a base financeira de produção."""
    banco = config_val('DSYSTEM_INTER_CONFIG_DATABASE', '')
    if not banco.endswith('_inter_config') or not banco.replace('_', '').isalnum():
        raise PermissionError('Configure a base separada DSYSTEM_INTER_CONFIG_DATABASE, com sufixo _inter_config.')
    return _repositorio_isolado(banco, financeiro_teste=False)


def _repositorio_isolado(banco, *, financeiro_teste):
    def conectar():
        conn = conectar_mysql(banco)
        c = conn.cursor()
        c.execute('SELECT DATABASE() AS banco')
        if (c.fetchone() or {}).get('banco') != banco:
            conn.close()
            raise PermissionError('Banco divergente da base de testes.')
        c.execute("SELECT TABLE_NAME, ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=%s", (banco,))
        tabelas = c.fetchall()
        if any((r['TABLE_NAME'].startswith('inter_') or r['TABLE_NAME'] in ('contas_pagar','contas_receber'))
               and str(r['ENGINE']).upper() != 'INNODB' for r in tabelas):
            conn.close()
            raise PermissionError('A integração exige tabelas transacionais InnoDB na base de testes.')
        c.close()
        return conn
    return RepositorioInter(conectar, financeiro_teste=financeiro_teste)


def salvar_credencial(repo, empresa, usuario, dados, *, ambiente='sandbox'):
    if ambiente not in ('sandbox', 'producao'):
        raise ValueError('Ambiente inválido.')
    if (not usuario.get('autenticado') or usuario.get('tipo_login') == 'cliente'
            or not usuario_tem_permissao('inter.configurar', usuario)):
        raise PermissionError('Sem permissão para configurar integração.')
    campos = {'conta','client_id','client_secret','certificado','chave','escopos'}
    if set(dados) != campos or any(not dados[k] for k in campos - {'conta'}):
        raise ValueError('Informe Client ID, Client Secret, certificado, chave e escopos.')
    if not isinstance(dados['conta'], str) or (dados['conta'] and not re.fullmatch(r'[1-9][0-9]*', dados['conta'])):
        raise ValueError('Conta deve conter somente números, sem zeros iniciais.')
    if not isinstance(dados['escopos'], (list, tuple, set, frozenset)) or not set(dados['escopos']) <= {o[2] for o in OPERACOES.values()}:
        raise ValueError('Escopos inválidos para esta integração.')
    if ambiente == 'producao':
        escolhidos = set(dados['escopos'])
        if 'extrato.read' not in escolhidos:
            raise ValueError('Produção exige o escopo extrato.read.')
        if not movimentacao_producao_liberada() and escolhidos != {'extrato.read'}:
            raise ValueError('Produção admite somente extrato.read; pagamentos permanecem bloqueados.')
        if movimentacao_producao_liberada() and not escolhidos <= ESCOPOS_MOVIMENTACAO:
            raise ValueError('Escopo de produção não autorizado para cobrança/pagamento.')
    raiz = Path(__file__).resolve().parents[2]
    for campo in ('certificado','chave'):
        arquivo = Path(dados[campo]).resolve(strict=True)
        if arquivo.is_relative_to(raiz) or not arquivo.is_file():
            raise ValueError('Instale certificado/chave fora do projeto, protegidos por ACL/permissões do sistema.')
        if os.name != 'nt' and arquivo.stat().st_mode & 0o077:
            raise ValueError('Certificado/chave devem ter permissão 0600 ou mais restrita.')
    cifrado = cifrar_credencial(dados,empresa,chave_mestra(), f'credencial:{ambiente}')
    with repo.transacao() as c:
        repo.exigir_empresa(c,empresa,usuario['username'])
        repo.executar(c,'SELECT conta FROM inter_contas WHERE empresa_id=%s AND ambiente=%s',(empresa,ambiente))
        if c.fetchone():
            # Rotação somente sem operações pendentes; impede aprovação para uma conta e envio por outra.
            repo.executar(c, "SELECT id FROM inter_operacoes WHERE empresa_id=%s AND ambiente=%s AND estado NOT IN ('LIQUIDADA','RECUSADA')",(empresa,ambiente))
            if c.fetchone():
                raise ValueError('Conclua/reconcilie as operações antes de rotacionar a configuração bancária.')
            repo.executar(c,'UPDATE inter_contas SET conta=%s, credencial_secret=%s WHERE empresa_id=%s AND ambiente=%s',
                          (dados['conta'],cifrado,empresa,ambiente))
        else:
            repo.executar(c,'INSERT INTO inter_contas (empresa_id,ambiente,conta,credencial_secret) VALUES (%s,%s,%s,%s)',
                          (empresa,ambiente,dados['conta'],cifrado))
        repo.registrar(c,empresa,ambiente,usuario['username'],'CONFIGURACAO_CERTIFICADO')


def _proteger_pasta_certificados(pasta):
    """Restringe antes de gravar qualquer chave. Falha fechada se não houver ACL."""
    if os.name == 'nt':
        import csv
        import subprocess
        flags = subprocess.CREATE_NO_WINDOW
        identidade = subprocess.run(['whoami', '/user', '/fo', 'csv', '/nh'],
            capture_output=True, text=True, check=True, creationflags=flags, timeout=10)
        sid = next(csv.reader([identidade.stdout.strip()]))[-1]
        if not re.fullmatch(r'S-1-[0-9-]+', sid):
            raise ValueError('Não foi possível proteger os certificados para a conta do serviço.')
        subprocess.run(['icacls', str(pasta), '/inheritance:r', '/grant:r', f'*{sid}:(OI)(CI)F'],
            capture_output=True, check=True, creationflags=flags, timeout=10)
    else:
        pasta.chmod(0o700)


def salvar_credencial_upload(repo, empresa, usuario, dados, certificado, chave, *, ambiente='sandbox'):
    """Recebe .crt/.key pelo site; não autentica nem chama o banco.

    Nomes enviados pelo navegador nunca viram caminhos locais. Uma pasta nova
    de acesso restrito é usada por versão, sem sobrescrever certificados prévios.
    """
    if (not usuario.get('autenticado') or usuario.get('tipo_login') == 'cliente'
            or not usuario_tem_permissao('inter.configurar', usuario)):
        raise PermissionError('Sem permissão para configurar integração.')
    with repo.transacao() as c:
        repo.exigir_empresa(c, empresa, usuario['username'])
    chave_mestra()  # Validar configuração antes de persistir arquivos.
    validar_par_certificado(certificado, chave)
    diretorio = config_val('DSYSTEM_INTER_CERT_DIR', '')
    if not diretorio and os.name == 'nt':
        from .inter_pendente import pasta_local
        diretorio = str(pasta_local() / 'certificados')
    if not diretorio or not Path(diretorio).is_absolute():
        raise ValueError('O administrador deve configurar DSYSTEM_INTER_CERT_DIR fora do projeto.')
    raiz = Path(diretorio).resolve(strict=True)
    if not raiz.is_dir() or raiz.is_relative_to(Path(__file__).resolve().parents[2]):
        raise ValueError('Diretório de certificados deve existir fora do projeto.')
    import tempfile
    import shutil
    pasta = Path(tempfile.mkdtemp(prefix=f'inter-{int(empresa)}-', dir=raiz))
    try:
        _proteger_pasta_certificados(pasta)
        caminhos = {}
        for nome, conteudo in (('certificado', certificado), ('chave', chave)):
            arquivo = pasta / (nome+'.pem')
            fd = os.open(arquivo, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'wb') as saida:
                saida.write(conteudo)
            caminhos[nome] = str(arquivo)
        salvar_credencial(repo, empresa, usuario, {**dados, **caminhos}, ambiente=ambiente)
    except Exception:
        # Somente a pasta criada nesta chamada; nunca o diretório configurado.
        if pasta.parent == raiz and pasta.name.startswith(f'inter-{int(empresa)}-'):
            shutil.rmtree(pasta)
        raise
    return True


def validar_par_certificado(certificado, chave):
    """Validação local reutilizável, sem persistência e sem rede."""
    if any(not isinstance(b, bytes) or not 1 <= len(b) <= 131072 for b in (certificado, chave)):
        raise ValueError('Envie certificado e chave PEM de até 128 KB cada.')
    from cryptography import x509
    from cryptography.hazmat.primitives import serialization
    from datetime import datetime, timezone
    try:
        cert = x509.load_pem_x509_certificate(certificado)
        privada = serialization.load_pem_private_key(chave, password=None)
        pub = lambda k: k.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
        if pub(cert.public_key()) != pub(privada.public_key()):
            raise ValueError
        agora = datetime.now(timezone.utc)
        if not cert.not_valid_before_utc <= agora <= cert.not_valid_after_utc:
            raise ValueError
    except (ValueError, TypeError):
        raise ValueError('Certificado/chave PEM inválidos, divergentes, vencidos ou protegidos por senha.') from None
    return cert.not_valid_after_utc.date().isoformat()


def ler_zip_certificado(conteudo):
    """Lê em memória; nunca extrai caminhos ou executa conteúdo do ZIP."""
    from io import BytesIO
    from zipfile import ZipFile, BadZipFile
    if not isinstance(conteudo, bytes) or not 1 <= len(conteudo) <= 524288:
        raise ValueError('Envie o ZIP do Inter de até 512 KB.')
    try:
        with ZipFile(BytesIO(conteudo)) as z:
            arquivos = [i for i in z.infolist() if not i.is_dir()]
            if len(arquivos) != 2 or any(i.file_size > 131072 or i.flag_bits & 1 for i in arquivos):
                raise ValueError
            certificados = [i for i in arquivos if Path(i.filename).suffix.lower() in ('.crt', '.cer', '.pem')]
            chaves = [i for i in arquivos if Path(i.filename).suffix.lower() == '.key']
            if len(certificados) != 1 or len(chaves) != 1:
                raise ValueError
            cert, chave = z.read(certificados[0]), z.read(chaves[0])
    except (BadZipFile, ValueError, RuntimeError, NotImplementedError, OSError):
        raise ValueError('O ZIP deve conter somente um certificado e uma chave .key, sem senha, até 128 KB cada.') from None
    validar_par_certificado(cert, chave)
    return cert, chave


def status_configuracao(repo, empresa, usuario, *, ambiente='sandbox'):
    if (not usuario.get('autenticado') or usuario.get('tipo_login') == 'cliente'
            or not usuario_tem_permissao('inter.configurar', usuario)):
        raise PermissionError('Sem permissão para consultar configuração.')
    with repo.transacao() as c:
        repo.exigir_empresa(c, empresa, usuario['username'])
        repo.executar(c, 'SELECT conta FROM inter_contas WHERE empresa_id=%s AND ambiente=%s', (empresa, ambiente))
        row = c.fetchone()
    return {'configurada': bool(row), 'conta_final': str(row['conta'])[-4:] if row else ''}


def abrir_sandbox(repo, empresa, usuario):
    if config_val('DSYSTEM_INTER_ALLOW_SANDBOX', '') != '1':
        raise PermissionError('Rede sandbox desabilitada; use primeiro a simulação.')
    if not usuario.get('autenticado') or not usuario_tem_permissao('inter.view',usuario):
        raise PermissionError('Sem acesso bancário.')
    with repo.transacao() as c:
        repo.exigir_empresa(c,empresa,usuario['username'])
        repo.executar(c,'SELECT credencial_secret FROM inter_contas WHERE empresa_id=%s AND ambiente=%s',(empresa,'sandbox'))
        row = c.fetchone()
    if not row:
        raise ValueError('Nenhuma credencial sandbox configurada para esta empresa.')
    chave = chave_mestra()
    dados = decifrar_credencial(row['credencial_secret'],empresa,chave)
    dados['escopos'] = frozenset(dados['escopos'])
    credencial = CredencialInter(empresa_id=empresa, **dados)
    return FinanceiroInter(repo,ClienteInter(credencial,permitir_sandbox=True),chave,ambiente='sandbox')


def abrir_producao_movimentacao(repo, empresa, usuario):
    if not movimentacao_producao_liberada():
        raise PermissionError('Movimentação em produção desabilitada. Defina DSYSTEM_INTER_PERMITIR_MOVIMENTACAO=1.')
    if not usuario.get('autenticado') or not usuario_tem_permissao('inter.view', usuario):
        raise PermissionError('Sem acesso bancário.')
    with repo.transacao() as c:
        repo.exigir_empresa(c, empresa, usuario['username'])
        repo.executar(c, 'SELECT credencial_secret FROM inter_contas WHERE empresa_id=%s AND ambiente=%s', (empresa, 'producao'))
        row = c.fetchone()
    if not row:
        raise ValueError('Cadastre as credenciais de produção desta empresa em Configurar chaves.')
    chave = chave_mestra()
    dados = decifrar_credencial(row['credencial_secret'], empresa, chave, 'credencial:producao')
    dados['escopos'] = frozenset(dados['escopos'])
    if 'boleto-cobranca.write' not in dados['escopos'] and 'pagamento-boleto.write' not in dados['escopos'] and 'pagamento-pix.write' not in dados['escopos']:
        raise ValueError('As chaves de produção desta empresa ainda estão só para consulta. Recadastre com os escopos de cobrança/pagamento.')
    credencial = CredencialInter(empresa_id=empresa, ambiente='producao', **dados)
    return FinanceiroInter(repo, ClienteInter(credencial, permitir_producao_movimentacao=True), chave, ambiente='producao')


def abrir_servico_operacoes(usuario, sessao=None):
    """Abre simulação da sessão, sandbox ou produção com movimentação."""
    demo = (sessao or {}).get('_inter_demo')
    if demo and demo.get('usuario') == usuario.get('username') and demo.get('servico'):
        empresas = demo['servico'].repo.empresas(usuario['username'])
        if empresas:
            return empresas[0]['id'], demo['servico']
    if movimentacao_producao_liberada():
        repo = repositorio_configuracao()
        empresas = repo.empresas(usuario['username'])
        if not empresas:
            raise ValueError('Seu login não tem empresa bancária vinculada.')
        return empresas[0]['id'], abrir_producao_movimentacao(repo, empresas[0]['id'], usuario)
    if config_val('DSYSTEM_INTER_ALLOW_SANDBOX', '') == '1':
        repo = repositorio_teste()
        empresas = repo.empresas(usuario['username'])
        if not empresas:
            raise ValueError('Seu login não tem empresa bancária vinculada.')
        return empresas[0]['id'], abrir_sandbox(repo, empresas[0]['id'], usuario)
    raise ValueError(
        'Abra Banco Inter em Simulação, habilite o sandbox ou defina DSYSTEM_INTER_PERMITIR_MOVIMENTACAO=1.'
    )


class ConsultasInterProducao:
    """Não fornece preparar/aprovar/executar, conciliar nem alterar títulos."""
    def __init__(self, repo):
        self.repo = repo
        self._clientes = {}

    def consultar(self, empresa, usuario, operacao, *, params=None):
        if (not usuario.get('autenticado') or usuario.get('tipo_login') == 'cliente'
                or not usuario_tem_permissao('inter.view', usuario)):
            raise PermissionError('Sem acesso bancário.')
        if operacao not in CONSULTAS_PRODUCAO:
            raise PermissionError('Produção permite somente saldo e extrato. Movimentações bloqueadas.')
        with self.repo.transacao() as c:
            self.repo.exigir_empresa(c, empresa, usuario['username'])
            self.repo.executar(c, 'SELECT credencial_secret FROM inter_contas WHERE empresa_id=%s AND ambiente=%s', (empresa, 'producao'))
            row = c.fetchone()
            if not row:
                raise ValueError('Cadastre as credenciais de produção desta empresa em Configurar chaves.')
            self.repo.registrar(c, empresa, 'producao', usuario['username'], 'CONSULTA_' + operacao.upper())
        import hashlib
        versao = hashlib.sha256(row['credencial_secret'].encode()).hexdigest()
        atual = self._clientes.get(empresa)
        if not atual or atual[0] != versao:
            dados = decifrar_credencial(row['credencial_secret'], empresa, chave_mestra(), 'credencial:producao')
            dados['escopos'] = frozenset(dados['escopos'])
            cliente = ClienteInter(CredencialInter(empresa_id=empresa, ambiente='producao', **dados), permitir_producao_consulta=True)
            if atual:
                atual[1].session.close()
            self._clientes[empresa] = (versao, cliente)
        return self._clientes[empresa][1].chamar(operacao, empresa_id=empresa, params=params)

    def fechar(self):
        for _, cliente in self._clientes.values():
            cliente.session.close()
        self._clientes.clear()
