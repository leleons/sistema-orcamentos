"""Modelo fiscal autorizado uma vez; prepara novos faturamentos no clique."""
import copy
import hashlib
import json
from datetime import date
from decimal import Decimal

from dsystem_erp.services.fiscal_automatico import itens_lista, salvar_plano, validar_plano
from dsystem_erp.services.nfe_cadastro_automatico import completar_destinatario, digitos
from dsystem_erp.services.nfe_item_cadastro import nome_normalizado
from dsystem_erp.services.nfe_produto import aplicar_aliquotas_ibscbs_integral


def identidade_item(item):
    return str(item.get('estoque_id') or nome_normalizado(item.get('desc')))


def chave_modelo(fat, tipo):
    identidades = sorted(identidade_item(i) for i in itens_lista(fat)
                         if (i.get('tipo_item') or 'Serviço') == tipo)
    assinatura = json.dumps([digitos(fat.get('cnpj')), tipo, identidades], ensure_ascii=False)
    return 'FISCAL_MODELO_' + hashlib.sha256(assinatura.encode()).hexdigest()


def _produto_completo(item, dados):
    item = copy.deepcopy(item)
    for campo in ('ncm', 'cfop', 'unidade', 'ibscbs'):
        if not item.get(campo) and dados.get(campo):
            item[campo] = copy.deepcopy(dados[campo])
    item.setdefault('origem', '0')
    return item


def criar_modelo(fat, registro, usuario, *, por_item=False):
    if registro.get('estado') not in ('Pronta', 'Autorizada'):
        raise ValueError('Escolha uma configuração conferida ou uma nota autorizada.')
    plano = json.loads(registro['plano_json'])
    validar_plano(fat, registro['tipo'], plano)
    itens = [_produto_completo(i, plano['dados']) for i in plano.get('itens') or []] if registro['tipo'] == 'Produto' else []
    if registro['tipo'] == 'Produto':
        plano['itens'] = itens
    ids = [identidade_item(i) for i in itens]
    if len(ids) != len(set(ids)):
        raise ValueError('Agrupe produtos repetidos antes de configurar a emissão automática.')
    # Este modelo suporta bases integrais; não transforma reduções em regras genéricas.
    for item in itens:
        total = Decimal(str(item.get('vtotal') or 0))
        bases = [v for k, v in (item.get('tributos') or {}).items() if k.startswith('base_')]
        if item.get('ibscbs'):
            bases.append(item['ibscbs'].get('base'))
        if any(v is None or Decimal(str(v)) != total for v in bases):
            raise ValueError('Bases reduzidas/diferenciadas precisam de regra fiscal específica; não podem ser reutilizadas por este modelo.')
    if any(Decimal(str(v or 0)) != 0 for v in (plano['dados'].get('totais_tributos') or {}).values()):
        raise ValueError('Totais tributários fixos não podem ser reutilizados em valores diferentes.')
    referencias = [copy.deepcopy(i) for i in itens_lista(fat) if (i.get('tipo_item') or 'Serviço') == registro['tipo']]
    if registro['tipo'] == 'Produto':
        for referencia, preparado in zip(referencias, itens):
            referencia.update({k: copy.deepcopy(preparado[k]) for k in ('ncm', 'cfop', 'unidade', 'origem', 'tributos', 'ibscbs') if k in preparado})
    return dict(plano=plano, tipo=registro['tipo'], autorizado_por=usuario,
                chave=chave_modelo(fat, registro['tipo']), reutilizar_por_item=bool(por_item), itens_referencia=referencias,
                ano_referencia=date.today().year)


def _contexto_modelo(modelo):
    dados = copy.deepcopy(modelo['plano']['dados'])
    for campo in ('competencia', 'data_hora_emissao', 'numero', 'numero_dps', 'codigo_nf', 'valor', 'descricao', 'observacoes'):
        dados.pop(campo, None)
    if modelo['tipo'] == 'Produto':
        for campo in ('ncm', 'cfop', 'unidade', 'ibscbs'):
            dados.pop(campo, None)  # Classificação materializada em cada item.
    return dict(dados=dados, endpoint=modelo['plano']['endpoint'])


def _vinculo(item, tipo):
    return item.get('estoque_id') if tipo == 'Produto' else item.get('servico_id') or item.get('nfse_servico_id')


