"""Helpers puros do portal do cliente.

O Streamlit continua no orcamento.py, mas navegação, links e HTML pequeno ficam
aqui para reduzir duplicação e facilitar testes.
"""

from __future__ import annotations

from html import escape


def portal_funcionario(estado):
    return estado.get('tipo_login') == 'cliente' and estado.get('portal_tipo_usuario') != 'Empresa'


def filtro_chamados_portal(estado, cliente_id=None, cliente_nome=None):
    """Escopo do portal vem da sessão, nunca do nome informado no formulário."""
    if estado.get('tipo_login') == 'cliente':
        empresa = estado.get('cliente_id')
        usuario = estado.get('username')
        if not empresa or not usuario:
            return '1=0', ()
        if estado.get('portal_tipo_usuario') == 'Empresa':
            # O login principal vê todos os autores, mas somente desta empresa.
            return 'cliente_id=%s', (empresa,)
        filtro = 'cliente_id=%s AND criado_por=%s'
        params = (empresa, usuario)
        if portal_funcionario(estado):
            filtro += (' AND EXISTS (SELECT 1 FROM clientes_portal_usuarios p '
                       'WHERE p.cliente_id=%s AND p.username=%s AND p.ativo=1)')
            params += (empresa, usuario)
        return filtro, params
    if cliente_id:
        return '(cliente_id=%s OR (cliente_id IS NULL AND cliente_nome=%s))', (cliente_id, cliente_nome)
    return 'cliente_nome=%s', (cliente_nome,)


def exigir_acesso_chamado(cursor, estado, chamado_id):
    """Revalida leituras e mutações conforme login principal ou individual."""
    if estado.get('tipo_login') != 'cliente':
        return
    filtro, params = filtro_chamados_portal(estado)
    cursor.execute(f'SELECT id FROM chamados_cliente WHERE id=%s AND ({filtro})', (chamado_id, *params))
    if not cursor.fetchone():
        raise PermissionError('Este chamado não pertence ao seu acesso ou seu login foi desativado.')


def exigir_conta_portal_ativa(cursor, estado):
    if estado.get('tipo_login') != 'cliente':
        return
    if not estado.get('cliente_id') or not estado.get('username'):
        raise PermissionError('Entre novamente no portal.')
    if portal_funcionario(estado):
        cursor.execute('SELECT id FROM clientes_portal_usuarios WHERE cliente_id=%s AND username=%s AND ativo=1',
                       (estado['cliente_id'], estado['username']))
        if not cursor.fetchone():
            raise PermissionError('Seu login foi desativado. Entre em contato com a D-System.')


MAPA_SECOES_PORTAL = {
    "inicio": "inicio",
    "chamados": "meus_chamados",
    "meus_chamados": "meus_chamados",
    "abrir_chamado": "abrir_chamado",
    "financeiro": "financeiro",
    "notas": "notas",
    "documentos": "documentos",
    "os": "os",
    "contato": "contato",
}


def normalizar_secao_portal(secao: str | None) -> str:
    secao_norm = (secao or "inicio").strip().lower()
    return MAPA_SECOES_PORTAL.get(secao_norm, secao_norm or "inicio")


def link_portal(secao: str) -> str:
    return f"?pagina=portal&secao={normalizar_secao_portal(secao)}"


def portal_card_html(secao: str, titulo: str, numero: str, descricao: str) -> str:
    secao_normalizada = normalizar_secao_portal(secao)
    return (
        f'<div class="portal-card" data-portal-section="{escape(secao_normalizada)}" data-href="{link_portal(secao_normalizada)}">'
        f"<strong>{escape(str(titulo))}</strong>"
        f'<div class="portal-number">{escape(str(numero))}</div>'
        f'<div class="portal-muted">{escape(str(descricao))}</div>'
        "</div>"
    )


def portal_mini_grid_html() -> str:
    return """
<div class="portal-section-title">Acessos rápidos</div>
<div class="portal-mini-grid">
  <div class="portal-mini"><b>Suporte</b><br><span class="portal-muted">Abra chamados com descrição, prioridade e anexos.</span></div>
  <div class="portal-mini"><b>Documentos</b><br><span class="portal-muted">Consulte propostas, contratos, notas e arquivos.</span></div>
  <div class="portal-mini"><b>Atendimento</b><br><span class="portal-muted">Acompanhe respostas e andamento dos serviços.</span></div>
</div>
"""
