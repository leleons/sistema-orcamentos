"""Reutilização de taxas conferidas para o mesmo produto e operação fiscal."""
import copy
import hashlib
import json
from datetime import date
from decimal import Decimal, InvalidOperation

from dsystem_erp.services.fiscal_modelos import chave_modelo, _regra_item, _conferir_codigo_informado, _produto_completo
from dsystem_erp.services.nfe_cadastro_automatico import digitos
from dsystem_erp.services.nfe_item_cadastro import nome_normalizado
from dsystem_erp.services.nfe_produto import aplicar_aliquotas_ibscbs_integral


def carregar_modelos_produtos(conectar):
    conn = conectar()
    try:
        c = conn.cursor()
        c.execute("SELECT valor FROM configuracoes_sistema WHERE chave LIKE 'FISCAL_MODELO_%'")
        modelos = []
        for row in c.fetchall():
            try:
                modelo = json.loads(dict(row)['valor'])
                if (isinstance(modelo, dict) and modelo.get('tipo') == 'Produto'
                        and modelo.get('autorizado_por') and isinstance(modelo.get('plano'), dict)
                        and isinstance(modelo['plano'].get('dados'), dict)
                        and isinstance(modelo['plano'].get('faturamento'), dict)):
                    modelos.append(modelo)
            except (KeyError, TypeError, ValueError):
                continue
        return modelos
    finally:
        conn.close()


def contexto_tributacao(fat, dados):
    destino = dados.get('destinatario') or {}
    return (digitos(fat.get('cnpj')), digitos(dados.get('emitente_cnpj')),
            str(dados.get('regime_tributario') or '').split(' ')[0],
            str(dados.get('uf') or '').strip().upper(),
            str(destino.get('uf') or '').strip().upper(), str(destino.get('indicador_ie') or ''),
            str(dados.get('ambiente') or '').strip().lower(),
            nome_normalizado(dados.get('natureza_operacao') or 'Venda de mercadoria'))


def _bases_integrais(item):
    try:
        total = Decimal(str(item.get('vtotal')))
        bases = [v for k, v in (item.get('tributos') or {}).items() if k.startswith('base_')]
        if item.get('ibscbs'):
            bases.append(item['ibscbs'].get('base'))
        return bool(bases) and total.is_finite() and total > 0 and all(
            v is not None and Decimal(str(v)).is_finite() and Decimal(str(v)) == total for v in bases)
    except (InvalidOperation, TypeError, ValueError):
        return False


def buscar_tributacao_item(fat, item, dados, modelos, ano=None):
    """Devolve sugestão só para vínculo exato ou nome único, no contexto salvo."""
    ano = ano or date.today().year
    resultado = {'item': copy.deepcopy(item), 'aplicada': False,
                 'mensagem': 'Este item ainda não tem taxas salvas para esta operação. Preencha uma vez e salve a regra abaixo.'}
    contexto = contexto_tributacao(fat, dados)
    # UF e situação de ICMS precisam estar resolvidas antes de escolher a regra.
    if not all(contexto):
        resultado['mensagem'] = 'Complete o cliente, emitente, UF, situação de ICMS e operação para buscar as taxas salvas.'
        return resultado
    candidatos = []
    for modelo in modelos:
        if modelo.get('tipo') != 'Produto' or not modelo.get('autorizado_por'):
            continue
        plano = modelo.get('plano') or {}
        if contexto_tributacao(plano.get('faturamento') or {}, plano.get('dados') or {}) != contexto:
            continue
        # Modelos antigos não traziam o ano separado; usam a competência salva.
        ano_modelo = modelo.get('ano_referencia') or str((plano.get('dados') or {}).get('competencia') or '')[:4]
        if str(ano_modelo) != str(ano):
            continue
        if modelo.get('reutilizar_por_item') is not True and modelo.get('chave') != chave_modelo(fat, 'Produto'):
            continue
        for referencia in modelo.get('itens_referencia') or []:
            if not isinstance(referencia, dict):
                continue
            vinculo = item.get('estoque_id')
            coincide = (str(referencia.get('estoque_id')) == str(vinculo) if vinculo else
                        bool(nome_normalizado(item.get('desc'))) and nome_normalizado(referencia.get('desc')) == nome_normalizado(item.get('desc')))
            if coincide:
                candidatos.append((modelo, referencia))
    if not candidatos:
        return resultado
    if not item.get('estoque_id') and len({str(r.get('estoque_id') or '') for _, r in candidatos}) > 1:
        resultado['mensagem'] = 'Há produtos distintos com este nome. Selecione o cadastro correto para puxar as taxas.'
        return resultado
    if any(not _bases_integrais(r) for _, r in candidatos):
        resultado['mensagem'] = 'A regra salva contém bases diferenciadas; confira a tributação deste item.'
        return resultado
    referencia = aplicar_aliquotas_ibscbs_integral(candidatos[0][1], ano)
    if any(_regra_item(aplicar_aliquotas_ibscbs_integral(r, ano)) != _regra_item(referencia) for _, r in candidatos[1:]):
        resultado['mensagem'] = 'Há taxas salvas divergentes para este produto e operação. Confira e salve a regra correta.'
        return resultado
    try:
        _conferir_codigo_informado(item, referencia, 'Produto', dados)
    except ValueError as erro:
        resultado['mensagem'] = str(erro)
        return resultado
    preparado = copy.deepcopy(item)
    for campo in ('ncm', 'cfop', 'unidade', 'origem', 'tributos', 'ibscbs'):
        preparado.pop(campo, None)
        if campo in referencia:
            preparado[campo] = copy.deepcopy(referencia[campo])
    for campo in preparado.get('tributos', {}):
        if campo.startswith('base_'):
            preparado['tributos'][campo] = float(item['vtotal'])
    if preparado.get('ibscbs'):
        preparado['ibscbs']['base'] = float(item['vtotal'])
    resultado.update(item=preparado, aplicada=True,
                     mensagem='Taxas preenchidas pela regra salva deste produto. Bases ajustadas ao valor atual do item.')
    return resultado


