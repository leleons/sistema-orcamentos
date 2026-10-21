"""Adaptador oficial Inter. Produção limitada a saldo/extrato, sem movimentação.

Fontes: developers.inter.co/redocusaurus/swagger-*-yaml.yaml (15/10/2026).
Sem retries em escrita; respostas 202 não significam pagamento liquidado.
"""
from __future__ import annotations

import base64
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote

import requests
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import os

SANDBOX = 'https://cdpj-sandbox.partners.uatinter.co'
PRODUCAO = 'https://cdpj.partners.bancointer.com.br'
CONSULTAS_PRODUCAO = frozenset({'saldo', 'extrato', 'extrato_pdf'})
# método, caminho, escopo OAuth. A conta é sempre fixa na credencial da empresa.
OPERACOES = {
    'saldo': ('GET', '/banking/v2/saldo', 'extrato.read'),
    'extrato': ('GET', '/banking/v2/extrato/completo', 'extrato.read'),
    'extrato_pdf': ('GET', '/banking/v2/extrato/exportar', 'extrato.read'),
    'boleto_emitir': ('POST', '/cobranca/v3/cobrancas', 'boleto-cobranca.write'),
    'boleto_consultar': ('GET', '/cobranca/v3/cobrancas/{id}', 'boleto-cobranca.read'),
    'boleto_pdf': ('GET', '/cobranca/v3/cobrancas/{id}/pdf', 'boleto-cobranca.read'),
    'boleto_cancelar': ('POST', '/cobranca/v3/cobrancas/{id}/cancelar', 'boleto-cobranca.write'),
    'pix_receber': ('PUT', '/pix/v2/cob/{id}', 'cob.write'),
    'pix_cob_consultar': ('GET', '/pix/v2/cob/{id}', 'cob.read'),
    'pix_recebidos': ('GET', '/pix/v2/pix', 'pix.read'),
    'pix_recebido': ('GET', '/pix/v2/pix/{id}', 'pix.read'),
    'pix_enviar': ('POST', '/banking/v2/pix', 'pagamento-pix.write'),
    'pix_consultar': ('GET', '/banking/v2/pix/{id}', 'pagamento-pix.read'),
    'conta_pagar': ('POST', '/banking/v2/pagamento', 'pagamento-boleto.write'),
    'conta_consultar': ('GET', '/banking/v2/pagamento', 'pagamento-boleto.read'),
    'conta_cancelar': ('DELETE', '/banking/v2/pagamento/{id}', 'pagamento-boleto.write'),
    'lote_boletos': ('POST', '/banking/v2/pagamento/lote', 'pagamento-lote.write'),
    'lote_consultar': ('GET', '/banking/v2/pagamento/lote/{id}', 'pagamento-lote.read'),
    'rec_criar': ('POST', '/pix/v2/rec', 'rec.write'),
    'rec_consultar': ('GET', '/pix/v2/rec/{id}', 'rec.read'),
    'rec_cancelar': ('PATCH', '/pix/v2/rec/{id}', 'rec.write'),
    'rec_solicitar': ('POST', '/pix/v2/solicrec', 'solicrec.write'),
    'rec_solicitacao': ('GET', '/pix/v2/solicrec/{id}', 'solicrec.read'),
    'rec_cobrar': ('PUT', '/pix/v2/cobr/{id}', 'cobr.write'),
    'rec_cobranca': ('GET', '/pix/v2/cobr/{id}', 'cobr.read'),
    'rec_location': ('POST', '/pix/v2/locrec', 'payloadlocationrec.write'),
}


class InterErro(RuntimeError):
    def __init__(self, codigo, incerto=False):
        super().__init__(codigo)
        self.codigo, self.incerto = codigo, incerto


@dataclass(frozen=True)
class CredencialInter:
    empresa_id: int
    conta: str
    client_id: str = field(repr=False)
    client_secret: str = field(repr=False)
    certificado: str = field(repr=False)
    chave: str = field(repr=False)
    escopos: frozenset[str]
    ambiente: str = 'sandbox'


def cifrar_credencial(dados, empresa_id, chave_mestra, contexto='credencial:sandbox'):
    """AES-GCM com vínculo autenticado à empresa. Chave mestra fora do banco."""
    nonce = os.urandom(12)
    aad = f'inter:{int(empresa_id)}:{contexto}'.encode()
    return base64.b64encode(nonce + AESGCM(chave_mestra).encrypt(nonce, json.dumps(dados).encode(), aad)).decode()


def decifrar_credencial(texto, empresa_id, chave_mestra, contexto='credencial:sandbox'):
    try:
        bruto = base64.b64decode(texto, validate=True)
        return json.loads(AESGCM(chave_mestra).decrypt(bruto[:12], bruto[12:], f'inter:{int(empresa_id)}:{contexto}'.encode()))
    except Exception:
        raise InterErro('CREDENCIAL_INVALIDA_OU_EMPRESA_DIVERGENTE') from None


