"""Campos fiscais com taxas reutilizáveis por produto."""
import copy
import json
from datetime import date

from dsystem_erp.services.nfe_produto import aliquotas_ibscbs_integral
from dsystem_erp.services.fiscal_modelos import criar_modelo
from dsystem_erp.services.nfe_tributacao_item import sincronizar_regras_conferidas


def renderizar_taxas(st, item, chave, crt, ano=None):
    ano = ano or date.today().year
    preparado = copy.deepcopy(item)
    anteriores = preparado.get('tributos') or {}
    impostos = ('pis', 'cofins') if str(crt).startswith('1') else ('icms', 'pis', 'cofins')
    preparado['tributos'] = {}
    for imposto in impostos:
        col_base, col_aliq = st.columns(2)
        for campo, coluna, rotulo, limite in (
                (f'base_{imposto}', col_base, f'Base {imposto.upper()} (R$):', None),
                (imposto, col_aliq, f'Alíquota {imposto.upper()} (%):', 100.0)):
            salvo = anteriores.get(campo)
            preparado['tributos'][campo] = coluna.number_input(
                rotulo, min_value=0.0, max_value=limite,
                value=float(salvo) if salvo is not None else None,
                step=0.01, key=f'{chave}_{campo}')
    rtc_salvo = preparado.pop('ibscbs', None) or {}
    if st.checkbox('Aplicar IBS/CBS integral 000/000001 a este item',
                   value=bool(rtc_salvo), key=f'{chave}_rtc'):
        rtc = {'cst': '000', 'classificacao': '000001'}
        padrao = aliquotas_ibscbs_integral(ano)
        if padrao:
            st.caption(f'Alíquotas de {ano} preenchidas automaticamente: IBS estadual 0,1%, municipal 0% e CBS 0,9%.')
        for campo, rotulo in (('base', 'Base IBS/CBS (R$)'), ('uf', 'IBS estadual (%)'),
                              ('municipal', 'IBS municipal (%)'), ('cbs', 'CBS (%)')):
            valor = padrao.get(campo, rtc_salvo.get(campo))
            if campo == 'base' and valor is None:
                valor = item.get('vtotal')
            rtc[campo] = st.number_input(rotulo, min_value=0.0,
                max_value=None if campo == 'base' else 100.0,
                value=float(valor) if valor is not None else None,
                disabled=campo in padrao, step=0.01, key=f'{chave}_rtc_{campo}_{ano}')
        preparado['ibscbs'] = rtc
    return preparado


def salvar_regra_produtos(fat, dados, itens, endpoint, usuario, salvar_config, modelos_anteriores=()):
    plano = dict(faturamento=fat, dados=dados, itens=itens, endpoint=endpoint)
    modelo = criar_modelo(fat, dict(tipo='Produto', estado='Pronta',
                                  plano_json=json.dumps(plano, default=str)), usuario, por_item=True)
    for atualizado in [modelo] + sincronizar_regras_conferidas(modelo, modelos_anteriores):
        salvar_config(atualizado['chave'], json.dumps(atualizado, ensure_ascii=False, default=str),
                      'Taxas por produto conferidas no preparo da NF-e')
    return modelo


def renderizar_salvar_regra(st, fat, dados, itens, endpoint, pronto, pode_editar, usuario, salvar_config, modelos_anteriores=()):
    with st.expander('Guardar taxas para as próximas notas', expanded=False):
        st.caption('Depois de conferir os impostos, salve uma vez. O produto puxará NCM, CFOP e taxas nas próximas notas do mesmo cliente e operação, inclusive ao faturar com emissão automática.')
        if st.button('Salvar taxas dos produtos', disabled=not pronto or not pode_editar,
                     key=f"nfe_salvar_taxas_{fat['id']}"):
            try:
                salvar_regra_produtos(fat, dados, itens, endpoint, usuario, salvar_config, modelos_anteriores)
                st.session_state[f"nfe_taxas_salvas_{fat['id']}"] = True
                st.rerun()
            except Exception as erro:
                st.error(str(erro))
