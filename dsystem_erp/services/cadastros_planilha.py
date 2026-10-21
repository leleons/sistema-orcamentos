"""Importação validada dos três cadastros financeiros, sem lançamentos financeiros."""
from __future__ import annotations

import hashlib
import io
import json
import re
import unicodedata
from datetime import datetime
from zipfile import ZipFile, BadZipFile

from dsystem_erp.services.permissions import usuario_tem_permissao

ABAS = {
    'Plano de contas': ('Plano de contas', 'codigo nome codigo_pai nivel tipo natureza_saldo classe grupo_dre aceita_lancamento ativo observacao'),
    'Centros de custo': ('Centro de custo', 'codigo nome codigo_pai nivel tipo aceita_lancamento ativo responsavel criterio_rateio observacao'),
    'Naturezas financeiras': ('Natureza financeira', 'codigo nome codigo_pai nivel tipo fluxo conta_contabil_sugerida centro_custo_sugerido impacta_dre grupo_dre aceita_lancamento ativo regra_uso'),
}
TIPOS = tuple(v[0] for v in ABAS.values())
COLUNAS = {
    'codigo_pai': 'TEXT', 'nivel': 'INTEGER', 'tipo_conta': 'TEXT',
    'natureza_saldo': 'TEXT', 'classe': 'TEXT', 'grupo_dre': 'TEXT',
    'aceita_lancamento': "VARCHAR(10) DEFAULT 'Sim'", 'fluxo': 'TEXT',
    'conta_contabil_sugerida': 'TEXT', 'centro_custo_sugerido': 'TEXT',
    'impacta_dre': 'TEXT', 'responsavel': 'TEXT', 'criterio_rateio': 'TEXT',
    'regra_uso': 'TEXT', 'importacao_origem': 'TEXT',
}
CAMPOS = ('tipo', 'codigo', 'nome', 'ativo', 'observacoes', *COLUNAS)


def normalizar(v):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(v or '').strip()) if not unicodedata.combining(c)).casefold()


def _texto(v):
    return '' if v is None else str(v).strip()


def _codigo(v):
    # Códigos são identificadores, nunca números/datas a serem arredondados.
    if not isinstance(v, str) or not re.fullmatch(r'[A-Za-z0-9]+(?:[.][A-Za-z0-9]+)*', v.strip()):
        raise ValueError('Código deve ser texto, preservando pontos e zeros.')
    return v.strip()


def _sim_nao(v, campo):
    if normalizar(v) not in ('sim', 'nao'):
        raise ValueError(f'{campo}: use SIM ou NAO.')
    return 'Sim' if normalizar(v) == 'sim' else 'Não'


