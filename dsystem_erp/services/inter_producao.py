"""Operações reais com revisão humana; importar/renderizar nunca envia ao Inter.

Lê o financeiro existente, mas mantém o ledger e as autorizações na base Inter.
Não presume liquidação nem altera o status dos títulos do ERP.
"""
from datetime import datetime
from decimal import Decimal
from hashlib import sha256
import re
from zoneinfo import ZoneInfo

from lxml import etree

from .inter_financeiro import FinanceiroInter, dinheiro, validar_payload
from .inter_painel import carregar_usuario
from .permissions import usuario_tem_permissao
from .faturamento_parcelas import gerar_parcelas_faturamento
from .inter_titulos import data_iso
from .impostos_notas import extrair_nota


def hoje():
    return datetime.now(ZoneInfo('America/Sao_Paulo')).date()


def digitos(valor):
    return re.sub(r'\D', '', str(valor or ''))


def conectar_erp():
    import mysql.connector
    from dsystem_erp.config import config_val
    from dsystem_erp.db import mysql_connection_config
    return mysql.connector.connect(**mysql_connection_config(config_val('MYSQL_DATABASE', 'banco_dsystem')))


class OrigemFaturamento:
    def __init__(self, conectar=None):
        self.conectar = conectar or conectar_erp

    def carregar(self, faturamento_id, cnpj_empresa):
        conn = self.conectar()
        try:
            c = conn.cursor(dictionary=True)
            c.execute('SELECT * FROM faturamento WHERE id=%s', (int(faturamento_id),))
            fat = dict(c.fetchone() or {})
            if fat.get('status') != 'Faturado' or 'boleto' not in str(fat.get('forma_pag') or '').casefold():
                raise ValueError('Selecione um faturamento concluído com forma de pagamento Boleto.')
            doc = digitos(fat.get('cnpj'))
            if len(doc) not in (11, 14):
                raise ValueError('CPF/CNPJ do faturamento inválido.')
            c.execute('SELECT * FROM notas_fiscais WHERE faturamento_id=%s', (fat['id'],))
            notas = [dict(r) for r in c.fetchall()]
            canceladas = {n.get('chave_acesso') for n in notas if n.get('status') == 'Cancelada'}
            conferidas = {}
            for n in notas:
                if n.get('status') != 'Autorizada':
                    continue
                fiscal = extrair_nota(n, cnpj_empresa)
                if not fiscal or fiscal['chave'] in canceladas:
                    raise ValueError('Nota cancelada ou emitida por outra empresa/ambiente.')
                root = etree.fromstring(n['xml_autorizado'].encode() if isinstance(n['xml_autorizado'], str)
                                        else n['xml_autorizado'], etree.XMLParser(resolve_entities=False, no_network=True))
                ns = {'n': 'http://www.portalfiscal.inf.br/nfe' if n['tipo_nota'] == 'Produto'
                      else 'http://www.sped.fazenda.gov.br/nfse'}
                base = './/n:dest/' if n['tipo_nota'] == 'Produto' else './/n:toma/'
                destinatario = root.findtext(base+'n:CNPJ', namespaces=ns) or root.findtext(base+'n:CPF', namespaces=ns)
                if destinatario != doc:
                    raise ValueError('Destinatário da nota difere do faturamento.')
                fiscal['referencia'] = None
                if n['tipo_nota'] == 'Produto':
                    fiscal['referencia'] = {
                        'chaveNFe': fiscal['chave'],
                        'numero': int(root.findtext('.//n:ide/n:nNF', namespaces=ns)),
                        'serie': int(root.findtext('.//n:ide/n:serie', namespaces=ns)),
                        'dataEmissao': fiscal['competencia'].isoformat(),
                    }
                conferidas[fiscal['chave']] = fiscal
            if not conferidas or sum((n['total'] for n in conferidas.values()), Decimal(0)) != Decimal(dinheiro(fat['valor_total'])):
                raise ValueError('Notas autorizadas de produção precisam corresponder ao total do faturamento.')
            # Identidade fiscal, nunca busca por nome: não confundir clientes homônimos.
            c.execute("SELECT * FROM clientes WHERE REPLACE(REPLACE(REPLACE(COALESCE(cnpj,''),'.',''),'/',''),'-','')=%s OR documento_chave=%s", (doc, doc))
            clientes = [dict(r) for r in c.fetchall()]
            if len(clientes) != 1:
                raise ValueError('Localize um único cadastro do cliente pelo CPF/CNPJ antes de gerar o boleto.')
            cliente = clientes[0]
            if doc not in {digitos(cliente.get('cnpj')), digitos(cliente.get('documento_chave'))}:
                raise ValueError('Cadastro do cliente divergente.')
            uf = str(cliente.get('uf') or '').strip().upper()
            cidade = str(cliente.get('cidade_estado') or '').strip()
            cidade = re.sub(r'\s*[-/]\s*'+re.escape(uf)+r'$', '', cidade, flags=re.I) if uf else cidade
            pagador = dict(cpfCnpj=doc, tipoPessoa='JURIDICA' if len(doc) == 14 else 'FISICA',
                           nome=cliente.get('nome'), endereco=cliente.get('endereco'),
                           numero=str(cliente.get('numero') or ''), bairro=cliente.get('bairro'),
                           cidade=cidade, uf=uf, cep=digitos(cliente.get('cep')))
            limites = {'nome':100, 'endereco':100, 'bairro':60, 'cidade':60, 'numero':10}
            if any(not pagador.get(k) or len(str(pagador[k])) > lim for k, lim in limites.items() if k != 'numero') or len(pagador['numero']) > 10 or not re.fullmatch(r'[A-Z]{2}', uf) or len(pagador['cep']) != 8:
                raise ValueError('Complete nome e endereço válido do cliente (cidade, UF, CEP e número).')
            resultado = []
            for parcela in gerar_parcelas_faturamento(fat):
                c.execute('SELECT * FROM contas_receber WHERE numero_documento=%s', (parcela['documento'],))
                linhas = [dict(r) for r in c.fetchall()]
                if len(linhas) != 1:
                    raise ValueError('Parcela ausente ou duplicada no Contas a Receber: '+parcela['documento'])
                t = linhas[0]
                if (digitos(t.get('cpf_cnpj')) != doc or dinheiro(t['valor_total']) != dinheiro(parcela['valor'])
                        or 'boleto' not in str(t.get('forma_recebimento') or '').casefold()):
                    raise ValueError('Parcela divergente do faturamento. Revise o Contas a Receber.')
                if (t.get('status') not in ('Aberto', 'Pendente', 'Vencido', 'Em aberto')
                        or Decimal(str(t.get('valor_baixado') or 0)) != 0
                        or str(t.get('conciliado')).casefold() in ('sim', '1', 'true')):
                    continue
                payload = dict(seuNumero='CR'+str(t['id']), valorNominal=float(dinheiro(t['valor_total'])),
                               dataVencimento=data_iso(t.get('vencimento')), numDiasAgenda=30,
                               pagador=pagador, formasRecebimento=['BOLETO', 'PIX'])
                if len(conferidas) == 1 and next(iter(conferidas.values()))['referencia']:
                    payload['notaFiscal'] = dict(next(iter(conferidas.values()))['referencia'], parcela=parcela['numero'])
                validar_payload('boleto_emitir', payload)
                origem = dict(faturamento_id=fat['id'], titulo_id=t['id'], documento=parcela['documento'],
                              notas=sorted(conferidas), cliente_id=cliente['id'])
                resultado.append(dict(payload=payload, origem=origem, rotulo=parcela['rotulo']))
            return resultado
        finally:
            conn.close()


