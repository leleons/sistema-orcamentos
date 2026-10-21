"""Saldo/extrato de produção: consultas apenas, snapshot cifrado e agenda 08/12 BRT.

O agendador e a tela compartilham uma trava por empresa. Sem alterações no
financeiro do ERP, sem chamadas de pagamento e sem guardar respostas em logs.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from uuid import uuid4
from zoneinfo import ZoneInfo

from .inter_api import InterErro, cifrar_credencial, decifrar_credencial
from .permissions import usuario_tem_permissao

BRASILIA = ZoneInfo('America/Sao_Paulo')
CONTEXTO = 'painel:producao:v1'
MAX_PAGINAS = 25
TAMANHO_PAGINA = 1000


def agora_utc():
    return datetime.now(timezone.utc)


def slot_atual(agora):
    local = agora.astimezone(BRASILIA)
    if local.hour < 8:
        return None
    return local.strftime('%Y-%m-%d') + ('T12:00' if local.hour >= 12 else 'T08:00')


def proxima_atualizacao(agora):
    local = agora.astimezone(BRASILIA)
    for hora in (8, 12):
        candidato = local.replace(hour=hora, minute=0, second=0, microsecond=0)
        if candidato > local:
            return candidato
    return (local + timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0)


def carregar_usuario(username, conectar_erp=None):
    """Relê autorização atual, inclusive após revogação; nunca cria banco/tabelas."""
    if conectar_erp is None:
        import mysql.connector
        from dsystem_erp.config import config_val
        from dsystem_erp.db import mysql_connection_config
        conectar_erp = lambda: mysql.connector.connect(**mysql_connection_config(
            config_val('MYSQL_DATABASE', 'banco_dsystem')))
    conn = conectar_erp()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute('SELECT username,is_admin,submodulos FROM usuarios WHERE username=%s', (username,))
        row = cur.fetchone()
        cur.close()
    finally:
        conn.close()
    if not row:
        raise PermissionError('Usuário bancário não está mais cadastrado.')
    return {**dict(row), 'autenticado': True, 'tipo_login': 'interno'}


def decimal_api(valor):
    try:
        if isinstance(valor, bool) or valor is None:
            raise ValueError
        numero = Decimal(str(valor))
        if not numero.is_finite() or numero != numero.quantize(Decimal('0.01')):
            raise ValueError
        return numero
    except (InvalidOperation, ValueError, TypeError):
        raise InterErro('RESPOSTA_BANCARIA_INVALIDA') from None


def reais(valor):
    return 'R$ ' + f'{decimal_api(valor):,.2f}'.replace(',', '_').replace('.', ',').replace('_', '.')


def normalizar_transacao(item):
    if not isinstance(item, dict) or item.get('tipoOperacao') not in ('C', 'D'):
        raise InterErro('EXTRATO_INCOMPLETO_OU_INVALIDO')
    try:
        data = datetime.fromisoformat(str(item['dataTransacao']).replace('Z', '+00:00')).date().isoformat()
    except (ValueError, KeyError):
        raise InterErro('EXTRATO_INCOMPLETO_OU_INVALIDO') from None
    return {
        'id': str(item.get('idTransacao') or ''), 'data': data,
        'direcao': 'Entrada' if item['tipoOperacao'] == 'C' else 'Saída',
        'valor': str(abs(decimal_api(item.get('valor')))),
        'tipo': str(item.get('tipoTransacao') or 'OUTROS').replace('_', ' ').title(),
        'descricao': str(item.get('descricao') or item.get('titulo') or 'Sem descrição'),
    }


class PainelInter:
    def __init__(self, repo, consultas, *, obter_usuario=carregar_usuario, chave=None, clock=agora_utc):
        if chave is None:
            from .inter_runtime import chave_mestra
            chave = chave_mestra
        self.repo, self.consultas = repo, consultas
        self.obter_usuario, self.chave, self.clock = obter_usuario, chave, clock

    def _usuario(self, usuario):
        if not usuario.get('autenticado') or usuario.get('tipo_login') == 'cliente':
            raise PermissionError('Sem acesso bancário.')
        atual = self.obter_usuario(usuario.get('username', ''))
        if not atual.get('autenticado') or atual.get('tipo_login') == 'cliente' or not usuario_tem_permissao('inter.view', atual):
            raise PermissionError('Acesso bancário revogado ou não autorizado.')
        return atual

    def _credencial(self, c, empresa, usuario, *, obrigatoria=True):
        self.repo.exigir_empresa(c, empresa, usuario['username'])
        self.repo.executar(c, 'SELECT credencial_secret FROM inter_contas WHERE empresa_id=%s AND ambiente=%s', (empresa, 'producao'))
        row = c.fetchone()
        if not row:
            if obrigatoria:
                raise ValueError('Cadastre as credenciais de produção em Configurar conta real.')
            return None
        return sha256(row['credencial_secret'].encode()).hexdigest()

    def _registro(self, c, empresa):
        self.repo.executar(c, 'SELECT * FROM inter_painel WHERE empresa_id=%s', (empresa,))
        row = c.fetchone()
        return dict(row) if row else {}

    def _agenda(self, c, empresa):
        self.repo.executar(c, 'SELECT * FROM inter_painel_agenda WHERE empresa_id=%s', (empresa,))
        row = c.fetchone()
        return dict(row) if row else {}

    def ler(self, empresa, usuario):
        usuario = self._usuario(usuario)
        with self.repo.transacao() as c:
            versao = self._credencial(c, empresa, usuario, obrigatoria=False)
            registro = self._registro(c, empresa)
            agenda = self._agenda(c, empresa)
        dados = None
        if registro.get('snapshot_secret') and registro['credencial_digest'] == versao:
            dados = decifrar_credencial(registro['snapshot_secret'], empresa, self.chave(), CONTEXTO)
        return {'dados': dados, 'erro': registro.get('erro'), 'tentativa_em': registro.get('tentativa_em'),
                'agenda_ativa': bool(agenda.get('ativo')), 'atualizado_em': registro.get('atualizado_em') if dados else None}

    def configurar_agenda(self, empresa, usuario, *, ativo):
        usuario = self._usuario(usuario)
        if str(usuario.get('is_admin', 0)).lower() not in ('1', 'true') or not usuario_tem_permissao('inter.configurar', usuario):
            raise PermissionError('Somente administrador autorizado pode configurar a agenda bancária.')
        with self.repo.transacao() as c:
            self._credencial(c, empresa, usuario)
            self.repo.executar(c, 'DELETE FROM inter_painel_agenda WHERE empresa_id=%s', (empresa,))
            self.repo.executar(c, '''INSERT INTO inter_painel_agenda (empresa_id,usuario,ativo,configurado_em)
                VALUES (%s,%s,%s,%s)''', (empresa, usuario['username'], int(ativo), self.clock().isoformat()))
            self.repo.registrar(c, empresa, 'producao', usuario['username'], 'PAINEL_AGENDA_ATIVADA' if ativo else 'PAINEL_AGENDA_DESATIVADA')

    def atualizar(self, empresa, usuario, *, agendado=False):
        usuario = self._usuario(usuario)
        agora = self.clock().astimezone(timezone.utc)
        slot = slot_atual(agora) if agendado else None
        token = str(uuid4())
        with self.repo.transacao() as c:
            # Serializa criação e aquisição da trava inclusive no primeiro acesso.
            sql = 'SELECT id FROM inter_empresas WHERE id=%s' + ('' if self.repo.sqlite else ' FOR UPDATE')
            self.repo.executar(c, sql, (empresa,))
            c.fetchone()
            versao = self._credencial(c, empresa, usuario)
            registro = self._registro(c, empresa)
            if agendado:
                agenda = self._agenda(c, empresa)
                if not agenda.get('ativo') or agenda['usuario'] != usuario['username']:
                    raise PermissionError('Agenda não autorizada para este usuário/empresa.')
                if not slot or registro.get('ultimo_slot') == slot:
                    return 'ja_verificado'
            if registro.get('lock_ate') and registro['lock_ate'] > agora.isoformat():
                return 'em_andamento'
            if not registro:
                self.repo.executar(c, 'INSERT INTO inter_painel (empresa_id) VALUES (%s)', (empresa,))
            self.repo.executar(c, '''UPDATE inter_painel SET lock_token=%s,lock_ate=%s,tentativa_em=%s,
                ultimo_slot=%s WHERE empresa_id=%s''',
                (token, (agora + timedelta(minutes=20)).isoformat(), agora.isoformat(), slot or registro.get('ultimo_slot'), empresa))
        try:
            chave = self.chave()  # Falhar antes da rede se o cofre estiver indisponível.
            hoje = agora.astimezone(BRASILIA).date()
            inicio = hoje - timedelta(days=29)
            saldo = self.consultas.consultar(empresa, usuario, 'saldo')
            if not isinstance(saldo, dict):
                raise InterErro('RESPOSTA_BANCARIA_INVALIDA')
            disponivel = str(decimal_api(saldo.get('disponivel')))
            transacoes, ids, paginas, total = [], set(), None, None
            for pagina in range(MAX_PAGINAS):
                # Não continuar paginação se houver revogação no ERP.
                usuario = self._usuario(usuario)
                resposta = self.consultas.consultar(empresa, usuario, 'extrato', params={
                    'dataInicio': inicio.isoformat(), 'dataFim': hoje.isoformat(),
                    'pagina': pagina, 'tamanhoPagina': TAMANHO_PAGINA})
                if not isinstance(resposta, dict) or not isinstance(resposta.get('transacoes'), list):
                    raise InterErro('EXTRATO_INCOMPLETO_OU_INVALIDO')
                qtd = resposta.get('totalPaginas')
                quantidade = resposta.get('totalElementos')
                if type(qtd) is not int or not 0 <= qtd <= MAX_PAGINAS:
                    raise InterErro('EXTRATO_INCOMPLETO_OU_INVALIDO')
                if pagina == 0:
                    paginas, total = qtd, quantidade
                if qtd != paginas or quantidade != total or (total is not None and (type(total) is not int or total < 0)):
                    raise InterErro('EXTRATO_ALTERADO_DURANTE_CONSULTA')
                for item in resposta['transacoes']:
                    linha = normalizar_transacao(item)
                    if not inicio.isoformat() <= linha['data'] <= hoje.isoformat() or (linha['id'] and linha['id'] in ids):
                        raise InterErro('EXTRATO_ALTERADO_DURANTE_CONSULTA')
                    ids.add(linha['id'])
                    transacoes.append(linha)
                if pagina + 1 >= paginas:
                    break
            if (total is not None and len(transacoes) != total) or (paginas == 0 and transacoes):
                raise InterErro('EXTRATO_INCOMPLETO_OU_INVALIDO')
            concluido = self.clock().astimezone(timezone.utc).isoformat()
            dados = {'saldo': disponivel, 'referencia_saldo': saldo.get('dataReferencia'),
                     'inicio': inicio.isoformat(), 'fim': hoje.isoformat(), 'atualizado_em': concluido,
                     'transacoes': sorted(transacoes, key=lambda t: t['data'], reverse=True)}
            cifrado = cifrar_credencial(dados, empresa, chave, CONTEXTO)
            usuario = self._usuario(usuario)
            with self.repo.transacao() as c:
                if self._credencial(c, empresa, usuario) != versao:
                    raise InterErro('CONFIGURACAO_ALTERADA_ATUALIZE_NOVAMENTE')
                if self._registro(c, empresa).get('lock_token') != token:
                    raise InterErro('ATUALIZACAO_SUBSTITUIDA')
                self.repo.executar(c, '''UPDATE inter_painel SET snapshot_secret=%s,credencial_digest=%s,
                    atualizado_em=%s,erro=NULL,lock_token=NULL,lock_ate=NULL WHERE empresa_id=%s AND lock_token=%s''',
                    (cifrado, versao, concluido, empresa, token))
                self.repo.registrar(c, empresa, 'producao', usuario['username'], 'PAINEL_ATUALIZADO_AUTO' if agendado else 'PAINEL_ATUALIZADO_MANUAL')
            return 'atualizado'
        except Exception:
            with self.repo.transacao() as c:
                self.repo.executar(c, '''UPDATE inter_painel SET erro=%s,lock_token=NULL,lock_ate=NULL
                    WHERE empresa_id=%s AND lock_token=%s''', ('FALHA_NA_ATUALIZACAO', empresa, token))
            # Não expor resposta bancária, SQL, credenciais ou erro bruto.
            raise InterErro('Não foi possível atualizar. A última consulta completa foi preservada. Verifique conexão, permissões e certificados e tente novamente.') from None