def ler_planilha(conteudo: bytes):
    """Lê somente as abas de dados; nunca executa fórmulas ou instruções da pasta."""
    from openpyxl import load_workbook
    if len(conteudo) > 10 * 1024 * 1024:
        raise ValueError('Arquivo acima de 10 MB.')
    try:
        with ZipFile(io.BytesIO(conteudo)) as z:
            if sum(i.file_size for i in z.infolist()) > 50 * 1024 * 1024:
                raise ValueError('Conteúdo descompactado acima de 50 MB.')
        wb = load_workbook(io.BytesIO(conteudo), read_only=True, data_only=False, keep_links=False)
    except (BadZipFile, OSError, KeyError) as ex:
        raise ValueError('Arquivo XLSX inválido.') from ex
    registros, erros, lidas = [], [], []
    try:
        nomes = {normalizar(a): a for a in ABAS}
        for ws in wb:
            aba = nomes.get(normalizar(ws.title))
            if not aba:
                continue
            if aba in lidas:
                raise ValueError(f'Aba duplicada: {aba}.')
            lidas.append(aba)
            tipo, cabecalho = ABAS[aba]
            linhas = iter(ws.iter_rows())
            primeira = next(linhas, ())
            colunas = [_texto(c.value).lower() for c in primeira]
            esperadas = cabecalho.split()
            if len(colunas) != len(set(colunas)) or set(colunas) != set(esperadas):
                erros.append(f'{aba}: cabeçalho esperado: {", ".join(esperadas)}.')
                continue
            for numero, cells in enumerate(linhas, 2):
                if numero > 10001:
                    raise ValueError(f'{aba}: limite de 10.000 registros.')
                if not any(c.value is not None for c in cells):
                    continue
                try:
                    if any(c.data_type in ('f', 'e') for c in cells):
                        raise ValueError('Fórmulas e erros de Excel não são aceitos nos cadastros.')
                    if len(cells) > len(colunas) and any(c.value is not None for c in cells[len(colunas):]):
                        raise ValueError('Há dados fora das colunas previstas.')
                    dados = dict(zip(colunas, [c.value for c in cells]))
                    r = {k: '' for k in CAMPOS}
                    r.update(tipo=tipo, codigo=_codigo(dados['codigo']), nome=_texto(dados['nome']),
                             importacao_origem=aba)
                    if not r['nome'] or len(r['nome']) > 255:
                        raise ValueError('Nome obrigatório, até 255 caracteres.')
                    for campo in esperadas:
                        if campo in ('codigo', 'nome'):
                            continue
                        v = dados.get(campo)
                        destino = {'tipo': 'tipo_conta', 'observacao': 'observacoes'}.get(campo, campo)
                        if campo in ('ativo', 'aceita_lancamento', 'impacta_dre'):
                            v = _sim_nao(v, campo)
                        elif campo in ('codigo_pai', 'conta_contabil_sugerida', 'centro_custo_sugerido'):
                            v = _codigo(v) if v is not None and v != '' else ''
                        elif campo == 'nivel':
                            if isinstance(v, bool) or not re.fullmatch(r'[1-9][0-9]?', str(v)):
                                raise ValueError('Nível deve ser inteiro entre 1 e 99.')
                            v = int(v)
                        else:
                            v = _texto(v)
                        r[destino] = v
                    if r['tipo_conta'] not in ('ANALITICA', 'SINTETICA'):
                        raise ValueError('Tipo deve ser ANALITICA ou SINTETICA.')
                    if r['tipo_conta'] == 'SINTETICA' and r['aceita_lancamento'] == 'Sim':
                        raise ValueError('Conta sintética não pode aceitar lançamento.')
                    if tipo == 'Plano de contas' and r['natureza_saldo'] not in ('DEVEDORA', 'CREDORA'):
                        raise ValueError('Natureza de saldo inválida.')
                    if tipo == 'Natureza financeira' and r['fluxo'] not in ('ENTRADA', 'SAIDA', 'MISTO'):
                        raise ValueError('Fluxo deve ser ENTRADA, SAIDA ou MISTO.')
                    r['_linha'] = numero
                    registros.append(r)
                except (ValueError, KeyError) as ex:
                    erros.append(f'{aba}, linha {numero}: {ex}')
        if not lidas:
            erros.append('Nenhuma das três abas de cadastro foi encontrada.')
        if not registros and not erros:
            erros.append('As abas de cadastro estão vazias.')
        if erros:
            raise ValueError('\n'.join(erros[:30]))
        return registros
    finally:
        wb.close()


def _chave(r):
    return (r['tipo'], normalizar(r.get('codigo')))


def _dados(r):
    return {k: r.get(k) if r.get(k) is not None else '' for k in CAMPOS}


def _indice(registros):
    indice = {}
    for r in registros:
        if r.get('tipo') not in TIPOS or not r.get('codigo'):
            continue
        chave = _chave(r)
        if chave in indice:
            raise ValueError(f'Código duplicado em {r["tipo"]}: {r["codigo"]}. Corrija antes de importar.')
        indice[chave] = r
    return indice


def validar_vinculos(registros):
    indice = _indice(registros)
    for r in registros:
        if not r.get('tipo_conta'):
            continue  # cadastro legado não é convertido silenciosamente
        pai = r.get('codigo_pai')
        if pai:
            p = indice.get((r['tipo'], normalizar(pai)))
            if not p or p.get('tipo_conta') != 'SINTETICA':
                raise ValueError(f'{r["codigo"]}: pai {pai} inexistente ou não sintético.')
            if int(r['nivel']) != int(p['nivel']) + 1:
                raise ValueError(f'{r["codigo"]}: nível incompatível com o pai {pai}.')
        elif int(r['nivel']) != 1:
            raise ValueError(f'{r["codigo"]}: cadastro sem pai precisa ter nível 1.')
        for campo, tipo in (('conta_contabil_sugerida', 'Plano de contas'), ('centro_custo_sugerido', 'Centro de custo')):
            codigo = r.get(campo)
            if codigo:
                alvo = indice.get((tipo, normalizar(codigo)))
                if not alvo or alvo.get('tipo_conta') != 'ANALITICA' or alvo.get('aceita_lancamento') != 'Sim':
                    raise ValueError(f'{r["codigo"]}: {campo} {codigo} inexistente ou não aceita lançamento.')


