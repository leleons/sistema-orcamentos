"""Configuracao de navegacao e permissoes do ERP."""

from __future__ import annotations

ARVORE_PERMISSOES = [
    {
        "titulo": "Cadastros",
        "modulo": "cadastros",
        "submodulos": [
            {"titulo": "Cadastro de Clientes/Fornecedores", "acoes": [("clientes.view", "Acessar"), ("clientes.edit", "Editar"), ("clientes.delete", "Excluir")], "legacy": {"clientes.view": "perm_clientes"}},
            {"titulo": "Gerenciador de Usuários", "acoes": [("usuarios.view", "Acessar"), ("usuarios.edit", "Editar"), ("usuarios.delete", "Excluir")]},
            {"titulo": "Contratos", "acoes": [("contratos.view", "Consultar"), ("contratos.edit", "Editar"), ("contratos.delete", "Excluir")], "legacy": {"contratos.view": "perm_clientes", "contratos.edit": "perm_clientes"}},
        ],
    },
    {
        "titulo": "Financeiro",
        "modulo": "financeiro",
        "submodulos": [
            {"titulo": "Incluir Contas a Pagar", "acoes": [("financeiro.pagar", "Acessar"), ("financeiro.pagar.edit", "Editar/baixar"), ("financeiro.pagar.delete", "Excluir")]},
            {"titulo": "Incluir Contas a Receber", "acoes": [("financeiro.receber", "Acessar"), ("financeiro.receber.edit", "Editar/baixar"), ("financeiro.receber.delete", "Excluir")]},
            {"titulo": "Lançamentos Financeiros", "acoes": [("financeiro.lancamentos", "Acessar"), ("financeiro.lancamentos.edit", "Editar/baixar"), ("financeiro.lancamentos.delete", "Excluir")]},
            {"titulo": "Cadastros Financeiros", "acoes": [("financeiro.cadastros", "Acessar"), ("financeiro.cadastros.edit", "Editar"), ("financeiro.cadastros.delete", "Excluir")]},
        ],
    },
    {
        "titulo": "Faturamento",
        "modulo": "faturamento",
        "submodulos": [
            {"titulo": "A faturar", "acoes": [("faturamento.view", "Acessar"), ("faturamento.edit", "Editar"), ("faturamento.delete", "Excluir")], "legacy": {"faturamento.view": "perm_faturamento"}},
            {"titulo": "Faturado", "acoes": [("faturamento.faturado", "Acessar"), ("faturamento.faturado.edit", "Emitir/atualizar nota")]},
            {"titulo": "Cobranças Recorrentes", "acoes": [("faturamento.cobrancas", "Acessar"), ("faturamento.cobrancas.edit", "Editar"), ("faturamento.cobrancas.delete", "Excluir")]},
            {"titulo": "Gerador de Orçamentos", "acoes": [("orcamentos.view", "Acessar"), ("orcamentos.edit", "Editar/aprovar"), ("orcamentos.delete", "Excluir")], "legacy": {"orcamentos.view": "perm_orcamentos", "orcamentos.delete": "perm_del_orc"}},
        ],
    },
    {
        "titulo": "Estoque",
        "modulo": "estoque",
        "submodulos": [
            {"titulo": "Controle de Estoque", "acoes": [("estoque.view", "Acessar"), ("estoque.edit", "Editar"), ("estoque.delete", "Excluir")], "legacy": {"estoque.view": "perm_estoque"}},
            {"titulo": "Compras e Cotações", "acoes": [("compras.view", "Acessar"), ("compras.edit", "Incluir/escolher cotações"), ("compras.delete", "Excluir cotações")], "legacy": {"compras.view": "perm_estoque", "compras.edit": "perm_estoque", "compras.delete": "perm_estoque"}},
        ],
    },
    {
        "titulo": "Serviços",
        "modulo": "servicos",
        "submodulos": [
            {"titulo": "Ordem de Serviços", "acoes": [("os.view", "Acessar"), ("os.edit", "Editar"), ("os.delete", "Excluir")], "legacy": {"os.view": "perm_os", "os.edit": "perm_edit_os", "os.delete": "perm_del_os"}},
            {"titulo": "Recepção e Kanban", "acoes": [("recepcao.view", "Visualizar quadro/etiquetas"), ("recepcao.edit", "Movimentar equipamentos")], "legacy": {"recepcao.view": "perm_os", "recepcao.edit": "perm_edit_os"}},
            {"titulo": "Atendimentos e Checklists", "acoes": [("atendimentos.view", "Acessar"), ("atendimentos.edit", "Editar"), ("atendimentos.delete", "Excluir")], "legacy": {"atendimentos.view": "perm_atendimentos", "atendimentos.edit": "perm_edit_atendimentos"}},
        ],
    },
    {
        "titulo": "ServiceDesk",
        "modulo": "servicedesk",
        "submodulos": [],
    },
    {
        "titulo": "Infraestrutura TI",
        "modulo": "infraestrutura",
        "submodulos": [
            {"titulo": "Acesso ao módulo", "acoes": [("infra.view", "Acessar"), ("infra.edit", "Editar fichas"), ("infra.delete", "Excluir fichas")], "legacy": {"infra.view": "perm_infra", "infra.edit": "perm_edit_infra", "infra.delete": "perm_del_infra"}},
            {"titulo": "Sistemas", "acoes": [("infra.sistemas", "Acessar aba")]},
            {"titulo": "Rede", "acoes": [("infra.rede", "Acessar aba")]},
            {"titulo": "DVR", "acoes": [("infra.dvr", "Acessar aba")]},
            {"titulo": "Câmeras", "acoes": [("infra.cameras", "Acessar aba")]},
            {"titulo": "Alarme", "acoes": [("infra.alarme", "Acessar aba")]},
            {"titulo": "Wi-Fi", "acoes": [("infra.wifi", "Acessar aba")]},
            {"titulo": "Servidor", "acoes": [("infra.servidor", "Acessar aba")]},
            {"titulo": "Antivírus", "acoes": [("infra.antivirus", "Acessar aba")]},
            {"titulo": "Financeiro", "acoes": [("infra.financeiro", "Acessar aba")]},
            {"titulo": "PCs e Acessos", "acoes": [("infra.pcs", "Acessar aba")]},
            {"titulo": "Setores", "acoes": [("infra.setores", "Acessar aba")]},
            {"titulo": "Equipamentos", "acoes": [("infra.equipamentos", "Acessar aba")]},
            {"titulo": "Hospedagem", "acoes": [("infra.hospedagem", "Acessar aba")]},
            {"titulo": "Gestão de E-mails", "acoes": [("infra.emails", "Acessar aba")]},
            {"titulo": "Aplicativos", "acoes": [("infra.aplicativos", "Acessar aba")]},
        ],
    },
    {
        "titulo": "Acesso Softwares",
        "modulo": "softwares",
        "submodulos": [
            {"titulo": "Pasta Dsystem", "acoes": [("softwares.dsystem", "Acessar arquivos padrão")]},
        ],
    },
    {
        "titulo": "Cliente",
        "modulo": "cliente",
        "submodulos": [
            {"titulo": "Portal do Cliente", "acoes": [("cliente.portal", "Acessar"), ("cliente.os", "Ver OS/status"), ("cliente.autorizacao", "Autorizar serviço"), ("cliente.chamados", "Abrir chamados"), ("cliente.propostas", "Responder propostas/contratos")]},
        ],
    },
]

