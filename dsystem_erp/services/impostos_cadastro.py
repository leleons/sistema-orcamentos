"""Cadastro fiscal explícito por emitente, tipo e nome exato do item.

Reutiliza configuracoes_sistema. Não consulta serviços externos nem deduz
enquadramento tributário pelo nome/CNAE. Configurações levam autoria e versão.
"""
import copy
import hashlib
import json
from datetime import datetime, timezone

from dsystem_erp.services.impostos_simples import numero, percentual, moeda
from dsystem_erp.services.nfe_item_cadastro import nome_normalizado
from dsystem_erp.services.permissions import usuario_tem_permissao

PREFIXO = 'IMPOSTO_ITEM_'


def digitos(v):
    return ''.join(c for c in str(v or '') if c.isascii() and c.isdigit())


def codigo_fiscal(valor, tamanho, rotulo, opcional=False):
    texto = str(valor or '').strip()
    if not texto and opcional:
        return ''
    if any(c not in '0123456789./- ' for c in texto) or len(digitos(texto)) != tamanho:
        raise ValueError(f'{rotulo} deve conter {tamanho} dígitos, sem letras.')
    return digitos(texto)


def empresa_cnpj(v):
    v = digitos(v)
    if len(v) != 14 or len(set(v)) == 1:
        raise ValueError('Configure o CNPJ do emitente antes de cadastrar impostos.')
    return v


def chave_item(empresa, tipo, nome):
    if tipo not in ('Produto', 'Serviço') or not nome_normalizado(nome):
        raise ValueError('Informe tipo e nome completo do item.')
    texto = f'{tipo}:{nome_normalizado(nome)}'
    return PREFIXO + empresa_cnpj(empresa) + '_' + hashlib.sha256(texto.encode()).hexdigest()


def ler_cursor(cursor, chave, padrao=None):
    cursor.execute('SELECT valor FROM configuracoes_sistema WHERE chave=?', (chave,))
    row = cursor.fetchone()
    if not row:
        return padrao
    try:
        return json.loads(row['valor'])
    except (ValueError, TypeError):
        raise ValueError('Cadastro de impostos inválido. Revise antes de emitir.') from None


def gravar_cursor(cursor, chave, valor):
    # Evita DDL e funciona com MySQL e os bancos isolados de teste.
    cursor.execute('SELECT chave FROM configuracoes_sistema WHERE chave=?', (chave,))
    existe = cursor.fetchone()
    texto = json.dumps(valor, ensure_ascii=False, default=str, sort_keys=True)
    if existe:
        cursor.execute('UPDATE configuracoes_sistema SET valor=? WHERE chave=?', (texto, chave))
    else:
        cursor.execute('INSERT INTO configuracoes_sistema (chave,valor) VALUES (?,?)', (chave, texto))