def carregar_cadastros(conectar):
    conn = conectar()
    try:
        c = conn.cursor()
        c.execute('SELECT * FROM financeiro_cadastros_aux ORDER BY tipo, codigo, id')
        return [dict(r) for r in c.fetchall()]
    finally:
        conn.close()


def preparar_importacao(novos, existentes):
    antigos = _indice(existentes)
    recebidos = _indice(novos)
    combinado = {**antigos, **recebidos}
    validar_vinculos(list(combinado.values()))
    itens = []
    for chave, r in recebidos.items():
        anterior = antigos.get(chave)
        acao = 'Novo' if anterior is None else ('Sem alteração' if _dados(anterior) == _dados(r) else 'Atualizar')
        itens.append(dict(registro=r, anterior=anterior, acao=acao))
    # Inclui o estado visto na prévia: nunca sobrescreve alterações concorrentes sem nova revisão.
    base = [{**_dados(r), 'id': r.get('id')} for r in existentes if r.get('tipo') in TIPOS]
    base.sort(key=lambda r: (r['tipo'], str(r['codigo']), str(r['id'])))
    assinatura = hashlib.sha256(json.dumps({'base': base, 'novos': novos}, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()
    return {'itens': itens, 'assinatura': assinatura}


def importar(conectar, conteudo, assinatura, usuario, atualizar=False):
    if not usuario.get('autenticado') or not usuario_tem_permissao('financeiro.cadastros.edit', usuario):
        raise PermissionError('Sem permissão para importar cadastros financeiros.')
    novos = ler_planilha(conteudo)  # repete validação no serviço, não confia na interface
    conn = conectar()
    mysql = hasattr(conn, '_conn')
    lock = False
    try:
        c = conn.cursor()
        if mysql:
            c.execute("SELECT GET_LOCK('dsystem_cadastros_planilha', 10) AS adquirido")
            lock = dict(c.fetchone()).get('adquirido') == 1
            if not lock:
                raise ValueError('Outra importação está em andamento. Tente novamente.')
        else:
            c.execute('BEGIN IMMEDIATE')
        c.execute('SELECT * FROM financeiro_cadastros_aux ORDER BY tipo, codigo, id' + (' FOR UPDATE' if mysql else ''))
        plano = preparar_importacao(novos, [dict(r) for r in c.fetchall()])
        if assinatura != plano['assinatura']:
            raise ValueError('Os cadastros ou o arquivo mudaram. Atualize e confira novamente a prévia.')
        if not atualizar and any(i['acao'] == 'Atualizar' for i in plano['itens']):
            raise ValueError('Confirme a atualização dos códigos existentes apresentados na prévia.')
        agora = datetime.now().isoformat(timespec='seconds')
        resultado = {'Novo': 0, 'Atualizar': 0, 'Sem alteração': 0}
        for item in sorted(plano['itens'], key=lambda i: (TIPOS.index(i['registro']['tipo']), i['registro']['nivel'], i['registro']['codigo'])):
            acao, r = item['acao'], item['registro']
            resultado[acao] += 1
            if acao == 'Sem alteração':
                continue
            valores = tuple(r.get(k, '') for k in CAMPOS)
            if acao == 'Novo':
                c.execute(f'INSERT INTO financeiro_cadastros_aux ({", ".join(CAMPOS)}, criado_por, criado_em) VALUES ({", ".join("?" for _ in range(len(CAMPOS)+2))})',
                          valores + (usuario.get('username', ''), agora))
            else:
                c.execute(f'UPDATE financeiro_cadastros_aux SET {", ".join(k+"=?" for k in CAMPOS)}, alterado_por=?, alterado_em=? WHERE id=?',
                          valores + (usuario.get('username', ''), agora, item['anterior']['id']))
        conn.commit()
        return resultado
    except Exception:
        conn.rollback()
        raise
    finally:
        try:
            if lock:
                c.execute("SELECT RELEASE_LOCK('dsystem_cadastros_planilha')")
                c.fetchone()
        finally:
            conn.close()
