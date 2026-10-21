"""Leitura segura das notas já autorizadas; nunca emite ou altera notas."""
from datetime import date
from decimal import Decimal
from lxml import etree

from dsystem_erp.services.impostos_cadastro import empresa_cnpj
from dsystem_erp.services.impostos_simples import moeda, ZERO
from dsystem_erp.services.nfe_item_cadastro import nome_normalizado


def extrair_nota(nota, empresa):
    if nota.get('status') != 'Autorizada':
        return None
    xml = nota.get('xml_autorizado')
    if not xml:
        raise ValueError('XML autorizado ausente; ambiente e emitente não comprovados.')
    xml = xml.encode('utf-8') if isinstance(xml, str) else xml
    if len(xml) > 5_000_000 or b'<!DOCTYPE' in xml.upper() or b'<!ENTITY' in xml.upper():
        raise ValueError('XML autorizado inválido.')
    try:
        root = etree.fromstring(xml, etree.XMLParser(resolve_entities=False, no_network=True))
        if nota.get('tipo_nota') == 'Produto':
            ns = {'n': 'http://www.portalfiscal.inf.br/nfe'}
            inf = root.find('.//n:infNFe', ns)
            prot = root.find('.//n:infProt', ns)
            if inf is None or prot is None:
                raise ValueError('XML processado/protocolo da NF-e ausente.')
            get = lambda p: inf.findtext(p, namespaces=ns)
            chave = str(inf.get('Id') or '').removeprefix('NFe')
            if prot.findtext('n:cStat', namespaces=ns) not in ('100', '150') or prot.findtext('n:chNFe', namespaces=ns) != chave:
                raise ValueError('Protocolo da NF-e não corresponde à autorização.')
            if get('n:emit/n:CNPJ') != empresa or get('n:ide/n:tpAmb') != '1':
                return None
            if prot.findtext('n:tpAmb', namespaces=ns) != '1':
                raise ValueError('Ambiente do protocolo difere do XML de produção.')
            competencia = get('n:ide/n:dhEmi') or get('n:ide/n:dEmi')
            simples = get('n:emit/n:CRT') == '1'
            total = moeda(get('n:total/n:ICMSTot/n:vNF'))
            itens = []
            for det in inf.findall('n:det', ns):
                p = det.find('n:prod', ns)
                valor = moeda(p.findtext('n:vProd', namespaces=ns)) - moeda(p.findtext('n:vDesc', default='0', namespaces=ns))
                itens.append({'nome': p.findtext('n:xProd', namespaces=ns), 'valor': valor})
        elif nota.get('tipo_nota') == 'Serviço':
            ns = {'n': 'http://www.sped.fazenda.gov.br/nfse'}
            inf = root.find('n:infNFSe', ns)
            dps = root.find('.//n:infDPS', ns)
            if inf is None or dps is None:
                raise ValueError('XML autorizado da NFS-e Nacional não identificado.')
            get = lambda p: dps.findtext(p, namespaces=ns)
            if get('n:prest/n:CNPJ') != empresa or get('n:tpAmb') != '1':
                return None
            chave = str(inf.get('Id') or '').removeprefix('NFS')
            if not chave or not inf.findtext('n:nNFSe', namespaces=ns):
                raise ValueError('Número/chave da NFS-e ausente.')
            competencia = get('n:dCompet')
            simples = get('n:prest/n:regTrib/n:opSimpNac') == '3'
            total = moeda(get('n:valores/n:vServPrest/n:vServ'))
            # Discriminação livre não permite separar vários serviços com segurança.
            itens = []
        else:
            raise ValueError('Espécie de documento não suportada na apuração.')
        if nota.get('chave_acesso') and nota['chave_acesso'] != chave:
            raise ValueError('Chave cadastrada difere do XML autorizado.')
        data = date.fromisoformat(str(competencia)[:10])
        return dict(id=nota['id'], tipo=nota['tipo_nota'], chave=chave, competencia=data,
                    total=total, itens=itens, simples=simples)
    except (etree.XMLSyntaxError, TypeError, AttributeError, KeyError) as erro:
        raise ValueError('Não foi possível conferir o XML autorizado.') from erro


def base_mensal(notas, empresa, competencia):
    empresa = empresa_cnpj(empresa)
    mes = competencia.strftime('%Y-%m')
    incluidos, pendencias, vistos = [], [], set()
    # Cancelamento conhecido prevalece mesmo se houver linha autorizada duplicada.
    canceladas = {n.get('chave_acesso') for n in notas if n.get('status') == 'Cancelada' and n.get('chave_acesso')}
    for nota in notas:
        try:
            n = extrair_nota(nota, empresa)
            if not n or n['competencia'].strftime('%Y-%m') != mes or n['chave'] in canceladas:
                continue
            identidade = (n['tipo'], n['chave'])
            if identidade in vistos:
                continue
            vistos.add(identidade)
            incluidos.append(n)
        except ValueError as erro:
            # Sem XML não é seguro decidir a competência/empresa. Exibir pendência,
            # não somar receita presumida nem tratá-la como zero confirmado.
            pendencias.append(f"Nota #{nota.get('id')}: {erro}")
    return incluidos, pendencias