class ClienteInter:
    def __init__(self, credencial, *, permitir_sandbox=False, permitir_producao_consulta=False,
                 permitir_producao_movimentacao=False, session=None, clock=time.monotonic):
        self._producao_consulta = credencial.ambiente == 'producao' and permitir_producao_consulta is True
        self._producao_movimentacao = credencial.ambiente == 'producao' and permitir_producao_movimentacao is True
        if not self._producao_consulta and not self._producao_movimentacao and not (credencial.ambiente == 'sandbox' and permitir_sandbox):
            raise InterErro('REDE_BLOQUEADA: habilite explicitamente o ambiente correto')
        if not isinstance(credencial.conta, str) or (credencial.conta and not re.fullmatch(r'[1-9][0-9]*', credencial.conta)):
            raise ValueError('Conta deve conter somente números, sem zeros iniciais.')
        self._base_url = PRODUCAO if (self._producao_consulta or self._producao_movimentacao) else SANDBOX
        for arquivo in (credencial.certificado, credencial.chave):
            if not Path(arquivo).is_file():
                raise InterErro('CERTIFICADO_OU_CHAVE_AUSENTE')
        self.credencial, self.clock = credencial, clock
        self.session = session or requests.Session()
        self.session.trust_env = False  # não enviar segredos por proxy herdado
        self._token, self._expira, self._scope = None, 0, None

    def _http(self, metodo, caminho, **kwargs):
        if self._producao_consulta and not self._producao_movimentacao:
            consulta = metodo == 'GET' and caminho in {OPERACOES[o][1] for o in CONSULTAS_PRODUCAO}
            token = (metodo == 'POST' and caminho == '/oauth/v2/token'
                     and kwargs.get('data', {}).get('scope') == 'extrato.read')
            if not (consulta or token):
                raise PermissionError('Produção permite somente saldo e extrato. Movimentações bloqueadas.')
        try:
            resposta = self.session.request(metodo, self._base_url + caminho,
                cert=(self.credencial.certificado, self.credencial.chave), verify=True,
                timeout=(5, 30), allow_redirects=False, **kwargs)
        except requests.RequestException:
            raise InterErro('CONEXAO_INCERTA_CONSULTE_STATUS', incerto=metodo != 'GET') from None
        if not 200 <= resposta.status_code < 300:
            # Nunca retornar corpo do banco/token/CPF para logs genéricos do ERP.
            raise InterErro(f'INTER_HTTP_{resposta.status_code}', incerto=metodo != 'GET' and resposta.status_code >= 500)
        try:
            return resposta.json() if resposta.content else {}
        except ValueError:
            raise InterErro('RESPOSTA_INVALIDA', incerto=metodo != 'GET') from None

    def chamar(self, operacao, *, empresa_id, identificador=None, payload=None, params=None, idempotencia=None):
        if int(empresa_id) != self.credencial.empresa_id:
            raise PermissionError('Empresa não corresponde à credencial.')
        if self._producao_consulta and not self._producao_movimentacao and operacao not in CONSULTAS_PRODUCAO:
            raise PermissionError('Produção permite somente saldo e extrato. Movimentações bloqueadas.')
        metodo, caminho, scope = OPERACOES[operacao]
        if scope not in self.credencial.escopos:
            raise PermissionError('Escopo não habilitado: ' + scope)
        if '{id}' in caminho:
            if not identificador or not re.fullmatch(r'[A-Za-z0-9-]{1,80}', str(identificador)):
                raise ValueError('Identificador inválido.')
            caminho = caminho.replace('{id}', quote(str(identificador), safe=''))
        if metodo != 'GET' and not idempotencia:
            raise ValueError('Escrita exige identificador local idempotente.')
        if not self._token or self._expira <= self.clock() or self._scope != scope:
            token = self._http('POST', '/oauth/v2/token', data={
                'client_id': self.credencial.client_id, 'client_secret': self.credencial.client_secret,
                'scope': scope, 'grant_type': 'client_credentials'})
            if not isinstance(token, dict) or not isinstance(token.get('access_token'), str) or not token['access_token']:
                raise InterErro('TOKEN_INVALIDO')
            self._token, self._scope = token['access_token'], scope
            self._expira = self.clock() + max(0, int(token.get('expires_in', 0)) - 60)
        headers = {'Authorization': 'Bearer ' + self._token}
        # Oficial: obrigatório somente para integrações associadas a múltiplas contas.
        if self.credencial.conta:
            headers['x-conta-corrente'] = self.credencial.conta
        if operacao == 'pix_enviar':
            import uuid
            headers['x-id-idempotente'] = str(uuid.UUID(idempotencia))
        # Outros endpoints não anunciam este header: a proteção fica no ledger local.
        return self._http(metodo, caminho, headers=headers, json=payload, params=params)


def pdf_da_resposta(resposta):
    try:
        dados = base64.b64decode(resposta.get('pdf') or resposta.get('arquivo') or '', validate=True)
    except (ValueError, TypeError, AttributeError):
        raise InterErro('PDF_AINDA_INDISPONIVEL') from None
    if not dados.startswith(b'%PDF-'):
        raise InterErro('PDF_AINDA_INDISPONIVEL')
    return dados


class InterSimulado:
    """Sem rede. Valores fictícios e liquidação explícita, nunca presumida."""
    def __init__(self):
        self.chamadas = []
        self.resultados = {}

    def chamar(self, operacao, *, empresa_id, identificador=None, payload=None, params=None, idempotencia=None):
        import uuid
        self.chamadas.append((empresa_id, operacao, idempotencia))
        if operacao == 'saldo':
            return {'disponivel': 10000.00, 'simulado': True}
        if operacao == 'extrato':
            return {'transacoes': [], 'totalPaginas': 1, 'simulado': True}
        if operacao == 'boleto_pdf':
            pdf = b'%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<>\n%%EOF'
            return {'pdf': base64.b64encode(pdf).decode(), 'simulado': True}
        if OPERACOES[operacao][0] == 'GET':
            return self.resultados.get((empresa_id, identificador), {'status': 'EM_PROCESSAMENTO', 'simulado': True})
        codigo = identificador or str(uuid.uuid5(uuid.NAMESPACE_URL, f'{empresa_id}:{idempotencia}'))
        return {'codigoSolicitacao': codigo, 'txid': codigo, 'idRec': codigo,
                'status': 'EM_PROCESSAMENTO', 'simulado': True}
