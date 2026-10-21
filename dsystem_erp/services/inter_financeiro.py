"""Orquestração bancária com aprovação, idempotência e isolamento por empresa.

Não executa tarefas ao importar; rede de produção não é suportada nesta versão.
"""
from __future__ import annotations
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re
from uuid import uuid4

from dsystem_erp.services.permissions import usuario_tem_permissao
from dsystem_erp.services.inter_api import (
    OPERACOES, ClienteInter, InterSimulado, InterErro, cifrar_credencial, decifrar_credencial,
)

DEBITOS = frozenset({'pix_enviar', 'conta_pagar', 'lote_boletos', 'conta_cancelar'})
CONSULTAS = {
    'boleto_emitir': 'boleto_consultar', 'pix_receber': 'pix_cob_consultar',
    'pix_enviar': 'pix_consultar', 'conta_pagar': 'conta_consultar',
    'lote_boletos': 'lote_consultar', 'rec_criar': 'rec_consultar',
    'rec_cobrar': 'rec_cobranca', 'rec_solicitar': 'rec_solicitacao',
}


def dinheiro(valor):
    try:
        numero = Decimal(str(valor))
        if not numero.is_finite() or numero <= 0 or numero != numero.quantize(Decimal('0.01')):
            raise ValueError
        return format(numero, '.2f')
    except (InvalidOperation, ValueError):
        raise ValueError('Valor deve ser positivo, finito e ter no máximo duas casas decimais.') from None