class ProducaoInter(FinanceiroInter):
    def __init__(self, repo, cliente, chave, *, carregar=None, origem=None):
        self.carregar_usuario = carregar or carregar_usuario
        self.origem = origem or OrigemFaturamento()
        super().__init__(repo, cliente, chave, ambiente='producao', politica_producao=self._politica)

    def _autorizar(self, c, empresa, usuario, acao):
        if not usuario.get('autenticado') or usuario.get('tipo_login') == 'cliente':
            raise PermissionError('Acesso interno autenticado obrigatório.')
        atual = self.carregar_usuario(usuario.get('username'))
        super()._autorizar(c, empresa, atual, acao)
        if not usuario_tem_permissao('inter.view', atual):
            raise PermissionError('Acesso bancário revogado.')

    def _credencial(self, c, empresa):
        self.repo.executar(c, "SELECT credencial_secret FROM inter_contas WHERE empresa_id=%s AND ambiente='producao'"+('' if self.repo.sqlite else ' FOR UPDATE'), (empresa,))
        r = c.fetchone()
        if not r:
            raise ValueError('Credencial de produção ausente.')
        return sha256(r['credencial_secret'].encode()).hexdigest()

    def _politica(self, c, empresa, usuario, registro, pacote, etapa):
        from .inter_runtime import movimentacao_producao_liberada
        if not movimentacao_producao_liberada(self.repo, empresa, cursor=c):
            raise PermissionError('Movimentações desativadas para esta empresa.')
        if int(empresa) != self.cliente.credencial.empresa_id:
            raise PermissionError('Conta bancária pertence a outra empresa.')
        ctx = pacote.get('contexto') or {}
        versao = self._credencial(c, empresa)
        if ctx.get('credencial') != versao or versao != getattr(self, 'credencial_digest', None):
            raise PermissionError('Configuração bancária mudou. Reabra a tela e revise a operação.')
        tipo, p = registro['tipo'], pacote['payload']
        if tipo not in ('boleto_emitir', 'pix_enviar', 'conta_pagar'):
            raise PermissionError('Modalidade não habilitada para produção.')
        from .inter_api import OPERACOES
        if OPERACOES[tipo][2] not in self.cliente.credencial.escopos:
            raise PermissionError('Habilite o escopo desta operação nas chaves da empresa.')
        if etapa in ('aprovar', 'executar'):
            self._autorizar(c, empresa, dict(usuario, username=registro['criado_por']), 'preparar')
        if etapa == 'executar':
            self._autorizar(c, empresa, dict(usuario, username=registro['aprovado_por']), 'aprovar')
        if tipo == 'boleto_emitir':
            origem = ctx.get('origem') or {}
            if registro['chave'] != 'titulo:contas_receber:'+str(origem.get('titulo_id')):
                raise ValueError('Cobrança deve estar vinculada à parcela da nota.')
            self.repo.executar(c, 'SELECT cnpj FROM inter_empresas WHERE id=%s', (empresa,))
            cadastro = c.fetchone()
            atuais = self.origem.carregar(origem.get('faturamento_id'), cadastro['cnpj'])
            if not any(i['origem'] == origem and i['payload'] == p for i in atuais):
                raise ValueError('Nota, cliente ou parcela mudou após a preparação. Envio bloqueado.')
            if data_iso(p['dataVencimento']) < hoje().isoformat():
                raise ValueError('Boleto vencido: ajuste o vencimento no Contas a Receber antes de preparar.')
            # Uma mesma parcela não pode ser emitida através de outra empresa bancária.
            self.repo.executar(c, "SELECT id FROM inter_operacoes WHERE ambiente='producao' AND chave=%s AND empresa_id<>%s", (registro['chave'], empresa))
            if c.fetchone():
                raise ValueError('Parcela já vinculada a outra empresa bancária.')
        else:
            favorecido = ctx.get('favorecido') or {}
            if not str(favorecido.get('nome') or '').strip() or len(digitos(favorecido.get('documento'))) not in (11, 14):
                raise ValueError('Informe nome e CPF/CNPJ do favorecido para revisão.')
            if not registro['chave'].startswith('pagamento:'):
                raise ValueError('Referência estável do pagamento obrigatória.')
            if not p.get('dataPagamento') or p['dataPagamento'] < hoje().isoformat():
                raise ValueError('Revise a data de pagamento; não pode estar no passado.')
            if tipo == 'conta_pagar' and p.get('cpfCnpjBeneficiario') != digitos(favorecido['documento']):
                raise ValueError('CPF/CNPJ do beneficiário divergente.')
            if etapa == 'criar':
                # Mesma transação do INSERT: duas sessões não passam juntas na verificação.
                self.repo.executar(c, 'SELECT id FROM inter_empresas WHERE id=%s'+('' if self.repo.sqlite else ' FOR UPDATE'), (empresa,))
                c.fetchone()
                self.repo.executar(c, "SELECT * FROM inter_operacoes WHERE empresa_id=%s AND ambiente='producao' AND tipo=%s", (empresa, tipo))
                for r in c.fetchall():
                    anterior = self._ler(empresa, dict(r))
                    if anterior['payload'] == p and r['chave'] != registro['chave']:
                        raise ValueError('Pagamento idêntico já preparado. Consulte o histórico; não troque a referência.')

    def _contexto(self, empresa, usuario, **dados):
        with self.repo.transacao() as c:
            self._autorizar(c, empresa, usuario, 'preparar')
            return dict(credencial=self._credencial(c, empresa), **dados)

    def parcelas(self, empresa, usuario, faturamento_id):
        with self.repo.transacao() as c:
            self._autorizar(c, empresa, usuario, 'preparar')
            self.repo.executar(c, 'SELECT cnpj FROM inter_empresas WHERE id=%s', (empresa,))
            cadastro = c.fetchone()
        return self.origem.carregar(faturamento_id, cadastro['cnpj'])

    def preparar_parcela(self, empresa, usuario, faturamento_id, titulo_id):
        linhas = self.parcelas(empresa, usuario, faturamento_id)
        linha = next((i for i in linhas if i['origem']['titulo_id'] == int(titulo_id)), None)
        if not linha:
            raise ValueError('Parcela não disponível.')
        return self.criar(empresa, usuario, 'boleto_emitir', linha['payload'],
                          'titulo:contas_receber:'+str(titulo_id),
                          contexto=self._contexto(empresa, usuario, origem=linha['origem']))

    def preparar_pagamento(self, empresa, usuario, tipo, payload, referencia, nome, documento):
        if tipo not in ('pix_enviar', 'conta_pagar'):
            raise ValueError('Selecione Pix ou boleto/conta.')
        referencia = str(referencia).strip().casefold()
        if not re.fullmatch(r'[a-z0-9:._-]{1,100}', referencia):
            raise ValueError('Referência obrigatória: letras, números, ponto, dois-pontos, hífen ou sublinhado.')
        contexto = self._contexto(empresa, usuario, favorecido=dict(nome=nome.strip(), documento=digitos(documento)))
        return self.criar(empresa, usuario, tipo, payload, 'pagamento:'+referencia, contexto=contexto)

    def listar(self, empresa, usuario):
        with self.repo.transacao() as c:
            self._autorizar(c, empresa, usuario, 'view')
        return self.repo.listar(empresa, self.ambiente, usuario['username'])

    def consultar(self, empresa, usuario, operacao, *, identificador=None, params=None):
        # Consulta de documentos somente de operações desta empresa, não IDs arbitrários da tela.
        if operacao in ('boleto_pdf', 'boleto_consultar', 'pix_consultar', 'conta_consultar'):
            tipo = {'boleto_pdf':'boleto_emitir', 'boleto_consultar':'boleto_emitir',
                    'pix_consultar':'pix_enviar', 'conta_consultar':'conta_pagar'}[operacao]
            with self.repo.transacao() as c:
                self._autorizar(c, empresa, usuario, 'view')
                self.repo.executar(c, "SELECT id FROM inter_operacoes WHERE empresa_id=%s AND ambiente='producao' AND tipo=%s AND externo=%s", (empresa, tipo, identificador))
                if not identificador or not c.fetchone():
                    raise PermissionError('Documento não vinculado a uma operação desta empresa.')
            if operacao == 'conta_consultar':
                params = {'codigoTransacao': identificador}
        return super().consultar(empresa, usuario, operacao, identificador=identificador, params=params)
