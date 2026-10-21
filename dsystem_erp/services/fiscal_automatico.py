"""Emissão opt-in por faturamento, com preparação persistida e trava de reenvio.

Não é um agendador: roda no clique de faturar. Transmitindo/Conferir nunca são
reenviados automaticamente, mesmo após reinício do processo.
"""
import hashlib
import json
import re
from datetime import date
from decimal import Decimal

from dsystem_erp.services.nfe_produto import (
    gerar_xml_nfe_produto_400, validar_xml_nfe_produto_minimo, endpoint_autorizacao_nfe,
    assinar_xml_nfe_produto, enviar_xml_nfe_produto, analisar_retorno_nfe_produto,
    sha256_nfe_assinada,
    aplicar_aliquotas_ibscbs_integral,
)
from dsystem_erp.services.nfse_nacional import (
    gerar_xml_dps_nacional, executar_fluxo_nfse_nacional, endpoint_nacional,
    validar_destino_dps, RejeicaoNacionalHTTP,
)
from dsystem_erp.services.nfse_sequencia import proximo_numero_nfse
from dsystem_erp.services.nfe_documento import montar_nfe_processada
from dsystem_erp.services.impostos_cadastro import conferir_plano, salvar_snapshot

ESTADOS_EDITAVEIS = ('Pendente', 'Pronta', 'Rejeitada')


def rejeicao_nfse_corrigivel(resposta):
    erros = resposta.get('erros') if isinstance(resposta, dict) else None
    return isinstance(erros, list) and bool(erros) and all(isinstance(e, dict) and
        (e.get('Codigo') or e.get('codigo')) in {'E0120', 'E0160', 'E0312', 'E0314', 'E0712', 'E0713'}
        for e in erros)


def permite_correcao(registro):
    if registro.get('estado') in ('Pendente', 'Rejeitada'):
        return True
    if registro.get('estado') != 'Conferir' or registro.get('tipo') != 'Serviço':
        return False
    # Compatibilidade com rejeições HTTP antigas que não guardavam o JSON.
    mensagem = str(registro.get('mensagem') or '')
    codigos = re.findall(r'\bE\d{4}\b', mensagem)
    return bool(re.match(r'^API Nacional retornou HTTP (400|422): E\d{4}\b', mensagem)
                and codigos and rejeicao_nfse_corrigivel({'erros': [{'Codigo': c} for c in codigos]}))