def digest_conteudo(tipo, payload, identificador):
    return hashlib.sha256(json.dumps([tipo, payload, identificador], sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def validar_payload(tipo, payload, identificador=None):
    if tipo not in OPERACOES or OPERACOES[tipo][0] == 'GET' or not isinstance(payload, dict):
        raise ValueError('Operação de escrita inválida.')
    if '{id}' in OPERACOES[tipo][1] and not identificador:
        raise ValueError('Identificador obrigatório.')
    for campo in ('dataPagamento', 'dataVencimento'):
        if campo in payload:
            dia = date.fromisoformat(payload[campo])
            if campo == 'dataPagamento' and dia < date.today():
                raise ValueError('Data de pagamento no passado.')
    if tipo == 'pix_enviar':
        dinheiro(payload.get('valor'))
        dest = payload.get('destinatario') or {}
        if dest.get('tipo') != 'CHAVE' or not str(dest.get('chave') or '').strip():
            raise ValueError('Nesta versão, envio Pix exige destinatário do tipo CHAVE.')
    elif tipo == 'conta_pagar':
        dinheiro(payload.get('valorPagar'))
        if not re.fullmatch(r'\d{44}|\d{47}|\d{48}', str(payload.get('codBarraLinhaDigitavel') or '')):
            raise ValueError('Código de barras/linha digitável inválido.')
        date.fromisoformat(payload.get('dataVencimento', ''))
    elif tipo == 'boleto_emitir':
        if Decimal(dinheiro(payload.get('valorNominal'))) < Decimal('2.50'):
            raise ValueError('Cobrança Inter exige valor mínimo de R$ 2,50.')
        if not 1 <= len(str(payload.get('seuNumero') or '')) <= 15:
            raise ValueError('Seu número é obrigatório, com até 15 caracteres.')
        date.fromisoformat(payload.get('dataVencimento', ''))
        if not isinstance(payload.get('numDiasAgenda'), int) or not 0 <= payload['numDiasAgenda'] <= 60:
            raise ValueError('Dias de agenda: 0 a 60.')
        pagador = payload.get('pagador') or {}
        if any(not pagador.get(k) for k in ('cpfCnpj', 'tipoPessoa', 'nome', 'endereco', 'bairro', 'cidade', 'uf', 'cep')):
            raise ValueError('Complete os dados cadastrais do pagador.')
        if payload.get('formasRecebimento') != ['BOLETO', 'PIX']:
            raise ValueError('Cobrança desta integração utiliza BOLETO e PIX.')
    elif tipo == 'pix_receber':
        dinheiro((payload.get('valor') or {}).get('original'))
        if not payload.get('chave') or not re.fullmatch(r'[A-Za-z0-9]{26,35}', str(identificador)):
            raise ValueError('Chave recebedora e txid de 26 a 35 caracteres obrigatórios.')
    elif tipo == 'lote_boletos':
        if not 1 <= len(str(payload.get('meuIdentificador') or '')) <= 30:
            raise ValueError('Identificador do lote obrigatório (até 30 caracteres).')
        itens = payload.get('pagamentos') or []
        if not 2 <= len(itens) <= 150:
            raise ValueError('Lote bancário exige de 2 a 150 boletos. Pix usa lote interno.')
        for item in itens:
            if item.get('tipoPagamento') != 'BOLETO':
                raise ValueError('Este fluxo aceita somente boletos no lote bancário.')
            validar_payload('conta_pagar', item)
    elif tipo == 'rec_criar':
        if not payload.get('vinculo') or not payload.get('calendario') or not payload.get('valor'):
            raise ValueError('Informe vínculo, calendário e valor da recorrência.')
        date.fromisoformat(payload['calendario'].get('dataInicial', ''))
        if payload['calendario'].get('periodicidade') not in ('SEMANAL', 'MENSAL', 'TRIMESTRAL', 'SEMESTRAL', 'ANUAL'):
            raise ValueError('Periodicidade inválida.')
    elif tipo == 'rec_cobrar':
        if not payload.get('idRec') or not payload.get('recebedor'):
            raise ValueError('Recorrência autorizada e recebedor obrigatórios.')
        dinheiro((payload.get('valor') or {}).get('original'))
        date.fromisoformat((payload.get('calendario') or {}).get('dataDeVencimento', ''))
        if not re.fullmatch(r'[A-Za-z0-9]{26,35}', str(identificador)):
            raise ValueError('txid inválido.')
    elif tipo == 'rec_cancelar':
        if payload != {'status': 'CANCELADA'}:
            raise ValueError('Cancelamento exige status CANCELADA.')
    elif tipo == 'rec_solicitar':
        if not payload.get('idRec') or not payload.get('calendario') or not payload.get('destinatario'):
            raise ValueError('Solicitação exige idRec, calendário e destinatário.')


class FinanceiroInter:
    def __init__(self, repo, cliente, chave_mestra, *, ambiente='simulacao'):
        if ambiente not in ('simulacao', 'sandbox', 'producao'):
            raise ValueError('Ambiente bancário inválido.')
        if ambiente == 'simulacao' and not isinstance(cliente, InterSimulado):
            raise ValueError('Transporte incompatível com o ambiente.')
        if ambiente == 'sandbox' and (not isinstance(cliente, ClienteInter) or getattr(cliente, '_producao_movimentacao', False)):
            raise ValueError('Sandbox exige adaptador mTLS.')
        if ambiente == 'producao' and not getattr(cliente, '_producao_movimentacao', False):
            raise ValueError('Cobrança e pagamentos em produção exigem opt-in explícito.')
        if ambiente != 'simulacao' and isinstance(cliente, InterSimulado):
            raise ValueError('Transporte incompatível com o ambiente.')
        self.repo, self.cliente, self.chave, self.ambiente = repo, cliente, chave_mestra, ambiente

    def _autorizar(self, c, empresa, usuario, acao):
        if (not usuario.get('autenticado') or usuario.get('tipo_login') == 'cliente'
                or not usuario.get('username') or not usuario_tem_permissao('inter.' + acao, usuario)):
            raise PermissionError('Permissão bancária explícita necessária: inter.' + acao)
        self.repo.exigir_empresa(c, empresa, usuario['username'])

    def _cifrar(self, empresa, dados, identificador, campo):
        return cifrar_credencial(dados, empresa, self.chave, f'{self.ambiente}:{identificador}:{campo}')

    def _ler(self, empresa, registro, campo='payload'):
        return decifrar_credencial(registro[campo + '_secret'], empresa, self.chave,
                                  f'{self.ambiente}:{registro["id"]}:{campo}')

    def criar(self, empresa, usuario, tipo, payload, chave, identificador=None):
        validar_payload(tipo, payload, identificador)
        if not re.fullmatch(r'[A-Za-z0-9:._-]{1,120}', chave):
            raise ValueError('Informe uma referência única e estável do lançamento/competência.')
        digest = digest_conteudo(tipo, payload, identificador)
        with self.repo.transacao() as c:
            self._autorizar(c, empresa, usuario, 'preparar')
            self.repo.executar(c, 'SELECT id,digest FROM inter_operacoes WHERE empresa_id=%s AND ambiente=%s AND chave=%s',
                              (empresa, self.ambiente, chave))
            anterior = c.fetchone()
            if anterior:
                if anterior['digest'] != digest:
                    raise ValueError('Referência já usada com dados diferentes. Não será reenviada.')
                return anterior['id']
            uid = str(uuid4())
            pacote = {'payload': payload, 'identificador': identificador}
            self.repo.executar(c, '''INSERT INTO inter_operacoes
                (id,empresa_id,ambiente,chave,tipo,payload_secret,digest,estado,criado_por,criado_em)
                VALUES (%s,%s,%s,%s,%s,%s,%s,'PENDENTE_APROVACAO',%s,%s)''',
                (uid, empresa, self.ambiente, chave, tipo, self._cifrar(empresa,pacote,uid,'payload'),
                 digest, usuario['username'], datetime.now(timezone.utc).isoformat()))
            self.repo.registrar(c, empresa, self.ambiente, usuario['username'], 'PREPARADA', uid)
            return uid

    def localizar(self, empresa, usuario, chave):
        with self.repo.transacao() as c:
            self._autorizar(c, empresa, usuario, 'view')
            self.repo.executar(c, '''SELECT id,tipo,estado,externo,criado_por,aprovado_por
                FROM inter_operacoes WHERE empresa_id=%s AND ambiente=%s AND chave=%s''',
                              (empresa, self.ambiente, chave))
            row = c.fetchone()
            return dict(row) if row else None

    def detalhes(self, empresa, usuario, uid):
        with self.repo.transacao() as c:
            self._autorizar(c, empresa, usuario, 'view')
            registro = self.repo.operacao(c, empresa, self.ambiente, uid)
            dados = self._ler(empresa, registro)
            dados.update({k: registro[k] for k in ('id','tipo','digest','estado','criado_por','aprovado_por','externo','erro')})
            if registro.get('resposta_secret'):
                dados['resposta'] = self._ler(empresa, registro, 'resposta')
            return dados

    def aprovar(self, empresa, usuario, uid, digest, confirmacao):
        with self.repo.transacao() as c:
            self._autorizar(c, empresa, usuario, 'aprovar')
            r = self.repo.operacao(c, empresa, self.ambiente, uid, travar=True)
            if r['estado'] != 'PENDENTE_APROVACAO' or digest != r['digest'] or confirmacao != 'CONFIRMAR ' + uid:
                raise ValueError('Confirme exatamente a operação revisada; dados ou status divergentes.')
            if r['tipo'] in DEBITOS and r['criado_por'].casefold() == usuario['username'].casefold():
                raise PermissionError('Pagamentos exigem aprovação de outra pessoa autorizada.')
            self.repo.executar(c, 'UPDATE inter_operacoes SET estado=%s, aprovado_por=%s WHERE id=%s AND empresa_id=%s AND ambiente=%s',
                ('APROVADA', usuario['username'], uid, empresa, self.ambiente))
            self.repo.registrar(c, empresa, self.ambiente, usuario['username'], 'APROVADA', uid)

    def executar(self, empresa, usuario, uid):
        with self.repo.transacao() as c:
            self._autorizar(c, empresa, usuario, 'executar')
            r = self.repo.operacao(c, empresa, self.ambiente, uid, travar=True)
            if r['estado'] != 'APROVADA':
                raise ValueError('Operação não aprovada ou já enviada. Consulte o status; não repita.')
            pacote = self._ler(empresa,r)
            if digest_conteudo(r['tipo'], pacote['payload'], pacote['identificador']) != r['digest']:
                raise ValueError('Dados modificados após aprovação.')
            from dsystem_erp.services.inter_titulos import validar_vinculo_envio
            validar_vinculo_envio(self, c, empresa, uid)
            self.repo.executar(c, 'UPDATE inter_operacoes SET estado=%s WHERE id=%s AND empresa_id=%s AND ambiente=%s',
                              ('ENVIO_INICIADO', uid, empresa, self.ambiente))
            self.repo.registrar(c, empresa,self.ambiente,usuario['username'],'ENVIO_INICIADO',uid)
        try:
            if r['tipo'] == 'rec_cobrar':
                rec = self.cliente.chamar('rec_consultar', empresa_id=empresa, identificador=pacote['payload']['idRec'])
                if rec.get('status') != 'APROVADA':
                    raise InterErro('RECORRENCIA_SEM_AUTORIZACAO')
            resposta = self.cliente.chamar(r['tipo'], empresa_id=empresa, payload=pacote['payload'],
                identificador=pacote['identificador'], idempotencia=uid)
            externo = resposta.get('codigoSolicitacao') or resposta.get('codigoTransacao') or resposta.get('idLote') or resposta.get('idRec') or resposta.get('idSolicRec') or resposta.get('txid') or resposta.get('id') or pacote['identificador']
            externo = str(externo) if externo is not None else None
            estado, erro = ('ENVIADA', None) if externo else ('INCERTA', 'RESPOSTA_SEM_IDENTIFICADOR')
        except Exception as exc:
            # Sem retry, inclusive quando o processo perdeu o resultado do banco.
            resposta, externo = {}, None
            estado = 'RECUSADA' if isinstance(exc, InterErro) and not exc.incerto else 'INCERTA'
            erro = exc.codigo if isinstance(exc, InterErro) else 'FALHA_ENVIO_CONSULTE_STATUS'
        with self.repo.transacao() as c:
            self.repo.executar(c, '''UPDATE inter_operacoes SET estado=%s, externo=%s, erro=%s, resposta_secret=%s
                WHERE id=%s AND empresa_id=%s AND ambiente=%s''',
                (estado, externo, erro, self._cifrar(empresa,resposta,uid,'resposta'),uid,empresa,self.ambiente))
            self.repo.registrar(c,empresa,self.ambiente,usuario['username'],estado,uid)
        return estado

    def consultar(self, empresa, usuario, operacao, *, identificador=None, params=None):
        if operacao not in OPERACOES or OPERACOES[operacao][0] != 'GET':
            raise ValueError('Somente consultas neste método.')
        with self.repo.transacao() as c:
            self._autorizar(c,empresa,usuario,'view')
        return self.cliente.chamar(operacao,empresa_id=empresa,identificador=identificador,params=params)

    def atualizar(self, empresa, usuario, uid):
        r = self.detalhes(empresa,usuario,uid)
        if not r['externo'] or r['tipo'] not in CONSULTAS:
            raise ValueError('Sem identificador consultável. Conferir no banco; reenvio bloqueado.')
        params = {'codigoTransacao': r['externo']} if r['tipo'] == 'conta_pagar' else None
        resposta = self.consultar(empresa,usuario,CONSULTAS[r['tipo']],identificador=r['externo'],params=params)
        with self.repo.transacao() as c:
            self._autorizar(c,empresa,usuario,'view')
            self.repo.executar(c, 'UPDATE inter_operacoes SET resposta_secret=%s WHERE id=%s AND empresa_id=%s AND ambiente=%s',
                              (self._cifrar(empresa,resposta,uid,'resposta'),uid,empresa,self.ambiente))
            self.repo.registrar(c,empresa,self.ambiente,usuario['username'],'STATUS_CONSULTADO',uid)
        return resposta

    def criar_folha_pix(self, empresa, usuario, referencia, itens):
        """Lote interno: um registro/uma aprovação por favorecido, sem fingir lote Pix bancário."""
        if not 1 <= len(itens) <= 150 or len({i['funcionario_id'] for i in itens}) != len(itens):
            raise ValueError('Lote vazio, acima do limite ou com funcionário repetido.')
        for item in itens:
            validar_payload('pix_enviar',item['payload'])
        return [self.criar(empresa,usuario,'pix_enviar',item['payload'],f'folha:{referencia}:{item["funcionario_id"]}') for item in itens]

    def cobranca_mensal(self, empresa, usuario, contrato_id, competencia, payload):
        if not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])',competencia):
            raise ValueError('Competência deve ser AAAA-MM.')
        return self.criar(empresa,usuario,'boleto_emitir',payload,f'recorrente:{contrato_id}:{competencia}')