def _regra_item(item):
    regra = {k: copy.deepcopy(item[k]) for k in ('ncm', 'cfop', 'unidade', 'origem', 'tributos', 'ibscbs') if k in item}
    for campo in regra.get('tributos', {}):
        if campo.startswith('base_'):
            regra['tributos'][campo] = 'integral'
    if regra.get('ibscbs'):
        regra['ibscbs']['base'] = 'integral'
    return regra


def _conferir_codigo_informado(item, referencia, tipo, dados):
    campos = ('ncm', 'cfop', 'origem', 'unidade') if tipo == 'Produto' else ('codigo_servico',)
    for campo in campos:
        atual = item.get(campo)
        salvo = (dados.get('codigo_tributacao_nacional') if campo == 'codigo_servico' else referencia.get(campo))
        if atual not in (None, '') and salvo not in (None, ''):
            normalizar = digitos if campo in ('ncm', 'cfop', 'codigo_servico') else lambda v: str(v).strip().upper()
            if normalizar(atual) != normalizar(salvo):
                raise ValueError(f"{item.get('desc')}: {campo} difere da configuração autorizada. Confira o cadastro antes de emitir.")


def montar_modelo_por_itens(fat, tipo, modelos, emitente):
    """Compõe só regras expressamente autorizadas por item, para o mesmo cliente.

    Nunca escolhe por aproximação, por última utilização, por CNAE, ou mistura
    ambientes/operações/tributação de serviço. Uma referência desconhecida bloqueia.
    """
    modelos = [m for m in modelos if m.get('reutilizar_por_item') is True and m.get('tipo') == tipo
               and digitos(m['plano']['faturamento'].get('cnpj')) == digitos(fat.get('cnpj'))
               and digitos(m['plano']['dados'].get('cnpj_prestador') or m['plano']['dados'].get('emitente_cnpj')) == digitos(emitente)]
    if not modelos:
        return None
    selecionados = []
    for item in (i for i in itens_lista(fat) if (i.get('tipo_item') or 'Serviço') == tipo):
        vinculo, nome = _vinculo(item, tipo), nome_normalizado(item.get('desc'))
        candidatos = [(m, r) for m in modelos for r in m.get('itens_referencia', [])
                      if (str(_vinculo(r, tipo)) == str(vinculo) if vinculo else
                          bool(nome) and nome_normalizado(r.get('desc')) == nome)]
        if not candidatos:
            raise ValueError(f"{item.get('desc') or tipo}: falta configuração fiscal autorizada para este item/nome.")
        if not vinculo and len({str(_vinculo(r, tipo) or '') for _, r in candidatos}) > 1:
            raise ValueError(f"{item.get('desc')}: nome ambíguo; vincule o cadastro correto antes de emitir.")
        modelo, referencia = candidatos[0]
        if any(_contexto_modelo(m) != _contexto_modelo(modelo) or _regra_item(r) != _regra_item(referencia) for m, r in candidatos[1:]):
            raise ValueError(f"{item.get('desc')}: configurações fiscais divergentes para este nome. Confirme a operação e o ambiente.")
        _conferir_codigo_informado(item, referencia, tipo, modelo['plano']['dados'])
        selecionados.append((modelo, referencia, item))
    if not selecionados:
        return None
    base = selecionados[0][0]
    if any(_contexto_modelo(m) != _contexto_modelo(base) for m, _, _ in selecionados[1:]):
        raise ValueError('Os itens possuem operações, códigos de serviço ou ambientes diferentes. Confira a separação das notas.')
    combinado = copy.deepcopy(base)
    combinado['chave'] = chave_modelo(fat, tipo)
    combinado['autorizado_por'] = ', '.join(sorted({m['autorizado_por'] for m, _, _ in selecionados}))
    if tipo == 'Produto':
        preparados = []
        for _, referencia, item in selecionados:
            preparado = copy.deepcopy(referencia)
            # Mantém o vínculo/nome atual para o montador atualizar valores e bases.
            for campo in ('estoque_id', 'desc'):
                preparado.pop(campo, None)
                if campo in item:
                    preparado[campo] = item[campo]
            preparados.append(preparado)
        combinado['plano']['itens'] = preparados
    return combinado


