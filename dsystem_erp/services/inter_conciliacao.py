"""Baixa conservadora por consulta autenticada. Nunca confia em callback isolado.

Somente banco de teste explicitamente habilitado nesta fase; usa as tabelas e
proteções financeiras do ERP. Valores divergentes/parciais vão para revisão.
"""
from decimal import Decimal
from datetime import date
from dsystem_erp.services.inter_financeiro import dinheiro
from dsystem_erp.services.conciliacao import esta_baixado


def valor_operacao(detalhes):
    tipo, p = detalhes['tipo'], detalhes['payload']
    if tipo == 'boleto_emitir':
        return 'contas_receber', dinheiro(p['valorNominal'])
    if tipo in ('pix_receber', 'rec_cobrar'):
        return 'contas_receber', dinheiro(p['valor']['original'])
    if tipo == 'pix_enviar':
        return 'contas_pagar', dinheiro(p['valor'])
    if tipo == 'conta_pagar':
        return 'contas_pagar', dinheiro(p['valorPagar'])
    raise ValueError('Vincule cada item individualmente, não o lote agregado.')


def vincular_titulo(servico, empresa, usuario, uid, titulo_id):
    repo = servico.repo
    if not repo.financeiro_teste:
        raise PermissionError('Vínculo/baixa financeira liberados somente em base de testes identificada.')
    dados = servico.detalhes(empresa,usuario,uid)
    tabela, valor = valor_operacao(dados)
    with repo.transacao() as c:
        servico._autorizar(c,empresa,usuario,'conciliar')
        repo.executar(c, 'SELECT empresa_id FROM inter_titulos_empresas WHERE tabela=%s AND titulo_id=%s AND empresa_id=%s',
                      (tabela,titulo_id,empresa))
        if not c.fetchone():
            raise PermissionError('Título sem vínculo empresarial validado. Não inferir por nome ou cliente.')
        repo.executar(c,f'SELECT * FROM {tabela} WHERE id=%s' + ('' if repo.sqlite else ' FOR UPDATE'),(titulo_id,))
        titulo = c.fetchone()
        if not titulo or esta_baixado(dict(titulo)) or titulo['status'] in ('Cancelado','Baixado por perda'):
            raise ValueError('Título inexistente/encerrado.')
        if Decimal(str(titulo['valor_baixado'] or 0)) != 0 or Decimal(str(titulo['valor_total'])) != Decimal(valor):
            raise ValueError('Valor divergente ou título parcialmente baixado: revisão manual necessária.')
        repo.executar(c, '''INSERT INTO inter_vinculos_financeiros
            (empresa_id,ambiente,operacao_id,tabela,titulo_id,valor) VALUES (%s,%s,%s,%s,%s,%s)''',
            (empresa,servico.ambiente,uid,tabela,titulo_id,valor))
        repo.registrar(c,empresa,servico.ambiente,usuario['username'],'TITULO_VINCULADO',uid)


def liquidacao_confirmada(detalhes, resposta):
    """Retorna identidade + valor + data somente em estados finais documentados."""
    tipo, externo = detalhes['tipo'], detalhes['externo']
    if tipo == 'boleto_emitir':
        cob = resposta.get('cobranca') or {}
        if cob.get('situacao') == 'RECEBIDO' and cob.get('codigoSolicitacao') == externo:
            return 'boleto:' + externo, dinheiro(cob.get('valorTotalRecebido')), cob.get('dataSituacao')
    elif tipo == 'pix_enviar':
        pix = resposta.get('transacaoPix') or {}
        if pix.get('status') == 'EFETIVADO' and pix.get('codigoSolicitacao') == externo and pix.get('endToEnd'):
            return pix['endToEnd'], dinheiro(pix.get('valor')), pix.get('dataHoraMovimento')
    elif tipo == 'conta_pagar' and isinstance(resposta, list):
        pagamentos = [p for p in resposta if p.get('codigoTransacao') == externo]
        if len(pagamentos) == 1:
            p = pagamentos[0]
            if p.get('statusPagamento') == 'REALIZADO' and p.get('autenticacao'):
                return 'pagamento:' + externo, dinheiro(p.get('valorPago')), p.get('dataPagamento')
    elif tipo in ('pix_receber','rec_cobrar'):
        if resposta.get('status') == 'CONCLUIDA' and resposta.get('txid') == externo:
            recebidos = resposta.get('pix') or []
            if len(recebidos) == 1 and recebidos[0].get('endToEndId') and not recebidos[0].get('devolucoes'):
                p = recebidos[0]
                return p['endToEndId'], dinheiro(p.get('valor')), p.get('horario')
    return None