def liberar_correcao(conectar, fat_id, tipo, permitido):
    """Libera edição, nunca transmite. Revalida a situação sob a trava do faturamento."""
    if not permitido:
        raise PermissionError('Sem permissão para corrigir emissões.')
    conn = conectar()
    try:
        c = conn.cursor()
        c.execute('SELECT * FROM faturamento WHERE id=? FOR UPDATE', (fat_id,))
        fat = c.fetchone()
        if not fat or fat.get('status') == 'Cancelado':
            raise ValueError('Faturamento indisponível para correção.')
        c.execute('SELECT * FROM fiscal_emissoes_auto WHERE faturamento_id=? AND tipo=? FOR UPDATE', (fat_id, tipo))
        registro = c.fetchone()
        if not registro or not permite_correcao(registro):
            raise ValueError('Resultado incerto ou nota já enviada. Consulte a autorização antes de tentar novamente.')
        c.execute('SELECT * FROM notas_fiscais WHERE faturamento_id=? AND tipo_nota=? FOR UPDATE', (fat_id, tipo))
        notas = c.fetchall()
        for nota in notas:
            if (nota.get('status') not in ('Pendente', 'Rejeitada', 'Conferir', '', None)
                    or nota.get('xml_autorizado') or nota.get('chave_acesso')
                    or (nota.get('status') == 'Conferir' and
                        (nota.get('id') != registro.get('nota_id') or not permite_correcao(dict(registro, estado='Conferir'))))):
                raise ValueError('Existe nota autorizada, enviada ou em conferência. Não é seguro liberar outro envio.')
        c.execute("UPDATE notas_fiscais SET status='Rejeitada' WHERE faturamento_id=? AND tipo_nota=?", (fat_id, tipo))
        c.execute("UPDATE fiscal_emissoes_auto SET estado='Pendente',origem_hash=NULL WHERE id=?", (registro['id'],))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def desativar_emissao_automatica(conectar, fat_id):
    """Troca somente o modo, sem limpar notas, planos ou travas de envio."""
    conn = conectar()
    try:
        c = conn.cursor()
        c.execute('SELECT * FROM faturamento WHERE id=? FOR UPDATE', (fat_id,))
        fat = c.fetchone()
        if not fat or fat.get('status') not in ('Aberto', 'Faturado'):
            raise ValueError('Faturamento indisponível para emissão manual.')
        c.execute('SELECT status FROM notas_fiscais WHERE faturamento_id=?', (fat_id,))
        if any(n.get('status') not in ('Pendente', 'Rejeitada', 'Autorizada', 'Cancelada', '', None) for n in c.fetchall()):
            raise ValueError('Existe nota em transmissão ou em conferência. Consulte o resultado antes de trocar o modo.')
        c.execute('SELECT estado FROM fiscal_emissoes_auto WHERE faturamento_id=?', (fat_id,))
        if any(n.get('estado') not in ('Pendente', 'Pronta', 'Rejeitada', 'Autorizada') for n in c.fetchall()):
            raise ValueError('Existe emissão automática em transmissão ou em conferência. Consulte o resultado antes de trocar o modo.')
        c.execute('UPDATE faturamento SET emitir_automaticamente=0 WHERE id=?', (fat_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def iniciar_envio_manual(conectar, fat_id, nota_id, *, plano_impostos=None):
    """Usa a mesma trava do automático antes de iniciar um envio manual."""
    conn = conectar()
    try:
        c = conn.cursor()
        c.execute('SELECT * FROM faturamento WHERE id=? FOR UPDATE', (fat_id,))
        fat = c.fetchone()
        if not fat or fat.get('status') != 'Faturado':
            raise ValueError('Fature o lançamento antes de emitir a nota.')
        if fat.get('emitir_automaticamente'):
            raise ValueError('Emissão automática ativada. Use Continuar notas preparadas, ou desative a opção antes do envio manual.')
        c.execute('SELECT * FROM notas_fiscais WHERE id=? AND faturamento_id=? FOR UPDATE', (nota_id, fat_id))
        nota = c.fetchone()
        if not nota or nota.get('status') not in ('Pendente', 'Rejeitada', '', None):
            raise ValueError('Nota já enviada ou em conferência. Consulte o resultado antes de qualquer novo envio.')
        c.execute('SELECT status FROM notas_fiscais WHERE faturamento_id=? AND tipo_nota=? AND id<>?',
                  (fat_id, nota['tipo_nota'], nota_id))
        if any(r.get('status') not in ('Pendente', 'Rejeitada', '', None) for r in c.fetchall()):
            raise ValueError('Já existe outra nota enviada deste tipo para o lançamento.')
        c.execute('SELECT estado FROM fiscal_emissoes_auto WHERE faturamento_id=? AND tipo=?', (fat_id, nota['tipo_nota']))
        registro = c.fetchone()
        if registro and registro['estado'] not in ESTADOS_EDITAVEIS:
            raise ValueError('Emissão anterior enviada ou em conferência. Consulte o resultado.')
        if plano_impostos is None:
            raise ValueError('Confira o cadastro de impostos antes do envio manual.')
        validar_plano(fat, nota['tipo_nota'], plano_impostos)
        empresa_impostos, snapshot_impostos = conferir_plano(c, fat, nota['tipo_nota'], plano_impostos)
        salvar_snapshot(c, empresa_impostos, nota_id, snapshot_impostos)
        c.execute("UPDATE notas_fiscais SET status='Transmitindo',mensagem_retorno=? WHERE id=?",
                  ('Envio manual iniciado. Não reenviar sem conferir o resultado.', nota_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def registrar_xml_manual(conectar, nota_id, xml):
    conn = conectar()
    try:
        c = conn.cursor()
        c.execute("UPDATE notas_fiscais SET xml_envio=? WHERE id=? AND status='Transmitindo'", (xml.decode('utf-8'), nota_id))
        conn.commit()
    finally:
        conn.close()


def registrar_falha_manual(conectar, nota_id, erro, enviou):
    conn = conectar()
    try:
        c = conn.cursor()
        c.execute("UPDATE notas_fiscais SET status=?,mensagem_retorno=? WHERE id=? AND status='Transmitindo'",
                  ('Conferir' if enviou else 'Pendente', str(erro), nota_id))
        conn.commit()
    finally:
        conn.close()


def itens_lista(faturamento):
    itens = faturamento.get('itens') or []
    return json.loads(itens) if isinstance(itens, str) else list(itens)


def tipos_fiscais(faturamento):
    if faturamento.get('emite_nf') != 'Sim' or faturamento.get('documentos_entrega') == 'Somente espelho':
        return []
    tipos = {i.get('tipo_item') or 'Serviço' for i in itens_lista(faturamento)}
    if tipos - {'Serviço', 'Produto'}:
        raise ValueError('Há itens sem tipo fiscal reconhecido. Revise Produto/Serviço.')
    return [tipo for tipo in ('Serviço', 'Produto') if tipo in tipos]


def hash_origem(fat):
    def numero(valor, casas=None):
        decimal = Decimal(str(valor or 0))
        if casas:
            decimal = decimal.quantize(Decimal(casas))
        return str(decimal.normalize())

    origem = {k: fat.get(k) or '' for k in ('cliente', 'cnpj', 'obs_nota', 'emite_nf', 'documentos_entrega')}
    origem['valor_total'] = numero(fat.get('valor_total'), '0.01')
    origem['cnpj'] = ''.join(filter(str.isdigit, str(origem['cnpj'])))
    origem['documentos_entrega'] = origem['documentos_entrega'] or 'Nota e espelho'
    origem['itens'] = []
    for item in itens_lista(fat):
        # A tela de edição acrescenta campos opcionais vazios e usa floats.
        # Essas diferenças de representação não alteram a conferência fiscal.
        normalizado = {k: v for k, v in item.items() if v is not None and v != ''}
        normalizado['tipo_item'] = item.get('tipo_item') or 'Serviço'
        for k in ('qtd', 'vunit', 'vtotal'):
            normalizado[k] = numero(item.get(k), '0.01' if k == 'vtotal' else None)
        origem['itens'].append(normalizado)
    return hashlib.sha256(json.dumps(origem, sort_keys=True, default=str, ensure_ascii=False).encode()).hexdigest()


def atualizar_taxas_tabeladas(plano, tipo):
    """Completa taxas fixas antes da assinatura; preserva o plano de origem."""
    import copy
    atualizado = copy.deepcopy(plano)
    if tipo == 'Produto':
        atualizado['itens'] = [aplicar_aliquotas_ibscbs_integral(i, date.today().year)
                              for i in atualizado.get('itens') or []]
        dados = atualizado.get('dados') or {}
        if dados.get('ibscbs'):
            dados['ibscbs'] = aplicar_aliquotas_ibscbs_integral({'ibscbs': dados['ibscbs']}, date.today().year)['ibscbs']
    return atualizado


def validar_plano(fat, tipo, plano):
    if tipo not in tipos_fiscais(fat):
        raise ValueError('Este lançamento não prevê nota deste tipo.')
    dados = plano['dados']
    if dados.get('ambiente') not in ('homologacao', 'producao'):
        raise ValueError('Confirme o ambiente da emissão.')
    emitente = ''.join(c for c in str(dados.get('cnpj_prestador') or dados.get('emitente_cnpj') or '') if c.isdigit())
    if len(emitente) != 14:
        raise ValueError('CNPJ do emitente incompleto.')
    origem = [i for i in itens_lista(fat) if (i.get('tipo_item') or 'Serviço') == tipo]
    total = sum(Decimal(str(i.get('vtotal') or 0)).quantize(Decimal('0.01')) for i in origem)
    if total <= 0:
        raise ValueError('Valor da nota deve ser positivo.')
    if tipo == 'Serviço':
        if Decimal(str(dados.get('valor') or 0)).quantize(Decimal('0.01')) != total:
            raise ValueError('Valor da NFS-e difere do total de serviços. Revise a preparação.')
        xml = gerar_xml_dps_nacional(plano['faturamento'], dados)
        validar_destino_dps(plano['endpoint'], xml)
    else:
        preparados = plano.get('itens') or []
        campos = ('desc', 'qtd', 'vunit', 'vtotal')
        normalizar = lambda item: tuple(str(item.get(k) or '') if k == 'desc' else Decimal(str(item.get(k) or 0)) for k in campos)
        if list(map(normalizar, preparados)) != list(map(normalizar, origem)):
            raise ValueError('Produtos preparados diferem dos itens do faturamento. Confira novamente.')
        esperado = endpoint_autorizacao_nfe(dados.get('uf') or '', dados['ambiente'])
        if not esperado or plano['endpoint'].rstrip('/') != esperado:
            raise ValueError('Emissão automática de produto requer endpoint SEFAZ suportado para UF/ambiente.')
        xml = gerar_xml_nfe_produto_400(plano['faturamento'], preparados, dados)
        erros = validar_xml_nfe_produto_minimo(xml, dados, preparados)
        for campo in ('logradouro', 'numero', 'bairro', 'municipio', 'cep'):
            if not str(dados.get(f'emitente_{campo}') or '').strip():
                erros.append(f'Preencha o endereço do emitente: {campo}.')
        if erros:
            raise ValueError(' '.join(erros))
    if ''.join(filter(str.isdigit, str(plano['faturamento'].get('cnpj') or ''))) != ''.join(filter(str.isdigit, str(fat.get('cnpj') or ''))):
        raise ValueError('Documento do cliente difere do faturamento. Corrija o cadastro antes de preparar.')


def listar_emissoes(conectar, fat_id):
    conn = conectar()
    try:
        c = conn.cursor()
        c.execute('SELECT * FROM fiscal_emissoes_auto WHERE faturamento_id=? ORDER BY tipo', (fat_id,))
        return [dict(r) for r in c.fetchall()]
    finally:
        conn.close()


def recuperar_pdfs(conectar, fat_id):
    """Gera somente PDFs ausentes a partir do XML autorizado salvo. Sem rede."""
    import base64
    from dsystem_erp.services.nfe_documento import gerar_danfe_autorizado
    from dsystem_erp.services.danfse_local import gerar_danfse_local
    from dsystem_erp.services.danfse import conferir_xml_nacional, url_consulta_publica
    from dsystem_erp.services.fiscal_documentos import pdf_da_nota
    conn = conectar()
    gerados = 0
    erros = []
    try:
        c = conn.cursor()
        c.execute("SELECT * FROM notas_fiscais WHERE faturamento_id=? AND status='Autorizada'", (fat_id,))
        for nota in c.fetchall():
            if pdf_da_nota(nota):
                continue
            xml = nota.get('xml_autorizado') or ''
            xml = xml.encode() if isinstance(xml, str) else bytes(xml)
            link = nota.get('link_nota') or ''
            try:
                if nota['tipo_nota'] == 'Produto':
                    pdf = gerar_danfe_autorizado(xml)
                else:
                    dados = conferir_xml_nacional(xml, nota.get('chave_acesso') or '')
                    pdf = gerar_danfse_local({'xml_autorizado': xml, 'chave_acesso': dados['chave']})
                    link = url_consulta_publica(dados['chave'], dados['ambiente'])
            except Exception as erro_pdf:
                erros.append(f"{nota['tipo_nota']} #{nota['id']}: {erro_pdf}")
                continue
            c.execute("UPDATE notas_fiscais SET pdf_base64=?,link_nota=? WHERE id=? AND status='Autorizada'",
                      (base64.b64encode(pdf).decode('ascii'), link, nota['id']))
            gerados += 1
        conn.commit()
        if erros:
            raise ValueError('PDF pendente, sem reemitir nota: ' + '; '.join(erros))
        return gerados
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def salvar_plano(conectar, fat_id, tipo, dados, itens, fat_dados, endpoint, usuario):
    # Senha/certificado nunca são persistidos com o plano.
    dados = {k: v for k, v in dados.items() if not any(p in k.lower() for p in ('password', 'senha', 'cert_path'))}
    plano = dict(dados=dados, itens=itens, faturamento={k: fat_dados.get(k) for k in ('id', 'cliente', 'cnpj', 'telefone', 'email')}, endpoint=endpoint)
    plano = atualizar_taxas_tabeladas(plano, tipo)
    conn = conectar()
    try:
        c = conn.cursor()
        c.execute('SELECT * FROM faturamento WHERE id=? FOR UPDATE', (fat_id,))
        fat = c.fetchone()
        if not fat or fat.get('status') == 'Cancelado':
            raise ValueError('Faturamento não está disponível para emissão.')
        conferir_plano(c, fat, tipo, plano, preparar=True)
        validar_plano(fat, tipo, plano)
        c.execute('SELECT estado FROM fiscal_emissoes_auto WHERE faturamento_id=? AND tipo=? FOR UPDATE', (fat_id, tipo))
        atual = c.fetchone()
        if atual and atual['estado'] not in ESTADOS_EDITAVEIS:
            raise ValueError('Nota enviada ou em conferência. Não prepare uma nova emissão.')
        c.execute('SELECT status FROM notas_fiscais WHERE faturamento_id=? AND tipo_nota=?', (fat_id, tipo))
        if any(r.get('status') not in ('Pendente', 'Rejeitada', None, '') for r in c.fetchall()):
            raise ValueError('Já existe nota enviada deste tipo; consulte o retorno antes de continuar.')
        c.execute('''INSERT INTO fiscal_emissoes_auto (faturamento_id,tipo,estado,plano_json,origem_hash,mensagem,autorizado_por)
                     VALUES (?,?,'Pronta',?,?,?,?) ON DUPLICATE KEY UPDATE estado='Pronta',
                     plano_json=VALUES(plano_json), origem_hash=VALUES(origem_hash), mensagem=VALUES(mensagem),
                     autorizado_por=VALUES(autorizado_por), atualizado_em=CURRENT_TIMESTAMP''',
                  (fat_id, tipo, json.dumps(plano, ensure_ascii=False, default=str), hash_origem(fat),
                   f"Conferida para {dados['ambiente']}; aguardando faturamento.", usuario))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _atualizar(conectar, registro_id, **campos):
    permitidos = {'estado', 'mensagem', 'xml_envio', 'xml_retorno', 'nota_id'}
    if not set(campos) <= permitidos:
        raise ValueError('Campo inválido.')
    conn = conectar()
    try:
        c = conn.cursor()
        c.execute('UPDATE fiscal_emissoes_auto SET ' + ','.join(f'{k}=?' for k in campos) + ',atualizado_em=CURRENT_TIMESTAMP WHERE id=?', tuple(campos.values()) + (registro_id,))
        conn.commit()
    finally:
        conn.close()


def reservar_numero_produto(conectar, dados):
    """Sequência separada por ambiente/CNPJ/série; sem usar ID do faturamento."""
    from lxml import etree
    from dsystem_erp.services.nfe_produto import NFE_NS
    cnpj = ''.join(filter(str.isdigit, str(dados['emitente_cnpj'])))
    serie = int(dados.get('serie') or 1)
    ambiente = '1' if dados['ambiente'] == 'producao' else '2'
    chave = f"nfe:{dados['ambiente']}:{cnpj}:{serie}"
    conn = conectar()
    try:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS nfse_sequencias (chave VARCHAR(255) PRIMARY KEY,
                     ultimo_numero BIGINT NOT NULL DEFAULT 0, atualizado_em DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        c.execute('''INSERT INTO nfse_sequencias (chave,ultimo_numero) VALUES (?,0)
                     ON DUPLICATE KEY UPDATE chave=VALUES(chave)''', (chave,))
        c.execute('SELECT ultimo_numero FROM nfse_sequencias WHERE chave=? FOR UPDATE', (chave,))
        maior = max(int(c.fetchone()['ultimo_numero']), int(dados.get('numero') or 1) - 1)
        c.execute("SELECT xml_envio FROM notas_fiscais WHERE tipo_nota='Produto' AND xml_envio IS NOT NULL")
        for row in c.fetchall():
            try:
                root = etree.fromstring(str(row['xml_envio']).encode(), etree.XMLParser(resolve_entities=False, no_network=True))
                ns = {'n': NFE_NS}
                get = lambda p: root.findtext('.//n:infNFe/' + p, namespaces=ns)
                if get('n:emit/n:CNPJ') == cnpj and get('n:ide/n:tpAmb') == ambiente and int(get('n:ide/n:serie') or 0) == serie:
                    maior = max(maior, int(get('n:ide/n:nNF') or 0))
            except (ValueError, etree.XMLSyntaxError):
                continue
        if maior >= 999999999:
            raise ValueError('Numeração NF-e esgotada para esta série.')
        c.execute('UPDATE nfse_sequencias SET ultimo_numero=? WHERE chave=?', (maior + 1, chave))
        conn.commit()
        return maior + 1
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _reivindicar(conectar, fat_id, tipo):
    conn = conectar()
    try:
        c = conn.cursor()
        c.execute('SELECT * FROM faturamento WHERE id=? FOR UPDATE', (fat_id,))
        fat = c.fetchone()
        if not fat or fat.get('status') != 'Faturado' or not fat.get('emitir_automaticamente') or tipo not in tipos_fiscais(fat):
            return None
        c.execute('''INSERT INTO fiscal_emissoes_auto (faturamento_id,tipo,estado,mensagem) VALUES (?,?,'Pendente',?)
                     ON DUPLICATE KEY UPDATE faturamento_id=VALUES(faturamento_id)''',
                  (fat_id, tipo, 'Falta configuração fiscal reutilizável para este cliente e itens. Configure uma vez em A faturar.'))
        c.execute('SELECT * FROM fiscal_emissoes_auto WHERE faturamento_id=? AND tipo=? FOR UPDATE', (fat_id, tipo))
        registro = dict(c.fetchone())
        if registro['estado'] != 'Pronta':
            conn.commit()
            return None
        if registro['origem_hash'] != hash_origem(fat):
            c.execute("UPDATE fiscal_emissoes_auto SET estado='Pendente',mensagem=? WHERE id=?",
                      ('Lançamento alterado após a conferência. Revise e salve novamente a preparação.', registro['id']))
            conn.commit()
            return None
        c.execute('SELECT * FROM notas_fiscais WHERE faturamento_id=? AND tipo_nota=? FOR UPDATE', (fat_id, tipo))
        notas = c.fetchall()
        bloqueada = next((r for r in notas if r.get('status') not in ('Pendente', 'Rejeitada', '', None)), None)
        if bloqueada:
            c.execute('UPDATE fiscal_emissoes_auto SET estado=?,mensagem=?,nota_id=? WHERE id=?',
                      ('Autorizada' if bloqueada['status'] == 'Autorizada' else 'Conferir',
                       'Nota existente preservada; não será reenviada.', bloqueada['id'], registro['id']))
            conn.commit()
            return None
        plano = atualizar_taxas_tabeladas(json.loads(registro['plano_json']), tipo)
        empresa_impostos, snapshot_impostos = conferir_plano(c, fat, tipo, plano)
        validar_plano(fat, tipo, plano)
        if notas:
            nota_id = notas[0]['id']
        else:
            itens = [i for i in itens_lista(fat) if (i.get('tipo_item') or 'Serviço') == tipo]
            c.execute('''INSERT INTO notas_fiscais (faturamento_id,cliente,cpf_cnpj,tipo_nota,status,
                         valor_servicos,descricao,data_competencia,criado_por,criado_em) VALUES (?,?,?,?,'Pendente',?,?,?,?,?)''',
                      (fat_id, fat.get('cliente'), fat.get('cnpj'), tipo,
                       sum(float(i.get('vtotal') or 0) for i in itens), '\n'.join(str(i.get('desc') or '') for i in itens),
                       plano['dados'].get('competencia'), registro.get('autorizado_por'), date.today().isoformat()))
            nota_id = c.lastrowid
        salvar_snapshot(c, empresa_impostos, nota_id, snapshot_impostos)
        c.execute("UPDATE fiscal_emissoes_auto SET estado='Transmitindo',nota_id=?,mensagem=?,plano_json=? WHERE id=?",
                  (nota_id, 'Emissão iniciada. Se interrompida, consulte a nota antes de reenviar.',
                   json.dumps(plano, ensure_ascii=False, default=str), registro['id']))
        c.execute("UPDATE notas_fiscais SET status='Transmitindo' WHERE id=?", (nota_id,))
        conn.commit()  # trava durável ANTES de acessar a rede
        return registro, plano, nota_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def preparar_antes_de_faturar(conectar, fat_id, config):
    """Confere ambas as espécies antes da baixa financeira/estoque. Não transmite."""
    conn = conectar()
    try:
        c = conn.cursor()
        c.execute('SELECT * FROM faturamento WHERE id=?', (fat_id,))
        fat = c.fetchone()
        if not fat or fat.get('status') in ('Faturado', 'Cancelado'):
            raise ValueError('Lançamento já faturado, cancelado ou indisponível.')
    finally:
        conn.close()
    pendencias, ambientes = [], set()
    from dsystem_erp.services.fiscal_modelos import preparar_por_modelo
    from dsystem_erp.services.nfse_certificado import certificado_bate_com_cnpj, inspecionar_certificado_pfx
    info_cert = None
    for tipo in tipos_fiscais(fat):
        try:
            registro = next((r for r in listar_emissoes(conectar, fat_id) if r['tipo'] == tipo), None)
            if not registro or (registro['estado'] == 'Pendente' and not registro.get('plano_json')):
                if not preparar_por_modelo(conectar, fat, tipo, config):
                    raise ValueError('falta configuração fiscal autorizada para este cliente e itens. Configure uma vez em A faturar.')
                registro = next(r for r in listar_emissoes(conectar, fat_id) if r['tipo'] == tipo)
            if registro['estado'] != 'Pronta':
                raise ValueError(registro.get('mensagem') or 'confira/corrija a tentativa anterior antes de continuar.')
            if registro.get('origem_hash') != hash_origem(fat):
                raise ValueError('lançamento alterado após a conferência; revise a configuração fiscal.')
            plano = atualizar_taxas_tabeladas(json.loads(registro['plano_json']), tipo)
            conn_impostos = conectar()
            try:
                conferir_plano(conn_impostos.cursor(), fat, tipo, plano)
            finally:
                conn_impostos.close()
            validar_plano(fat, tipo, plano)
            if info_cert is None:
                info_cert = inspecionar_certificado_pfx(config('NFSE_CERT_PFX_PATH', ''), config('NFSE_CERT_PASSWORD', ''))
            dados = plano['dados']
            if info_cert.get('vencido') or not certificado_bate_com_cnpj(info_cert, dados.get('cnpj_prestador') or dados.get('emitente_cnpj')):
                raise ValueError('certificado inválido, vencido ou diferente do emitente.')
            ambientes.add(dados['ambiente'])
        except Exception as erro:
            pendencias.append(f'{tipo}: {erro}')
    if len(ambientes) > 1:
        pendencias.append('Produto e serviço precisam estar no mesmo ambiente de emissão.')
    if pendencias:
        raise ValueError('Não foi faturado nem enviado. ' + ' | '.join(pendencias))
    return hash_origem(fat)


def processar_emissoes(conectar, fat_id, config, salvar_retorno):
    conn = conectar()
    try:
        c = conn.cursor()
        c.execute('SELECT * FROM faturamento WHERE id=?', (fat_id,))
        fat = c.fetchone() or {}
    finally:
        conn.close()
    if not fat.get('emitir_automaticamente'):
        return []
    for tipo in tipos_fiscais(fat):
        try:
            reivindicacao = _reivindicar(conectar, fat_id, tipo)
            if not reivindicacao:
                existente = next((r for r in listar_emissoes(conectar, fat_id) if r['tipo'] == tipo), None)
                if existente and existente['estado'] == 'Pendente' and not existente.get('plano_json'):
                    from dsystem_erp.services.fiscal_modelos import preparar_por_modelo
                    try:
                        if preparar_por_modelo(conectar, fat, tipo, config):
                            reivindicacao = _reivindicar(conectar, fat_id, tipo)
                    except Exception as erro_modelo:
                        _atualizar(conectar, existente['id'], estado='Pendente', mensagem=str(erro_modelo))
        except ValueError as erro_plano:
            existente = next((r for r in listar_emissoes(conectar, fat_id) if r['tipo'] == tipo), None)
            if existente and existente['estado'] in ESTADOS_EDITAVEIS:
                _atualizar(conectar, existente['id'], estado='Pendente', mensagem=str(erro_plano))
            continue
        if not reivindicacao:
            continue
        registro, plano, nota_id = reivindicacao
        xml_enviado = b''
        enviou = False

        def antes_envio(xml):
            nonlocal xml_enviado, enviou
            texto = xml.decode('utf-8')
            _atualizar(conectar, registro['id'], xml_envio=texto)
            conn_envio = conectar()
            try:
                cenvio = conn_envio.cursor()
                cenvio.execute('UPDATE notas_fiscais SET xml_envio=? WHERE id=?', (texto, nota_id))
                conn_envio.commit()
            finally:
                conn_envio.close()
            xml_enviado, enviou = xml, True

        try:
            dados = plano['dados']
            cert = config('NFSE_CERT_PFX_PATH', '')
            senha = config('NFSE_CERT_PASSWORD', '')
            from dsystem_erp.services.nfse_certificado import certificado_bate_com_cnpj, inspecionar_certificado_pfx
            info_cert = inspecionar_certificado_pfx(cert, senha)
            if info_cert.get('vencido') or not certificado_bate_com_cnpj(info_cert, dados.get('cnpj_prestador') or dados.get('emitente_cnpj')):
                raise ValueError('Certificado não corresponde ao emitente. Revise a configuração.')
            if tipo == 'Serviço':
                dados['numero_dps'] = proximo_numero_nfse(conectar, ambiente=dados['ambiente'], cnpj=dados['cnpj_prestador'], serie=dados['serie_dps'], reservar=True)
                resultado = executar_fluxo_nfse_nacional(plano['faturamento'], dados, endpoint=plano['endpoint'],
                    cert_path=cert, cert_password=senha, antes_envio=antes_envio)
                retorno = resultado.xml_nfse or b''
                info = dict(status=resultado.status, mensagem=resultado.mensagem, protocolo=resultado.id_dps,
                            chave_acesso=resultado.chave_acesso, numero_nfse=resultado.numero_nfse)
                if info['status'] == 'Rejeitada' and not rejeicao_nfse_corrigivel(resultado.resposta_json):
                    info['status'] = 'Conferir'
                    info['mensagem'] += ' Consulte este retorno antes de preparar outro envio.'
                if info['status'] == 'Autorizada':
                    from dsystem_erp.services.danfse import conferir_xml_nacional
                    conferido = conferir_xml_nacional(retorno, info['chave_acesso'])
                    if conferido['ambiente'] != ('1' if dados['ambiente'] == 'producao' else '2'):
                        raise ValueError('Retorno de outro ambiente. Consulte antes de continuar.')
                    from lxml import etree
                    from dsystem_erp.services.nfse_nacional import NS_NFSE
                    raiz_retorno = etree.fromstring(retorno, etree.XMLParser(resolve_entities=False, no_network=True))
                    dps_retorno = raiz_retorno.find(f'.//{{{NS_NFSE}}}DPS/{{{NS_NFSE}}}infDPS')
                    dps_enviada = etree.fromstring(xml_enviado).find(f'{{{NS_NFSE}}}infDPS')
                    if dps_retorno is None or dps_retorno.get('Id') != dps_enviada.get('Id'):
                        raise ValueError('A NFS-e retornada não corresponde à DPS enviada. Consulte antes de continuar.')
                if not retorno:
                    retorno = json.dumps(resultado.resposta_json, ensure_ascii=False).encode()
            else:
                dados['numero'] = reservar_numero_produto(conectar, dados)
                xml = gerar_xml_nfe_produto_400(plano['faturamento'], plano['itens'], dados)
                erros = validar_xml_nfe_produto_minimo(xml, dados, plano['itens'])
                if erros:
                    raise ValueError(' '.join(erros))
                xml = assinar_xml_nfe_produto(xml, cert, senha)
                hash_assinado = sha256_nfe_assinada(xml)
                antes_envio(xml)
                retorno = enviar_xml_nfe_produto(plano['endpoint'], xml, cert, senha,
                                               sha256_assinado=hash_assinado)
                info = analisar_retorno_nfe_produto(retorno)
                if info['status'] == 'Autorizada':
                    retorno = montar_nfe_processada(xml, retorno)
            _atualizar(conectar, registro['id'], xml_retorno=retorno.decode('utf-8', errors='replace'))
            if tipo == 'Produto' and info.get('cstat') in ('204', '539'):
                info['status'] = 'Conferir'
            salvar_retorno(nota_id, xml_enviado, retorno, info)
            estado = info['status'] if info['status'] in ('Autorizada', 'Rejeitada') else 'Conferir'
            # Duplicidade pode significar autorização anterior: nunca preparar novo envio.
            if tipo == 'Produto' and info.get('cstat') in ('204', '539'):
                estado = 'Conferir'
            _atualizar(conectar, registro['id'], estado=estado, mensagem=info['mensagem'] +
                (' PDF pendente: ' + str(info['danfse_erro']) if info.get('danfse_erro') else ''))
        except Exception as erro:
            # Rejeição HTTP pode também sinalizar duplicidade. Só libera correção
            # para validações conhecidas; demais retornos requerem conferência.
            rejeitada = (isinstance(erro, RejeicaoNacionalHTTP) and erro.status in (400, 422)
                         and rejeicao_nfse_corrigivel(erro.resposta))
            estado = 'Rejeitada' if rejeitada else ('Conferir' if enviou else 'Pendente')
            mensagem = str(erro) + (' Consulte o resultado antes de qualquer novo envio.' if estado == 'Conferir' else '')
            detalhes = {}
            if isinstance(erro, RejeicaoNacionalHTTP):
                detalhes['xml_retorno'] = json.dumps({'http_status': erro.status, 'resposta': erro.resposta}, ensure_ascii=False)
            _atualizar(conectar, registro['id'], estado=estado, mensagem=mensagem, **detalhes)
            # Mantém o XML transmitido para consulta/recuperação e não libera timeout.
            conn_erro = conectar()
            try:
                c = conn_erro.cursor()
                c.execute("UPDATE notas_fiscais SET status=?,mensagem_retorno=? WHERE id=? AND status<>'Autorizada'", (estado, mensagem, nota_id))
                conn_erro.commit()
            finally:
                conn_erro.close()
    # Finaliza os documentos das duas espécies, inclusive após falha isolada de PDF.
    # Trabalha somente com XMLs já autorizados; jamais repete transmissão fiscal.
    try:
        recuperar_pdfs(conectar, fat_id)
    except Exception as erro_pdf:
        for registro in listar_emissoes(conectar, fat_id):
            if registro['estado'] == 'Autorizada':
                _atualizar(conectar, registro['id'], mensagem='Autorização preservada. ' + str(erro_pdf))
    return listar_emissoes(conectar, fat_id)