def montar_do_modelo(fat, tipo, modelo, cliente, config):
    if modelo.get('chave') != chave_modelo(fat, tipo):
        raise ValueError('Modelo não corresponde ao cliente e aos itens deste faturamento.')
    plano = copy.deepcopy(modelo['plano'])
    dados = plano['dados']
    emitente = dados.get('cnpj_prestador') or dados.get('emitente_cnpj')
    if digitos(config('NFSE_CNPJ', '')) != digitos(emitente):
        raise ValueError('O emitente mudou. Revise o modelo fiscal antes de emitir.')
    if digitos(cliente.get('cnpj')) != digitos(fat.get('cnpj')):
        raise ValueError('Confirme o cadastro do destinatário deste faturamento.')
    dados['competencia'] = date.today().isoformat()
    dados['observacoes'] = fat.get('obs_nota') or ''
    dados.pop('codigo_nf', None)
    dados.pop('data_hora_emissao', None)
    origem = [dict(i) for i in itens_lista(fat) if (i.get('tipo_item') or 'Serviço') == tipo]
    if tipo == 'Serviço':
        for item in origem:
            _conferir_codigo_informado(item, {}, tipo, dados)
        dados['valor'] = float(sum(Decimal(str(i.get('vtotal') or 0)) for i in origem))
        dados['descricao'] = '\n'.join(f"{i.get('desc')} — Qtd: {i.get('qtd')} — Total: {i.get('vtotal')}" for i in origem)
        plano['itens'] = origem
    else:
        consulta = completar_destinatario(cliente, dados['ambiente'], config('NFSE_CERT_PFX_PATH', ''), config('NFSE_CERT_PASSWORD', ''))
        destino = consulta['dados']
        anterior = dados.get('destinatario') or {}
        # Mesma empresa não implica operação fiscal idêntica após mudança de UF/situação.
        if any(destino.get(k) != anterior.get(k) for k in ('uf', 'indicador_ie')):
            raise ValueError('UF ou situação de ICMS do destinatário mudou/não foi confirmada. Revise a configuração fiscal.')
        dados['destinatario'] = destino
        por_id = {identidade_item(i): i for i in plano['itens']}
        preparados = []
        for item in origem:
            anterior_item = por_id[identidade_item(item)]
            _conferir_codigo_informado(item, anterior_item, tipo, dados)
            for campo in ('ncm', 'cfop', 'origem', 'unidade', 'tributos', 'ibscbs'):
                if campo in anterior_item:
                    item[campo] = copy.deepcopy(anterior_item[campo])
            for campo in item.get('tributos', {}):
                if campo.startswith('base_'):
                    item['tributos'][campo] = float(item['vtotal'])
            if item.get('ibscbs'):
                item['ibscbs']['base'] = float(item['vtotal'])
            preparados.append(aplicar_aliquotas_ibscbs_integral(item, date.today().year))
        plano['itens'] = preparados
    plano['faturamento'] = {**fat, 'telefone': cliente.get('telefone'), 'email': cliente.get('email')}
    validar_plano(fat, tipo, plano)
    return plano


def preparar_por_modelo(conectar, fat, tipo, config):
    raw = config(chave_modelo(fat, tipo), '')
    modelo = json.loads(raw) if raw else None
    conn = conectar()
    try:
        c = conn.cursor()
        if modelo is None:
            c.execute("SELECT chave,valor FROM configuracoes_sistema WHERE chave LIKE 'FISCAL_MODELO_%'")
            modelos = []
            for row in c.fetchall():
                if str(row.get('chave') or '').startswith('FISCAL_MODELO_'):
                    modelos.append(json.loads(row['valor']))
            modelo = montar_modelo_por_itens(fat, tipo, modelos, config('NFSE_CNPJ', ''))
            if modelo is None:
                return False
        c.execute('SELECT * FROM clientes')
        clientes = [r for r in c.fetchall() if digitos(r.get('cnpj')) == digitos(fat.get('cnpj'))]
    finally:
        conn.close()
    if len(clientes) != 1:
        raise ValueError('Cadastro do cliente ausente ou duplicado. Corrija antes da emissão automática.')
    plano = montar_do_modelo(fat, tipo, modelo, clientes[0], config)
    salvar_plano(conectar, fat['id'], tipo, plano['dados'], plano['itens'],
                 plano['faturamento'], plano['endpoint'], modelo['autorizado_por'])
    return True
