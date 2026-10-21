"""Reutiliza cadastros/títulos existentes, exclusivamente na base de homologação."""
from datetime import date, datetime
import re

from dsystem_erp.services.inter_financeiro import dinheiro
from dsystem_erp.services.inter_conciliacao import vincular_titulo


def data_iso(valor):
    texto = str(valor or '').strip()
    for formato in ('%Y-%m-%d', '%d/%m/%Y'):
        try:
            return datetime.strptime(texto, formato).date().isoformat()
        except ValueError:
            pass
    raise ValueError('Data do título inválida; corrija o cadastro de teste.')


def listar_titulos(servico, empresa, usuario, tabela):
    if tabela not in ('contas_pagar', 'contas_receber') or not servico.repo.financeiro_teste:
        raise PermissionError('Somente títulos financeiros da base de testes.')
    repo = servico.repo
    with repo.transacao() as c:
        servico._autorizar(c, empresa, usuario, 'preparar')
        repo.executar(c, f'''SELECT t.* FROM {tabela} t JOIN inter_titulos_empresas e
            ON e.titulo_id=t.id AND e.tabela=%s WHERE e.empresa_id=%s
            AND t.status NOT IN ('Pago','Recebido','Cancelado','Baixado por perda')
            AND COALESCE(CAST(t.valor_baixado AS DECIMAL(14,2)),0)=0 ORDER BY t.id DESC LIMIT 200''', (tabela, empresa))
        return [dict(r) for r in c.fetchall()]


def dados_do_titulo(servico, empresa, usuario, tabela, titulo_id, modalidade, pagamento=None):
    titulos = listar_titulos(servico, empresa, usuario, tabela)
    titulo = next((t for t in titulos if t['id'] == titulo_id), None)
    if not titulo:
        raise PermissionError('Título não autorizado ou encerrado.')
    valor = dinheiro(titulo['valor_total'])
    if tabela == 'contas_pagar':
        dia = data_iso(pagamento or date.today())
        if modalidade == 'pix_enviar':
            payload = {'valor': float(valor), 'dataPagamento': dia,
                       'destinatario': {'tipo': 'CHAVE', 'chave': titulo.get('chave_pix') or ''}}
        elif modalidade == 'conta_pagar':
            payload = {'valorPagar': valor, 'dataPagamento': dia,
                       'dataVencimento': data_iso(titulo.get('data_vencimento')),
                       'codBarraLinhaDigitavel': re.sub(r'\D', '', titulo.get('codigo_barras') or '')}
        else:
            raise ValueError('Modalidade incompatível com contas a pagar.')
    elif modalidade == 'boleto_emitir':
        with servico.repo.transacao() as c:
            servico._autorizar(c, empresa, usuario, 'preparar')
            servico.repo.executar(c, 'SELECT * FROM clientes WHERE id=%s', (titulo.get('cliente_id'),))
            cliente = dict(c.fetchone() or {})
        documento = re.sub(r'\D', '', cliente.get('cnpj') or titulo.get('cpf_cnpj') or '')
        if len(documento) not in (11, 14):
            raise ValueError('CPF/CNPJ do cliente ausente ou inválido no cadastro de teste.')
        cidade = str(cliente.get('cidade_estado') or '').strip()
        uf = str(cliente.get('uf') or '').strip().upper()
        if uf and cidade.upper().endswith('/'+uf):
            cidade = cidade[:-3].strip()
        pagador = {'cpfCnpj': documento, 'tipoPessoa': 'JURIDICA' if len(documento)==14 else 'FISICA',
                   'nome': cliente.get('nome'), 'endereco': ', '.join(str(cliente.get(k) or '') for k in ('endereco','numero')).strip(', '),
                   'bairro': cliente.get('bairro'), 'cidade': cidade, 'uf': uf,
                   'cep': re.sub(r'\D', '', cliente.get('cep') or '')}
        payload = {'seuNumero': str(titulo_id), 'valorNominal': float(valor),
                   'dataVencimento': data_iso(titulo.get('data_vencimento')), 'numDiasAgenda': 30,
                   'pagador': pagador, 'formasRecebimento': ['BOLETO', 'PIX']}
    else:
        raise ValueError('Modalidade incompatível com contas a receber.')
    from dsystem_erp.services.inter_financeiro import validar_payload
    validar_payload(modalidade, payload)
    return payload


def preparar_titulo(servico, empresa, usuario, tabela, titulo_id, modalidade, pagamento=None):
    payload = dados_do_titulo(servico, empresa, usuario, tabela, titulo_id, modalidade, pagamento)
    uid = servico.criar(empresa, usuario, modalidade, payload, f'titulo:{tabela}:{titulo_id}')
    with servico.repo.transacao() as c:
        servico._autorizar(c, empresa, usuario, 'conciliar')
        servico.repo.executar(c, '''SELECT operacao_id FROM inter_vinculos_financeiros
            WHERE empresa_id=%s AND ambiente=%s AND operacao_id=%s''', (empresa, servico.ambiente, uid))
        existente = c.fetchone()
    if not existente:
        vincular_titulo(servico, empresa, usuario, uid, titulo_id)
    return uid


def validar_vinculo_envio(servico, cursor, empresa, uid):
    """Impede enviar título que foi pago/alterado após a preparação."""
    repo = servico.repo
    repo.executar(cursor, '''SELECT v.* FROM inter_vinculos_financeiros v
        WHERE empresa_id=%s AND ambiente=%s AND operacao_id=%s''', (empresa, servico.ambiente, uid))
    v = cursor.fetchone()
    if not v:
        return
    tabela = v['tabela']
    if tabela not in ('contas_pagar', 'contas_receber'):
        raise ValueError('Vínculo financeiro inválido.')
    repo.executar(cursor, f'''SELECT t.* FROM {tabela} t JOIN inter_titulos_empresas e
        ON e.titulo_id=t.id AND e.tabela=%s WHERE t.id=%s AND e.empresa_id=%s'''
        + ('' if repo.sqlite else ' FOR UPDATE'), (tabela, v['titulo_id'], empresa))
    t = dict(cursor.fetchone() or {})
    if (not t or t.get('status') in ('Pago','Recebido','Cancelado','Baixado por perda')
            or float(t.get('valor_baixado') or 0) != 0
            or str(t.get('conciliado')).casefold() in ('sim','1','true')
            or dinheiro(t['valor_total']) != dinheiro(v['valor'])):
        raise ValueError('Título alterado após preparação. Não será enviado; revise o financeiro.')
