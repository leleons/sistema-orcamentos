"""Delegação de consultas por empresa; usa as permissões já existentes do ERP."""
from .permissions import usuario_tem_permissao


def _autorizar(repo, empresa, usuario):
    if (not usuario.get('autenticado') or usuario.get('tipo_login') == 'cliente'
            or str(usuario.get('is_admin', 0)).lower() not in ('1', 'true')
            or not usuario_tem_permissao('inter.configurar', usuario)):
        raise PermissionError('Somente administrador autorizado pode delegar acesso bancário.')
    with repo.transacao() as c:
        repo.exigir_empresa(c, empresa, usuario['username'])


def listar_acessos(repo, empresa, usuario, conectar_erp):
    _autorizar(repo, empresa, usuario)
    conn = conectar_erp()
    try:
        cur = conn.cursor()
        cur.execute('SELECT username,submodulos FROM usuarios ORDER BY username')
        elegiveis = [r['username'] for r in cur.fetchall() if usuario_tem_permissao('inter.view', dict(r))]
    finally:
        conn.close()
    with repo.transacao() as c:
        repo.executar(c, 'SELECT usuario FROM inter_acessos WHERE empresa_id=%s', (empresa,))
        atuais = [r['usuario'] for r in c.fetchall()]
    return elegiveis, atuais


def salvar_acessos(repo, empresa, usuario, conectar_erp, logins):
    elegiveis, atuais = listar_acessos(repo, empresa, usuario, conectar_erp)
    if not isinstance(logins, (list, tuple)) or any(not isinstance(v, str) for v in logins):
        raise ValueError('Selecione os logins autorizados.')
    desejados = set(logins) | {usuario['username']}
    if not desejados <= set(elegiveis):
        raise ValueError('Habilite Consultar banco no cadastro de usuários antes de vincular a esta empresa.')
    with repo.transacao() as c:
        repo.exigir_empresa(c, empresa, usuario['username'])
        # Releitura na transação: a lista da tela não é a fonte de autorização.
        repo.executar(c, 'SELECT usuario FROM inter_acessos WHERE empresa_id=%s', (empresa,))
        atuais = {r['usuario'] for r in c.fetchall()}
        for login in desejados - atuais:
            repo.executar(c, 'INSERT INTO inter_acessos (empresa_id,usuario) VALUES (%s,%s)', (empresa, login))
        for login in atuais - desejados:
            repo.executar(c, 'DELETE FROM inter_acessos WHERE empresa_id=%s AND usuario=%s', (empresa, login))
        repo.registrar(c, empresa, 'producao', usuario['username'], 'ACESSOS_CONSULTA_ATUALIZADOS')
    return True