def chave_widgets_tributacao(fat, indice, item, dados):
    conteudo = [contexto_tributacao(fat, dados), item]
    assinatura = hashlib.sha256(json.dumps(conteudo, sort_keys=True, default=str).encode()).hexdigest()[:16]
    return f"nfe_taxas_{fat['id']}_{indice}_{assinatura}"


def sincronizar_regras_conferidas(modelo_novo, anteriores):
    """Atualiza configurações futuras já salvas ao conferir novamente as taxas.

    A substituição exige o mesmo contexto e vínculo. Nunca escolhe a configuração
    mais recente por conta própria e não altera notas ou planos de envio existentes.
    """
    contexto = contexto_tributacao(modelo_novo['plano']['faturamento'], modelo_novo['plano']['dados'])
    novos = modelo_novo['itens_referencia']
    alterados = []
    for anterior in anteriores:
        if anterior.get('chave') == modelo_novo['chave']:
            continue  # O modelo principal já será substituído pelo novo.
        plano = anterior.get('plano') or {}
        if (anterior.get('tipo') != 'Produto' or not anterior.get('autorizado_por')
                or contexto_tributacao(plano.get('faturamento') or {}, plano.get('dados') or {}) != contexto):
            continue
        ano_anterior = anterior.get('ano_referencia') or str((plano.get('dados') or {}).get('competencia') or '')[:4]
        if str(ano_anterior) != str(modelo_novo['ano_referencia']):
            continue
        atualizado = copy.deepcopy(anterior)
        for campo in ('itens_referencia',):
            atualizado[campo] = [_produto_completo(item, plano.get('dados') or {})
                                for item in atualizado.get(campo) or []]
        atualizado['plano']['itens'] = [_produto_completo(item, plano.get('dados') or {})
                                       for item in atualizado['plano'].get('itens') or []]
        # O enquadramento fica em cada produto; um padrão antigo do documento não
        # pode reativar IBS/CBS quando ele foi retirado explicitamente de um item.
        atualizado['plano']['dados'].pop('ibscbs', None)
        mudou = False
        for lista in (atualizado.get('itens_referencia') or [], atualizado['plano'].get('itens') or []):
            for item in lista:
                candidatos = [novo for novo in novos if
                    (str(novo.get('estoque_id')) == str(item.get('estoque_id')) if novo.get('estoque_id') else
                     not item.get('estoque_id') and nome_normalizado(novo.get('desc')) == nome_normalizado(item.get('desc')))]
                if len(candidatos) != 1 or not _bases_integrais(item):
                    continue
                novo = candidatos[0]
                for campo in ('ncm', 'cfop', 'origem', 'unidade', 'tributos', 'ibscbs'):
                    item.pop(campo, None)
                    if campo in novo:
                        item[campo] = copy.deepcopy(novo[campo])
                for campo in item.get('tributos', {}):
                    if campo.startswith('base_'):
                        item['tributos'][campo] = float(item['vtotal'])
                if item.get('ibscbs'):
                    item['ibscbs']['base'] = float(item['vtotal'])
                mudou = True
        if mudou:
            atualizado['taxas_atualizadas_por'] = modelo_novo['autorizado_por']
            alterados.append(atualizado)
    return alterados