def conciliar_operacao(servico, empresa, usuario, uid):
    """Polling autenticado + transação única de ledger/baixa. Repetição é inócua."""
    repo = servico.repo
    if not repo.financeiro_teste:
        raise PermissionError('Baixa bloqueada fora da base financeira de teste.')
    with repo.transacao() as c:
        servico._autorizar(c,empresa,usuario,'conciliar')
    detalhes = servico.detalhes(empresa,usuario,uid)
    resposta = servico.atualizar(empresa,usuario,uid)
    resultado = liquidacao_confirmada(detalhes,resposta)
    if not resultado:
        return 'AGUARDANDO_LIQUIDACAO'
    evento, valor, quando = resultado
    data_baixa = date.fromisoformat(str(quando or '')[:10]).strftime('%d/%m/%Y')
    with repo.transacao() as c:
        servico._autorizar(c,empresa,usuario,'conciliar')
        repo.operacao(c,empresa,servico.ambiente,uid,travar=True)
        repo.executar(c,'SELECT evento_id FROM inter_liquidacoes WHERE empresa_id=%s AND ambiente=%s AND operacao_id=%s',
                      (empresa,servico.ambiente,uid))
        if c.fetchone():
            return 'JA_CONCILIADA'
        repo.executar(c,'SELECT * FROM inter_vinculos_financeiros WHERE empresa_id=%s AND ambiente=%s AND operacao_id=%s',
                      (empresa,servico.ambiente,uid))
        vinculo = c.fetchone()
        if not vinculo or Decimal(vinculo['valor']) != Decimal(valor):
            return 'REVISAO_VALOR_OU_VINCULO'
        tabela = vinculo['tabela']
        if tabela not in ('contas_receber','contas_pagar'):
            raise ValueError('Tabela financeira inválida.')
        repo.executar(c,'SELECT empresa_id FROM inter_titulos_empresas WHERE tabela=%s AND titulo_id=%s AND empresa_id=%s',
                      (tabela,vinculo['titulo_id'],empresa))
        if not c.fetchone():
            raise PermissionError('Vínculo empresarial revogado.')
        repo.executar(c,f'SELECT * FROM {tabela} WHERE id=%s' + ('' if repo.sqlite else ' FOR UPDATE'),(vinculo['titulo_id'],))
        titulo = dict(c.fetchone() or {})
        if (not titulo or titulo.get('status') in ('Pago','Recebido','Cancelado','Baixado por perda')
                or Decimal(str(titulo.get('valor_baixado') or 0)) != 0
                or Decimal(str(titulo.get('valor_total') or 0)) != Decimal(valor)
                or str(titulo.get('conciliado')).lower() in ('sim','1','true')):
            return 'REVISAO_TITULO_ALTERADO'
        status = 'Recebido' if tabela == 'contas_receber' else 'Pago'
        repo.executar(c,f'''UPDATE {tabela} SET status=%s, data_baixa=%s, valor_baixado=%s,
            observacao_baixa=%s, baixado_por=%s WHERE id=%s''',
            (status,data_baixa,valor,'Inter: '+evento,usuario['username'],vinculo['titulo_id']))
        # A proteção existente exige baixa integral anterior, na mesma transação.
        repo.executar(c,f'UPDATE {tabela} SET conciliado=%s, data_conciliacao=%s WHERE id=%s',
                      ('Sim',data_baixa,vinculo['titulo_id']))
        repo.executar(c,'''INSERT INTO inter_liquidacoes
            (empresa_id,ambiente,evento_id,operacao_id,valor,data_liquidacao) VALUES (%s,%s,%s,%s,%s,%s)''',
            (empresa,servico.ambiente,evento,uid,valor,str(quando)))
        repo.executar(c,'UPDATE inter_operacoes SET estado=%s WHERE id=%s AND empresa_id=%s AND ambiente=%s',
                      ('LIQUIDADA',uid,empresa,servico.ambiente))
        repo.registrar(c,empresa,servico.ambiente,usuario['username'],'BAIXA_CONCILIADA',uid)
    return 'CONCILIADA'


def sincronizar_vinculados(servico, empresa, usuario):
    """Um ciclo de polling; não cria agendador nem envia pagamentos.

    O chamador fornece um usuário de serviço autorizado. Apenas vínculos
    previamente revisados entram na baixa automática. Falhas não geram retry
    de escrita bancária; a próxima consulta é segura.
    """
    repo = servico.repo
    if not repo.financeiro_teste:
        raise PermissionError('Sincronização financeira exclusiva de teste.')
    with repo.transacao() as c:
        servico._autorizar(c, empresa, usuario, 'conciliar')
        repo.executar(c, '''SELECT o.id FROM inter_operacoes o
            JOIN inter_vinculos_financeiros v ON v.operacao_id=o.id
            AND v.empresa_id=o.empresa_id AND v.ambiente=o.ambiente
            WHERE o.empresa_id=%s AND o.ambiente=%s AND o.estado='ENVIADA'
            ORDER BY o.criado_em LIMIT 100''', (empresa, servico.ambiente))
        ids = [r['id'] for r in c.fetchall()]
    resultados = {}
    for uid in ids:
        try:
            resultados[uid] = conciliar_operacao(servico, empresa, usuario, uid)
        except Exception:
            resultados[uid] = 'FALHA_CONSULTA_OU_REVISAO_NECESSARIA'
    return resultados