def segregar(notas, snapshots, regras, *, permitir_cadastro_atual=False):
    receitas, pendencias = {}, []
    for nota in notas:
        if not nota.get('simples'):
            pendencias.append(f"Nota #{nota['id']}: regime do emitente no XML não é Simples Nacional ME/EPP; requer apuração específica.")
            continue
        itens = snapshots.get(str(nota['id']))
        if itens is None and permitir_cadastro_atual and nota['itens']:
            itens = []
            for item in nota['itens']:
                candidatas = [r for r in regras if r['tipo'] == nota['tipo']
                              and nome_normalizado(r['nome']) == nome_normalizado(item['nome']) and r.get('ativo', True)]
                if len(candidatas) == 1:
                    itens.append(dict(item, regra=candidatas[0]))
        if not itens or sum((moeda(i['valor']) for i in itens), ZERO) != nota['total']:
            pendencias.append(f"Nota #{nota['id']}: falta classificação fiscal histórica ou os itens não fecham com o total (frete/descontos/ajustes).")
            continue
        grupos = {}
        for item in itens:
            r = item['regra']
            especial = (not r.get('confirmado') or r.get('operacao_especial') or r.get('anexo') not in ('I', 'III', 'V', 'Fator R')
                        or r.get('csosn') == '500' or str(r.get('tipo_retencao_issqn', '1')) != '1'
                        or Decimal(str(r.get('retencao_inss') or 0)) > 0)
            if especial:
                pendencias.append(f"Nota #{nota['id']}: {item['nome']} exige segregação/retenções pela contabilidade; não calculado como operação comum.")
                break
            grupos[r['anexo']] = grupos.get(r['anexo'], ZERO) + moeda(item['valor'])
        else:
            for anexo, valor in grupos.items():
                receitas[anexo] = receitas.get(anexo, ZERO) + valor
    return receitas, pendencias


def carregar_base(conectar, empresa, competencia):
    from dsystem_erp.services.impostos_cadastro import ler_cursor
    conn = conectar()
    try:
        c = conn.cursor()
        c.execute("SELECT id,tipo_nota,status,xml_autorizado,chave_acesso FROM notas_fiscais WHERE status IN ('Autorizada','Cancelada')")
        notas, pendencias = base_mensal(c.fetchall(), empresa, competencia)
        snapshots = {}
        for nota in notas:
            snap = ler_cursor(c, f'IMPOSTO_NOTA_{empresa}_{nota["id"]}')
            if snap:
                snapshots[str(nota['id'])] = snap['itens']
        return notas, snapshots, pendencias
    finally:
        conn.close()


def classificar_historica(conectar, empresa, nota_id, linhas, usuario):
    """Classificação gerencial explícita de nota antiga; preserva XML e status."""
    from datetime import datetime, timezone
    from dsystem_erp.services.permissions import usuario_tem_permissao
    from dsystem_erp.services.impostos_cadastro import ler_cursor, gravar_cursor, regras_itens
    if not usuario_tem_permissao('impostos.edit', usuario):
        raise PermissionError('Sem permissão para classificar notas históricas.')
    empresa = empresa_cnpj(empresa)
    conn = conectar()
    try:
        c = conn.cursor()
        c.execute('SELECT * FROM notas_fiscais WHERE id=? FOR UPDATE', (nota_id,))
        row = c.fetchone()
        nota = extrair_nota(row or {}, empresa)
        if not nota:
            raise ValueError('Nota não autorizada em produção para este emitente.')
        chave = f'IMPOSTO_NOTA_{empresa}_{nota_id}'
        if ler_cursor(c, chave) is not None:
            raise ValueError('Esta nota já possui histórico fiscal; o registro original será preservado.')
        if not linhas or sum((moeda(i['valor']) for i in linhas), ZERO) != nota['total']:
            raise ValueError('A soma da classificação deve corresponder exatamente ao valor da nota.')
        itens = [dict(desc=i['nome'], vtotal=moeda(i['valor']), tipo_item=nota['tipo']) for i in linhas]
        pares = regras_itens(c, empresa, itens, nota['tipo'])
        if any(i['vtotal'] <= 0 for i in itens):
            raise ValueError('Informe valor positivo para cada classificação.')
        gravar_cursor(c, chave, dict(itens=[dict(nome=i['desc'], valor=str(i['vtotal']), regra=r) for i,r in pares],
                     origem='classificacao_historica_manual', autor=usuario['username'],
                     registrado_em=datetime.now(timezone.utc).isoformat(), chave_nota=nota['chave']))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