TODAS_PERMISSOES = [
    acao
    for modulo in ARVORE_PERMISSOES
    for submodulo in modulo["submodulos"]
    for acao, _ in submodulo["acoes"]
]

LEGACY_PERMISSOES = {
    acao: coluna
    for modulo in ARVORE_PERMISSOES
    for submodulo in modulo["submodulos"]
    for acao, coluna in submodulo.get("legacy", {}).items()
}

PERMISSOES_INFRA_ABAS = {
    "Sistemas": "infra.sistemas",
    "Rede": "infra.rede",
    "DVR": "infra.dvr",
    "Câmeras": "infra.cameras",
    "Alarme": "infra.alarme",
    "Wi-Fi": "infra.wifi",
    "Servidor": "infra.servidor",
    "Antivírus": "infra.antivirus",
    "Financeiro": "infra.financeiro",
    "PCs e Acessos": "infra.pcs",
    "Setores": "infra.setores",
    "Equipamentos": "infra.equipamentos",
    "Hospedagem": "infra.hospedagem",
    "Gestão de E-mails": "infra.emails",
    "Aplicativos": "infra.aplicativos",
}

MODULOS_NAVEGACAO = [
    {
        "titulo": "Cadastros",
        "submodulos": [
            {"titulo": "Cadastro de Clientes/Fornecedores", "pagina": "Cadastro de Cliente/Fornecedor", "acoes": ["clientes.view"], "botao": "Acessar Cadastro"},
            {"titulo": "Gerenciador de Usuários", "pagina": "Gerenciador de Usuários", "acoes": ["usuarios.view"], "botao": "Acessar Usuários"},
            {"titulo": "Contratos", "pagina": "Contratos", "acoes": ["contratos.view"], "botao": "Acessar Contratos"},
        ],
    },
    {
        "titulo": "Financeiro",
        "submodulos": [
            {"titulo": "Incluir Contas a Pagar", "pagina": "Contas a Pagar", "acoes": ["financeiro.pagar"], "botao": "Incluir Contas a Pagar"},
            {"titulo": "Incluir Contas a Receber", "pagina": "Contas a Receber", "acoes": ["financeiro.receber"], "botao": "Incluir Contas a Receber"},
            {"titulo": "Lançamentos Financeiros", "pagina": "Lançamentos Financeiros", "acoes": ["financeiro.lancamentos"], "botao": "Acessar Lançamentos"},
            {"titulo": "Cadastros Financeiros", "pagina": "Cadastros Financeiros", "acoes": ["financeiro.cadastros"], "botao": "Acessar Cadastros"},
        ],
    },
    {
        "titulo": "Estoque",
        "submodulos": [
            {"titulo": "Controle de Estoque", "pagina": "Controle de Estoque", "acoes": ["estoque.view"], "botao": "Acessar Estoque"},
            {"titulo": "Compras e Cotações", "pagina": "Compras e Cotações", "acoes": ["compras.view"], "botao": "Acessar Compras"},
        ],
    },
    {
        "titulo": "Serviços",
        "submodulos": [],
    },
    {
        "titulo": "Faturamento",
        "submodulos": [
            {"titulo": "A faturar", "pagina": "Faturamento", "acoes": ["faturamento.view"], "botao": "A faturar"},
            {"titulo": "Faturado", "pagina": "Faturado", "acoes": ["faturamento.faturado", "faturamento.view"], "botao": "Faturado"},
            {"titulo": "Cobranças Recorrentes", "pagina": "Cobranças", "acoes": ["faturamento.view"], "botao": "Acessar Cobranças"},
            {"titulo": "Gerador de Orçamentos", "pagina": "Gerador de Orçamentos", "acoes": ["orcamentos.view"], "botao": "Acessar Orçamentos"},
        ],
    },
    {
        "titulo": "ServiceDesk",
        "submodulos": [
            {"titulo": "Ordem de Serviços", "pagina": "Ordem de Serviço (OS)", "acoes": ["os.view"], "botao": "Acessar O.S."},
            {"titulo": "Recepção e Kanban", "pagina": "Recepção e Kanban", "acoes": ["recepcao.view"], "botao": "Abrir Kanban"},
            {"titulo": "Atendimentos e Checklists", "pagina": "Atendimentos e Checklists", "acoes": ["atendimentos.view"], "botao": "Acessar Atendimentos"},
            {"titulo": "Infraestrutura TI", "pagina": "Infraestrutura TI", "acoes": ["infra.view"], "prefixo": "infra", "botao": "Acessar Infra/TI"},
            {"titulo": "Gestão de Chamados", "pagina": "Portal do Cliente", "acoes": ["cliente.portal"], "permite_chamados_atribuidos": True, "botao": "Acessar Chamados"},
        ],
    },
    {
        "titulo": "Relatórios",
        "submodulos": [
            {"titulo": "Log do Sistema", "pagina": "Log do Sistema", "acoes": [], "somente_daniel": True, "botao": "Acessar Log"},
            {"titulo": "Backups", "pagina": "Backups do Sistema", "acoes": [], "somente_daniel": True, "botao": "Gerenciar Backups"},
            {"titulo": "Diagnóstico", "pagina": "Diagnóstico do Sistema", "acoes": [], "somente_daniel": True, "botao": "Ver Diagnóstico"},
            {"titulo": "Configurações", "pagina": "Configurações do Sistema", "acoes": [], "somente_daniel": True, "botao": "Configurações"},
        ],
    },
    {
        "titulo": "Acesso Softwares",
        "submodulos": [
            {"titulo": "Pasta Dsystem", "pagina": "Acesso Softwares", "acoes": ["softwares.dsystem"], "botao": "Acessar Softwares"},
        ],
    },
]
