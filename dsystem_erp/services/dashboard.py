"""Indicadores calculados sem alterar os lançamentos de origem."""

from decimal import Decimal, InvalidOperation
import unicodedata

from dsystem_erp.utils.datas import parse_data_flex
from dsystem_erp.services.orcamentos import orcamento_esta_vencido


def normalizar(texto):
    return ''.join(c for c in unicodedata.normalize('NFD', str(texto or '').strip().lower())
                   if unicodedata.category(c) != 'Mn')


def valor_decimal(valor):
    texto = str(valor or 0).replace('R$', '').replace(' ', '').strip()
    if ',' in texto:
        texto = texto.replace('.', '').replace(',', '.')
    try:
        numero = Decimal(texto)
        return numero if numero.is_finite() else Decimal('0')
    except InvalidOperation:
        return Decimal('0')


def resumo_financeiro(registros, hoje):
    abertos, vencidos, sem_data = [], [], []
    janelas = {dias: [] for dias in (5, 10, 15)}
    for registro in registros:
        if normalizar(registro.get('status')) in {'pago', 'recebido', 'cancelado', 'baixado por perda'}:
            continue
        saldo = max(Decimal('0'), valor_decimal(registro.get('valor_total')) - valor_decimal(registro.get('valor_baixado')))
        if saldo == 0:
            continue
        item = dict(registro, saldo=saldo)
        abertos.append(item)
        vencimento = parse_data_flex(item.get('data_vencimento'))
        if not vencimento:
            sem_data.append(item)
            continue
        diferenca = (vencimento - hoje).days
        if diferenca < 0:
            vencidos.append(item)
        else:
            for dias in janelas:
                if diferenca <= dias:
                    janelas[dias].append(item)
    return {'abertos': abertos, 'vencidos': vencidos, 'sem_data': sem_data, 'janelas': janelas}


def total_saldo(registros):
    return sum((r['saldo'] for r in registros), Decimal('0'))


def resumo_atendimentos(checklists, agendamentos, chamados, hoje):
    registros = []
    for origem, dados, campo_cliente, campo_titulo, campo_data in (
        ('Atendimento', checklists, 'cliente', 'equipamento', None),
        ('Agendamento', agendamentos, 'cliente_nome', 'descricao', 'data_visita'),
        ('Chamado', chamados, 'cliente_nome', 'titulo', 'data_solicitada'),
    ):
        for dado in dados:
            status = normalizar(dado.get('status'))
            if status in {'concluido', 'realizado', 'cancelado', 'recusado pelo cliente', 'finalizado', 'entregue'}:
                continue
            prazo = parse_data_flex((dado.get('ajuste_data') or dado.get(campo_data)) if campo_data else None)
            registros.append({
                'ID': dado.get('id'), 'Origem': origem, 'Cliente': dado.get(campo_cliente) or '',
                'Descrição': dado.get(campo_titulo) or '', 'Status': dado.get('status') or 'Em aberto',
                'Prazo': prazo.isoformat() if prazo else '',
                '_pendente': not status or status in {'novo', 'aberto', 'em aberto', 'agendado', 'adiado', 'atrasado', 'transferido', 'reagendado', 'designado'} or 'aguardando' in status,
                '_vencido': bool(prazo and prazo < hoje),
                '_a_vencer': bool(prazo and 0 <= (prazo - hoje).days <= 15),
            })
    return {
        'Em aberto': registros,
        'Pendentes': [r for r in registros if r['_pendente']],
        'Vencidos': [r for r in registros if r['_vencido']],
        'A vencer (15 dias)': [r for r in registros if r['_a_vencer']],
    }


def resumo_orcamentos(registros, hoje):
    grupos = {'Não faturados': [], 'Vencidos': [], 'Faturados': []}
    for registro in registros:
        status = normalizar(registro.get('status'))
        if status == 'cancelado':
            continue
        if registro.get('faturamento_id') or status in {'aprovado e lancado', 'faturado'}:
            grupos['Faturados'].append(registro)
        else:
            grupos['Não faturados'].append(registro)
            if status == 'vencido' or orcamento_esta_vencido(registro, hoje):
                grupos['Vencidos'].append(registro)
    return grupos