def validar_regra(regra):
    r = copy.deepcopy(regra)
    r['empresa'] = empresa_cnpj(r.get('empresa'))
    r['nome'] = str(r.get('nome') or '').strip()
    chave_item(r['empresa'], r.get('tipo'), r['nome'])
    r['cnae'] = codigo_fiscal(r.get('cnae'), 7, 'CNAE (não uma data)')
    if r.get('anexo') not in ('I', 'III', 'V', 'Fator R', 'IV', 'Outro'):
        raise ValueError('Confirme o anexo com a contabilidade.')
    if not r.get('confirmado'):
        raise ValueError('Confirme o enquadramento e os parâmetros fiscais do item.')
    if r['tipo'] == 'Produto':
        r['crt'] = str(r.get('crt') or '1')
        if r['crt'] not in ('1', '3'):
            raise ValueError('Este emissor suporta CRT 1 ou CRT 3 / ICMS 00.')
        for campo, tamanho in (('ncm', 8), ('cfop', 4)):
            r[campo] = codigo_fiscal(r.get(campo), tamanho, campo.upper())
        if r.get('csosn') not in ('102', '500'):
            raise ValueError('Cadastre CSOSN 102 ou 500.')
        if str(r.get('origem')) not in list('012345678'):
            raise ValueError('Informe a origem fiscal de 0 a 8.')
        for campo in ('pis', 'cofins', 'icms'):
            r[campo] = str(percentual(r.get(campo, 0)))
        # O gerador atual implementa PIS/COFINS 01; não converter outros CST.
        if r.get('cst_pis', '01') != '01' or r.get('cst_cofins', '01') != '01':
            raise ValueError('O emissor atual suporta PIS/COFINS CST 01. Outros CST exigem implementação específica.')
        r['unidade'] = str(r.get('unidade') or '').strip()
        if not 1 <= len(r['unidade']) <= 6:
            raise ValueError('Unidade deve ter de 1 a 6 caracteres.')
    else:
        r['codigo_tributacao_nacional'] = codigo_fiscal(r.get('codigo_tributacao_nacional'), 6, 'Código nacional do serviço')
        r['codigo_tributacao_municipal'] = codigo_fiscal(r.get('codigo_tributacao_municipal'), 3, 'Desdobramento municipal', opcional=True)
        r['aliquota_iss'] = str(percentual(r.get('aliquota_iss')))
        if numero(r['aliquota_iss']) > 5:
            raise ValueError('ISS acima de 5% exige revisão do enquadramento.')
        r['retencao_inss'] = str(percentual(r.get('retencao_inss', 0)))
        r['informar_aliquota'] = bool(r.get('informar_aliquota', False))
        if str(r.get('tipo_retencao_issqn')) not in ('1', '2', '3'):
            raise ValueError('Confirme se há retenção de ISS.')
    return r


def salvar_regra(conectar, empresa, regra, usuario):
    if not usuario_tem_permissao('impostos.edit', usuario):
        raise PermissionError('Sem permissão para cadastrar impostos.')
    r = validar_regra(dict(regra, empresa=empresa))
    r.update(atualizado_por=usuario['username'], atualizado_em=datetime.now(timezone.utc).isoformat())
    r['versao'] = hashlib.sha256(json.dumps(r, sort_keys=True, default=str).encode()).hexdigest()
    conn = conectar()
    try:
        c = conn.cursor()
        gravar_cursor(c, chave_item(empresa, r['tipo'], r['nome']), r)
        conn.commit()
        return r
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def listar_regras(conectar, empresa):
    conn = conectar()
    try:
        c = conn.cursor()
        c.execute('SELECT valor FROM configuracoes_sistema WHERE chave LIKE ?', (PREFIXO+empresa_cnpj(empresa)+'_%',))
        return [json.loads(r['valor']) for r in c.fetchall()]
    finally:
        conn.close()


def regras_itens(cursor, empresa, itens, tipo):
    saida = []
    for item in itens:
        if (item.get('tipo_item') or 'Serviço') != tipo:
            continue
        nome = item.get('desc') or ''
        r = ler_cursor(cursor, chave_item(empresa, tipo, nome))
        if not r or not r.get('ativo', True):
            raise ValueError(f'Cadastre os impostos de {tipo}: {nome} em Cadastros → Cadastrar impostos antes de emitir.')
        r = validar_regra(r)
        if r['empresa'] != empresa_cnpj(empresa) or r['tipo'] != tipo or nome_normalizado(r['nome']) != nome_normalizado(nome):
            raise ValueError('Cadastro fiscal não corresponde ao emitente/item.')
        saida.append((item, r))
    if not saida:
        raise ValueError('Nenhum item para a espécie de nota selecionada.')
    return saida


