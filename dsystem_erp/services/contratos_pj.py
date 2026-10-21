"""Vínculo PJ explícito, sem confundir a empresa contratada com o CPF da pessoa."""
import re

MODELO_PJ = 'Prestação de Serviços PJ'
TIPOS_PJ = ('PJ', 'Contrato terceirizado')
CAMPOS_EMPRESA_PJ = ('funcionario_pj_razao_social', 'funcionario_pj_cnpj', 'funcionario_pj_endereco')


def eh_pj(tipo):
    return str(tipo or '').strip().casefold() in {t.casefold() for t in TIPOS_PJ}


def tipos_contrato_funcionario(atual=''):
    tipos = ['PJ', 'Estágio']
    # Preserva o valor de registros antigos sem oferecer CLT/RPA em novos cadastros.
    if atual and atual not in tipos:
        tipos.append(atual)
    return tipos


def cnpj_pj_valido(valor):
    texto = re.sub(r'[. /\-]', '', str(valor or '').strip().upper())
    # Verificação de formato, não de situação cadastral. Nunca usa CPF como CNPJ.
    return bool(re.fullmatch(r'[A-Z0-9]{12}[0-9]{2}', texto))


def cadastro_empresa_pj(usuario):
    cnpj = str(usuario.get('funcionario_pj_cnpj') or '').strip()
    if not cnpj:
        legado = str(usuario.get('funcionario_rj') or '').strip()
        cnpj = legado if cnpj_pj_valido(legado) else ''
    return dict(id=usuario['id'], nome=usuario.get('funcionario_pj_razao_social') or '',
                cnpj=cnpj, endereco=usuario.get('funcionario_pj_endereco') or '',
                responsavel_legal=usuario.get('funcionario_nome') or '',
                cpf_responsavel=usuario.get('funcionario_cpf') or '',
                telefone=usuario.get('funcionario_telefone') or '', email=usuario.get('funcionario_email') or '')


def salvar_empresa_pj(cursor, usuario_id, dados):
    cursor.execute('UPDATE usuarios SET funcionario_pj_razao_social=?, funcionario_pj_cnpj=?, funcionario_pj_endereco=? WHERE id=?',
                   tuple(str(dados.get(c) or '').strip() for c in CAMPOS_EMPRESA_PJ) + (usuario_id,))


def sincronizar_campo_cadastro(estado, chave, valor):
    """Atualiza o cadastro na tela sem perder ajustes feitos neste contrato."""
    valor = str(valor or '').strip()
    origem = chave + '_origem_cadastro'
    anterior = estado.get(origem)
    if chave not in estado or not str(estado[chave] or '').strip() or (
        anterior is not None and estado[chave] == anterior
    ):
        estado[chave] = valor
    estado[origem] = valor
