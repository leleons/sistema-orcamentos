"""Importação de catálogo XLSX como rascunhos fiscais, nunca como autorização."""
import hashlib
import io
import json
from datetime import datetime, timezone
from zipfile import ZipFile, BadZipFile

from openpyxl import load_workbook

from dsystem_erp.services.impostos_cadastro import (
    chave_item, empresa_cnpj, codigo_fiscal, ler_cursor,
)
from dsystem_erp.services.permissions import usuario_tem_permissao


def ler_catalogo(conteudo, empresa):
    empresa = empresa_cnpj(empresa)
    if len(conteudo) > 5 * 1024 * 1024:
        raise ValueError('A planilha deve ter no máximo 5 MB.')
    try:
        with ZipFile(io.BytesIO(conteudo)) as z:
            if sum(i.file_size for i in z.infolist()) > 30 * 1024 * 1024:
                raise ValueError('Planilha descompactada muito grande.')
        wb = load_workbook(io.BytesIO(conteudo), read_only=True, data_only=False, keep_links=False)
    except (BadZipFile, KeyError, OSError) as erro:
        raise ValueError('Envie um arquivo Excel .xlsx válido.') from erro
    resultado, vistos = [], set()
    try:
        for aba, tipo, descricao, fiscal in (
            ('Produtos', 'Produto', 'Descrição do Item', 'Código Fiscal (NCM)'),
            ('Serviços', 'Serviço', 'Descrição do Serviço', 'Código Fiscal (LC 116)'),
        ):
            if aba not in wb.sheetnames:
                continue
            ws = wb[aba]
            if ws.max_row > 2001 or ws.max_column > 50:
                raise ValueError(f'{aba}: limite de 2.000 itens e 50 colunas.')
            linhas = ws.iter_rows()
            cab = [str(c.value or '').strip() for c in next(linhas, [])]
            obrigatorios = ['Código SKU', descricao, fiscal, 'CNAE', 'Anexo Simples']
            if any(cab.count(k) != 1 for k in obrigatorios):
                raise ValueError(f'{aba}: confira os cabeçalhos: ' + ', '.join(obrigatorios))
            for numero, cells in enumerate(linhas, 2):
                if not any(c.value is not None for c in cells):
                    continue
                if any(c.data_type == 'f' for c in cells):
                    raise ValueError(f'{aba}, linha {numero}: substitua fórmulas pelos valores antes de importar.')
                valores = {k: str(c.value).strip() if c.value is not None else ''
                           for k, c in zip(cab, cells) if k}
                nome = valores[descricao]
                chave = chave_item(empresa, tipo, nome)
                if chave in vistos:
                    raise ValueError(f'{aba}, linha {numero}: nome duplicado: {nome}.')
                vistos.add(chave)
                anexo = valores['Anexo Simples'].replace('Anexo ', '').strip()
                r = dict(empresa=empresa, tipo=tipo, nome=nome, ativo=False, confirmado=False,
                         cnae=codigo_fiscal(valores['CNAE'], 7, 'CNAE'),
                         anexo=anexo if anexo in ('I', 'III', 'IV', 'V', 'Fator R') else 'Outro',
                         origem_planilha=valores, sku=valores['Código SKU'],
                         importacao_aba=aba, importacao_linha=numero)
                if tipo == 'Produto':
                    r['ncm'] = codigo_fiscal(valores[fiscal], 8, 'NCM')
                    # CFOP interno/interestadual são referências: não escolher operação.
                    if valores.get('Origem') in list('012345678'):
                        r['origem'] = valores['Origem']
                    r['unidade'] = ''
                    pendencias = 'Confirmar CRT, CFOP da operação, CSOSN/CST, unidade, origem e taxas de ICMS/PIS/COFINS. ST não é liberada por esta importação.'
                else:
                    pendencias = 'Informar código nacional completo, ISS aplicável, retenções e parâmetros municipais. A faixa de ISS da planilha não é uma taxa definida.'
                r['pendencias_importacao'] = pendencias
                r['observacoes'] = 'Referências da planilha (não validadas):\n' + '\n'.join(f'{k}: {v}' for k, v in valores.items())
                resultado.append(r)
    finally:
        wb.close()
    if not resultado:
        raise ValueError('Nenhum item encontrado nas abas Produtos ou Serviços.')
    return resultado


def importar_catalogo(conectar, conteudo, empresa, usuario):
    if not usuario_tem_permissao('impostos.edit', usuario):
        raise PermissionError('Sem permissão para importar impostos.')
    regras = ler_catalogo(conteudo, empresa)
    conn = conectar()
    novos = ignorados = 0
    try:
        c = conn.cursor()
        for r in regras:
            chave = chave_item(empresa, r['tipo'], r['nome'])
            if ler_cursor(c, chave) is not None:
                ignorados += 1
                continue
            r.update(atualizado_por=usuario['username'], atualizado_em=datetime.now(timezone.utc).isoformat())
            r['versao'] = hashlib.sha256(json.dumps(r, sort_keys=True).encode()).hexdigest()
            # INSERT somente: nem importação repetida nem concorrente sobrescreve cadastro.
            c.execute('INSERT INTO configuracoes_sistema (chave,valor) VALUES (?,?)',
                      (chave, json.dumps(r, ensure_ascii=False)))
            novos += 1
        conn.commit()
        return novos, ignorados
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