def aplicar_regras(cursor, empresa, itens, tipo, dados):
    """Sempre antes de gerar/assinar XML. Operações não suportadas são bloqueadas."""
    pares = regras_itens(cursor, empresa, itens, tipo)
    novos, snapshots = [], []
    dados = copy.deepcopy(dados)
    for item, regra in pares:
        novo = copy.deepcopy(item)
        if regra.get('operacao_especial'):
            raise ValueError('Operação especial cadastrada. O emissor comum não aplica isenção, monofásicos ou ajustes especiais; revise o tratamento específico.')
        if tipo == 'Produto':
            if str(dados.get('regime_tributario') or '').split(' ')[0] != regra['crt']:
                raise ValueError('Regime tributário do emitente difere do cadastro do produto.')
            if regra['crt'] == '1' and regra['csosn'] != '102':
                raise ValueError('CSOSN 500 cadastrado, mas o emissor ainda não trata ICMS-ST. Não será convertido para 102; requer tratamento específico.')
            origem = str(dados.get('uf') or '').upper()
            destino = str((dados.get('destinatario') or {}).get('uf') or '').upper()
            prefixo = '5' if origem == destino else '6'
            if not origem or not destino or not regra['cfop'].startswith(prefixo):
                raise ValueError(f'CFOP cadastrado de {regra["nome"]} não corresponde às UFs da operação. Revise o cadastro.')
            for campo in ('ncm', 'cfop', 'origem', 'unidade', 'csosn'):
                novo[campo] = regra[campo]
            total = moeda(item['vtotal'])
            novo['tributos'] = {**(novo.get('tributos') or {}), 'base_pis': str(total),
                               'pis': regra['pis'], 'base_cofins': str(total), 'cofins': regra['cofins']}
            if regra['crt'] == '3':
                novo['tributos'].update(base_icms=str(total), icms=regra['icms'])
        else:
            if regra['tipo_retencao_issqn'] == '3':
                raise ValueError('Retenção pelo intermediário exige os dados do intermediário, ainda não implementados neste emissor.')
            if numero(regra.get('retencao_inss', 0)):
                raise ValueError('Retenção de INSS cadastrada, mas não suportada no emissor NFS-e atual. Não será omitida; requer tratamento específico.')
            campos = ('codigo_tributacao_nacional', 'codigo_tributacao_municipal', 'aliquota_iss', 'tipo_retencao_issqn', 'informar_aliquota')
            perfil = {k: regra[k] for k in campos}
            if novos and perfil != novos[0]:
                raise ValueError('Serviços possuem códigos/retenções diferentes. Separe em faturamentos próprios.')
            dados.update(perfil)
            novo = perfil
        novos.append(novo)
        snapshots.append(dict(nome=item.get('desc'), valor=str(moeda(item['vtotal'])), regra=regra))
    return dados, novos if tipo == 'Produto' else [], snapshots


def preparar_cadastro(conectar, empresa, itens, tipo, dados):
    conn = conectar()
    try:
        return aplicar_regras(conn.cursor(), empresa, itens, tipo, dados)
    finally:
        conn.close()


def conferir_plano(cursor, fat, tipo, plano, *, preparar=False):
    """Versão conferida fica congelada; alteração de regra exige nova revisão."""
    dados = plano['dados']
    empresa = empresa_cnpj(dados.get('emitente_cnpj') or dados.get('cnpj_prestador'))
    origem = fat.get('itens') or []
    origem = json.loads(origem) if isinstance(origem, str) else origem
    itens = plano['itens'] if tipo == 'Produto' else origem
    novos_dados, novos_itens, snapshot = aplicar_regras(cursor, empresa, itens, tipo, dados)
    if not preparar:
        if plano.get('cadastro_impostos') != snapshot:
            raise ValueError('Cadastro de impostos ausente ou alterado após a conferência. Revise e prepare a nota novamente.')
        campos = ('codigo_tributacao_nacional', 'codigo_tributacao_municipal', 'aliquota_iss', 'tipo_retencao_issqn', 'informar_aliquota')
        if tipo == 'Produto':
            if novos_itens != plano['itens']:
                raise ValueError('Tributação da nota difere do cadastro conferido. Prepare novamente.')
        elif any(dados.get(k) != novos_dados.get(k) for k in campos):
            raise ValueError('Tributação do serviço difere do cadastro conferido. Prepare novamente.')
    plano.update(dados=novos_dados, itens=novos_itens, cadastro_impostos=snapshot)
    return empresa, snapshot


def salvar_snapshot(cursor, empresa, nota_id, snapshot):
    gravar_cursor(cursor, f'IMPOSTO_NOTA_{empresa}_{nota_id}', {'itens': snapshot})
