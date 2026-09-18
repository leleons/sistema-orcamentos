"""Registro interno de corridas e vínculo com múltiplos clientes."""

import json
from decimal import Decimal, InvalidOperation
from dsystem_erp.utils.datas import parse_data_flex, agora_br


TIPOS_CORRIDA = (
    'Envio de produto sem acompanhante',
    'Entrega de produto com colaborador',
    'Deslocamento para suporte',
)


def garantir_tabelas_uber(cursor):
    cursor.execute('''CREATE TABLE IF NOT EXISTS uber_corridas (
        id INT PRIMARY KEY AUTO_INCREMENT, data_corrida DATE NOT NULL,
        finalidade VARCHAR(100) NOT NULL, valor_total DECIMAL(14,2) NOT NULL,
        colaboradores LONGTEXT, produtos TEXT, origem TEXT, destino TEXT, observacoes LONGTEXT,
        status VARCHAR(30) DEFAULT 'Registrada', criado_por VARCHAR(255), criado_em VARCHAR(30),
        alterado_por VARCHAR(255), alterado_em VARCHAR(30),
        INDEX idx_uber_data (data_corrida)
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS uber_corrida_clientes (
        corrida_id INT NOT NULL, cliente_id INT NOT NULL, cliente_nome VARCHAR(255) NOT NULL,
        PRIMARY KEY (corrida_id, cliente_id), INDEX idx_uber_cliente (cliente_id)
    )''')


def validar_corrida(dados):
    data = parse_data_flex(dados.get('data_corrida'))
    if not data:
        raise ValueError('Informe a data da corrida.')
    try:
        valor = Decimal(str(dados.get('valor_total') or 0))
    except InvalidOperation:
        raise ValueError('Informe um valor válido.') from None
    if not valor.is_finite() or valor <= 0 or valor >= Decimal('1000000000000'):
        raise ValueError('O valor total da corrida deve ser maior que zero e válido.')
    valor = valor.quantize(Decimal('0.01'))
    if valor <= 0 or valor >= Decimal('1000000000000'):
        raise ValueError('Informe um valor válido de pelo menos R$ 0,01.')
    finalidade = dados.get('finalidade')
    if finalidade not in TIPOS_CORRIDA:
        raise ValueError('Selecione a finalidade da corrida.')
    clientes = sorted(set(int(c) for c in dados.get('cliente_ids', [])))
    if not clientes or any(c <= 0 for c in clientes):
        raise ValueError('Vincule pelo menos um cliente à corrida.')
    colaboradores = list(dict.fromkeys(str(c).strip() for c in dados.get('colaboradores', []) if str(c).strip()))
    if finalidade != TIPOS_CORRIDA[0] and not colaboradores:
        raise ValueError('Selecione o colaborador que participou da corrida.')
    if finalidade == TIPOS_CORRIDA[0]:
        colaboradores = []
    produtos = str(dados.get('produtos') or '').strip()
    if finalidade in TIPOS_CORRIDA[:2] and not produtos:
        raise ValueError('Descreva os produtos enviados ou entregues.')
    return dict(dados, data_corrida=data.isoformat(), valor_total=valor.quantize(Decimal('0.01')),
                cliente_ids=clientes, colaboradores=colaboradores, produtos=produtos)


def listar_corridas(conectar):
    conn = conectar()
    try:
        c = conn.cursor()
        c.execute('SELECT * FROM uber_corridas ORDER BY data_corrida DESC, id DESC')
        corridas = [dict(r) for r in c.fetchall()]
        c.execute('SELECT corrida_id, cliente_id, cliente_nome FROM uber_corrida_clientes ORDER BY cliente_nome')
        vinculos = {}
        for r in c.fetchall():
            item = dict(r)
            vinculos.setdefault(int(item['corrida_id']), []).append(item)
        for corrida in corridas:
            corrida['clientes'] = vinculos.get(int(corrida['id']), [])
            try:
                corrida['colaboradores'] = json.loads(corrida.get('colaboradores') or '[]')
            except (ValueError, TypeError):
                corrida['colaboradores'] = []
            if not isinstance(corrida['colaboradores'], list):
                corrida['colaboradores'] = []
        return corridas
    finally:
        conn.close()


def salvar_corrida(conectar, dados, usuario, corrida_id=None, clientes_permitidos=None):
    dados = validar_corrida(dados)
    if clientes_permitidos is not None and not set(dados['cliente_ids']).issubset(set(clientes_permitidos)):
        raise ValueError('Você não possui acesso a um dos clientes selecionados.')
    conn = conectar()
    try:
        c = conn.cursor()
        if corrida_id:
            c.execute('SELECT status FROM uber_corridas WHERE id=?', (corrida_id,))
            atual = c.fetchone()
            if not atual or dict(atual).get('status') == 'Cancelada':
                raise ValueError('Corrida não encontrada ou já cancelada.')
            if clientes_permitidos is not None:
                c.execute('SELECT cliente_id FROM uber_corrida_clientes WHERE corrida_id=?', (corrida_id,))
                if not {int(dict(r)['cliente_id']) for r in c.fetchall()}.issubset(set(clientes_permitidos)):
                    raise ValueError('Você não possui acesso a todos os clientes desta corrida.')
        nomes = []
        for cliente_id in dados['cliente_ids']:
            c.execute('SELECT id, nome FROM clientes WHERE id=?', (cliente_id,))
            cliente = c.fetchone()
            if not cliente:
                raise ValueError(f'Cliente #{cliente_id} não encontrado.')
            nomes.append((cliente_id, dict(cliente)['nome']))
        valores = (dados['data_corrida'], dados['finalidade'], str(dados['valor_total']),
                   json.dumps(dados['colaboradores'], ensure_ascii=False), dados['produtos'],
                   dados.get('origem', ''), dados.get('destino', ''), dados.get('observacoes', ''))
        if corrida_id:
            c.execute('''UPDATE uber_corridas SET data_corrida=?, finalidade=?, valor_total=?, colaboradores=?,
                         produtos=?, origem=?, destino=?, observacoes=?, alterado_por=?, alterado_em=? WHERE id=?''',
                      valores + (usuario, agora_br(), corrida_id))
            c.execute('DELETE FROM uber_corrida_clientes WHERE corrida_id=?', (corrida_id,))
        else:
            c.execute('''INSERT INTO uber_corridas (data_corrida, finalidade, valor_total, colaboradores,
                         produtos, origem, destino, observacoes, criado_por, criado_em) VALUES (?,?,?,?,?,?,?,?,?,?)''',
                      valores + (usuario, agora_br()))
            corrida_id = c.lastrowid
        for cliente_id, nome in nomes:
            c.execute('INSERT INTO uber_corrida_clientes (corrida_id, cliente_id, cliente_nome) VALUES (?,?,?)',
                      (corrida_id, cliente_id, nome))
        conn.commit()
        return corrida_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
