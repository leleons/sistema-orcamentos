"""Datas de vigência independentes da interface e do banco."""
import calendar
from datetime import date, datetime


def data_contrato(valor):
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    for formato in ('%d/%m/%Y', '%Y-%m-%d'):
        try:
            return datetime.strptime(str(valor), formato).date()
        except ValueError:
            pass
    raise ValueError('Informe uma data válida para o início do contrato.')


def fim_vigencia(inicio, meses=12):
    inicio = data_contrato(inicio)
    if not isinstance(meses, int) or meses < 1:
        raise ValueError('O prazo deve ser um número positivo de meses.')
    total = inicio.year * 12 + inicio.month - 1 + meses
    ano, mes = divmod(total, 12)
    mes += 1
    return date(ano, mes, min(inicio.day, calendar.monthrange(ano, mes)[1]))


def preencher_datas_word(tipo, slots, inicio, fim, meses=12, assinatura=None):
    inicio = data_contrato(inicio)
    assinatura = data_contrato(assinatura) if assinatura is not None else inicio
    nomes_meses = ('janeiro fevereiro março abril maio junho julho agosto setembro outubro novembro dezembro').split()
    valores = {}
    for slot in slots:
        p, token = slot['paragrafo'], slot['token']
        valor = None
        if tipo in ('Tecnologia e Infraestrutura', 'Prestação de Serviços PJ') and p == 21:
            valor = f'1 ano, de {inicio:%d/%m/%Y} a {fim:%d/%m/%Y}'
        elif tipo == 'Serviços e Locação de Equipamentos' and p in (14, 15):
            if token == '[Número]':
                valor = str(meses)
            elif token == '[Data de Início]':
                valor = inicio.strftime('%d/%m/%Y')
            elif token == '[Data de Término]' and fim:
                valor = fim.strftime('%d/%m/%Y')
        elif p == (25 if tipo in ('Tecnologia e Infraestrutura', 'Prestação de Serviços PJ') else 42):
            valor = {'[Dia]': str(assinatura.day), '[Mês]': nomes_meses[assinatura.month-1], '[Ano]': str(assinatura.year)}.get(token)
        if valor is not None:
            valores[slot['chave']] = valor
    return valores
