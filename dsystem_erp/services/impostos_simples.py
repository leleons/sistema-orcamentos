"""Estimativas gerenciais de 2026; não transmite PGDAS-D, DAS ou folha.

Fontes e limites em IMPOSTOS_V14.md. Decimal e arredondamento comercial.
A RBT12/FS12 precisam ser confirmadas pela contabilidade (não só notas do ERP).
"""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

ZERO = Decimal('0')
LIMITES = (180000, 360000, 720000, 1800000, 3600000)
TABELAS = {
    'I': ((4, 0), ('7.3', 5940), ('9.5', 13860), ('10.7', 22500), ('14.3', 87300)),
    'III': ((6, 0), ('11.2', 9360), ('13.5', 17640), (16, 35640), (21, 125640)),
    'V': (('15.5', 0), (18, 4500), ('19.5', 9900), ('20.5', 17100), (23, 62100)),
}


def numero(valor):
    try:
        n = Decimal(str(valor))
        if not n.is_finite() or n < 0:
            raise ValueError()
        return n
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError('Informe um número finito e não negativo.') from None


def moeda(valor):
    return numero(valor).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)


def percentual(valor):
    n = numero(valor)
    if n > 100:
        raise ValueError('Percentual deve estar entre 0 e 100.')
    return n


def valor_prolabore(modo, valor, faturamento_com_nota):
    """Não há valor/percentual implícito; o usuário escolhe por beneficiário."""
    if modo == 'fixo':
        return moeda(valor)
    if modo == 'percentual':
        return moeda(numero(faturamento_com_nota) * percentual(valor) / 100)
    raise ValueError('Escolha valor mensal fixo ou percentual do faturamento com nota.')


def encargos_prolabore(bruto, *, ano, dependentes=0, base_inss_outros=0,
                        deducoes_legais_adicionais=0):
    """Uma pessoa/competência; outros vínculos reduzem o teto de contribuição.

    Não substitui agregação de pagamentos do mês nem ajuste anual do IRPF.
    Não calcula CPP patronal fora do DAS, pensão/isenções especiais ou 13º.
    """
    if ano != 2026:
        raise ValueError('Tabelas de pró-labore disponíveis somente para 2026.')
    if isinstance(dependentes, bool) or int(numero(dependentes)) != numero(dependentes):
        raise ValueError('Quantidade de dependentes deve ser inteira.')
    bruto = moeda(bruto)
    teto_restante = max(ZERO, Decimal('8475.55') - numero(base_inss_outros))
    inss = moeda(min(bruto, teto_restante) * Decimal('.11'))
    legal = inss + numero(dependentes) * Decimal('189.59') + numero(deducoes_legais_adicionais)
    deducao = max(Decimal('607.20'), legal)
    base = max(ZERO, bruto - deducao)
    ir = ZERO
    for limite, aliquota, parcela in (
        ('2428.80', '0', '0'), ('2826.65', '.075', '182.16'),
        ('3751.05', '.15', '394.16'), ('4664.68', '.225', '675.49'),
        ('Infinity', '.275', '908.73'),
    ):
        if base <= Decimal(limite):
            ir = moeda(max(ZERO, base * Decimal(aliquota) - Decimal(parcela)))
            break
    reducao = ZERO
    if bruto <= 5000:
        reducao = min(ir, Decimal('312.89'))
    elif bruto <= 7350:
        reducao = min(ir, moeda(max(ZERO, Decimal('978.62') - Decimal('.133145') * bruto)))
    ir = moeda(max(ZERO, ir - reducao))
    return dict(bruto=bruto, inss=inss, irpf=ir, liquido=moeda(bruto-inss-ir),
                base_irpf=moeda(base), deducao_irpf=moeda(deducao), reducao_irpf=moeda(reducao))


def aliquota_simples(anexo, rbt12, fs12=None, *, ano):
    if ano != 2026:
        raise ValueError('Regras do Simples parametrizadas somente para 2026.')
    receita = numero(rbt12)
    if not 0 < receita <= 3600000:
        raise ValueError('Confirme a RBT12 positiva/proporcional. Acima de R$ 3,6 milhões é necessária apuração de sublimites pela contabilidade.')
    fator = None
    if anexo == 'Fator R':
        if fs12 is None:
            raise ValueError('Informe a FS12 confirmada para atividades sujeitas ao Fator R.')
        fator = numero(fs12) / receita
        anexo = 'III' if fator >= Decimal('.28') else 'V'
    if anexo not in TABELAS:
        raise ValueError('Anexo requer apuração específica pela contabilidade; não estimado automaticamente.')
    for limite, (aliquota, deducao) in zip(LIMITES, TABELAS[anexo]):
        if receita <= limite:
            efetiva = (receita * Decimal(str(aliquota)) / 100 - Decimal(deducao)) / receita
            return dict(anexo=anexo, fator_r=fator, aliquota=efetiva,
                        nominal=Decimal(str(aliquota)), deducao=Decimal(deducao))


def estimar_simples(receitas, rbt12, fs12=None, *, ano):
    """Receitas segregadas por anexo; não inclui retenção/ST/monofásicos."""
    linhas = []
    for anexo, valor in receitas.items():
        if numero(valor) == 0:
            continue
        regra = aliquota_simples(anexo, rbt12, fs12, ano=ano)
        linhas.append(dict(regra, enquadramento=anexo, receita=moeda(valor),
                           imposto=moeda(numero(valor) * regra['aliquota'])))
    return linhas, sum((l['imposto'] for l in linhas), ZERO)


def totais(simples, prolabores):
    """Retenções já integram o bruto: nunca somá-las novamente ao desembolso."""
    das = moeda(simples)
    bruto = sum((p['bruto'] for p in prolabores), ZERO)
    inss = sum((p['inss'] for p in prolabores), ZERO)
    irpf = sum((p['irpf'] for p in prolabores), ZERO)
    return dict(simples=das, prolabore_bruto=bruto, prolabore_liquido=bruto-inss-irpf,
                inss=inss, irpf=irpf, impostos=das+irpf, encargos=inss,
                total_recolher=das+irpf+inss, desembolso=das+bruto)
