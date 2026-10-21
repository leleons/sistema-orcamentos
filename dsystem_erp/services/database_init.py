"""Inicialização e evolução compatível das tabelas do ERP."""

from __future__ import annotations

import json
import re

from dsystem_erp.config import config_val
from dsystem_erp.migrations import (
    aplicar_migrations_pendentes,
    garantir_coluna,
    garantir_tabela_migrations,
    registrar_migration,
)
from dsystem_erp.services.security import criar_hash_senha
from dsystem_erp.repositories.uber import garantir_tabelas_uber
from dsystem_erp.services.nfse_catalogo_ti import cadastrar_catalogo_ti

def garantir_tabela_nova(conn, cursor, nome_tabela, sql_criacao):
    cursor.execute(sql_criacao)
    try:
        cursor.execute(f"SELECT 1 FROM `{nome_tabela}` LIMIT 1")
        cursor.fetchone()
    except Exception as ex:
        codigo_erro = getattr(ex, "errno", None)
        if codigo_erro not in (1146, 1932):
            raise
        try:
            cursor.execute(f"DROP TABLE IF EXISTS `{nome_tabela}`")
        except Exception:
            pass
        cursor.execute(sql_criacao)
        conn.commit()

def iniciar_banco(conectar_banco):
    conn = conectar_banco()
    c = conn.cursor()
    garantir_tabela_migrations(c)
    aplicar_migrations_pendentes(c)
    garantir_tabelas_uber(c)
    
    c.execute('''CREATE TABLE IF NOT EXISTS logs_sistema (
        id INT PRIMARY KEY AUTO_INCREMENT,
        criado_em DATETIME,
        usuario VARCHAR(120),
        acao VARCHAR(40),
        tabela VARCHAR(120),
        registro_id VARCHAR(80),
        cliente VARCHAR(255),
        pagina VARCHAR(255),
        detalhes LONGTEXT,
        ip TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS financeiro_cadastros_aux (
        id INT PRIMARY KEY AUTO_INCREMENT,
        tipo VARCHAR(80),
        nome TEXT,
        codigo TEXT,
        ativo VARCHAR(10) DEFAULT 'Sim',
        observacoes LONGTEXT,
        criado_por TEXT,
        criado_em TEXT,
        alterado_por TEXT,
        alterado_em TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS ordens_servico (os_id INT PRIMARY KEY AUTO_INCREMENT, cliente_id INTEGER, data_os TEXT, cliente TEXT, cpf_cnpj TEXT, endereco TEXT, equipamento TEXT, marca TEXT, avaria TEXT, servico TEXT, atendente TEXT, so TEXT, formatar TEXT, backup TEXT, aplicativos TEXT, fonte TEXT, hd_ssd TEXT, ram TEXT, cpu TEXT, gpu TEXT, placa_mae TEXT, gabinete TEXT, chave_so TEXT, app_especifico_check TEXT, app_especifico_nome TEXT)''')
    try: garantir_coluna(c, "ordens_servico", "cliente_id", "INTEGER")
    except Exception: pass
    c.execute('''CREATE TABLE IF NOT EXISTS os_tipos_aparelhos (
        id INT PRIMARY KEY AUTO_INCREMENT, nome VARCHAR(120) NOT NULL UNIQUE,
        ativo VARCHAR(10) DEFAULT 'Sim', criado_por TEXT, criado_em TEXT
    )''')
    for tipo_os_padrao in ("Desktop", "Notebook", "Servidor", "Impressora", "DVR", "Câmera", "Outro"):
        c.execute("INSERT IGNORE INTO os_tipos_aparelhos (nome, ativo) VALUES (?, ?)", (tipo_os_padrao, "Sim"))
    c.execute('''CREATE TABLE IF NOT EXISTS clientes (id INT PRIMARY KEY AUTO_INCREMENT, codigo_cliente TEXT, documento_chave VARCHAR(20) UNIQUE, nome TEXT, telefone TEXT, telefone_secundario TEXT, email TEXT, emails_cobranca TEXT, cnpj TEXT, rg_mei TEXT, endereco TEXT, numero TEXT, complemento TEXT, bairro TEXT, cidade_estado TEXT, cep TEXT, pessoa TEXT, endereco_padrao TEXT, referencia TEXT, codigo_ibge TEXT, uf TEXT, contato_padrao TEXT, contato_cobranca TEXT, contato TEXT, estado_insc_estadual TEXT, data_nascimento TEXT, optante_simples_nacional TEXT, ramo_atividade TEXT, dias_antecedencia_faturamento TEXT, dia_faturamento TEXT, dia_vencimento TEXT, redes_sociais LONGTEXT, funcionarios LONGTEXT, logo_nome TEXT, logo_mime TEXT, logo LONGBLOB, portal_username TEXT, portal_password TEXT, portal_trocar_senha INTEGER DEFAULT 1, portal_2fa_secret TEXT, portal_2fa_ativo INTEGER DEFAULT 0, portal_ultimo_login TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS orcamentos (orc_id INT PRIMARY KEY AUTO_INCREMENT, numero TEXT, data_orc TEXT, cliente TEXT, cpf_cnpj TEXT, valor_total TEXT, forma_pagamento TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS orcamento_pdfs (
        id INT PRIMARY KEY AUTO_INCREMENT,
        orc_id INTEGER,
        empresa VARCHAR(80),
        nome_arquivo TEXT,
        mime_type TEXT,
        arquivo LONGBLOB,
        criado_por TEXT,
        criado_em TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios (id INT PRIMARY KEY AUTO_INCREMENT, username TEXT UNIQUE, password TEXT, trocar_senha INTEGER DEFAULT 0, is_admin INTEGER, perm_orcamentos INTEGER, perm_del_orc INTEGER, perm_os INTEGER, perm_edit_os INTEGER, perm_del_os INTEGER, perm_emails INTEGER DEFAULT 1, perm_edit_em INTEGER DEFAULT 0, perm_del_em INTEGER DEFAULT 0, perm_infra INTEGER DEFAULT 1, perm_edit_infra INTEGER DEFAULT 0, perm_del_infra INTEGER DEFAULT 0, perm_clientes INTEGER DEFAULT 1, perm_estoque INTEGER DEFAULT 1, perm_faturamento INTEGER DEFAULT 0, submodulos LONGTEXT, empresas_permitidas LONGTEXT, funcionario_nome TEXT, funcionario_cpf TEXT, funcionario_rj TEXT, funcionario_dados_bancarios TEXT, funcionario_telefone TEXT, funcionario_email TEXT, funcionario_endereco TEXT, funcionario_tipo_contrato TEXT, funcionario_forma_pagamento TEXT, funcionario_emite_nf TEXT, funcionario_deslocamento TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS emails_clientes (id INT PRIMARY KEY AUTO_INCREMENT, cliente_vinculado TEXT, funcionario TEXT, email TEXT, senha TEXT, aliases TEXT, provedor TEXT, config_entrada TEXT, config_saida TEXT, capacidade TEXT, data_verificacao TEXT, backup_realizado TEXT, data_backup TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS infra_v4 (id INT PRIMARY KEY AUTO_INCREMENT, cliente_vinc TEXT, fantasia TEXT, razao TEXT, cnpj TEXT, endereco TEXT, contato TEXT, email_prin TEXT, tel_prin TEXT, tel_prov TEXT, contrato_data TEXT, pagto TEXT, venc TEXT, sys_dados TEXT, sys_serial TEXT, sys_cod TEXT, sys_adm TEXT, sys_senha TEXT, sys_sec TEXT, rede_prov TEXT, rede_ip TEXT, rede_log TEXT, rede_sen TEXT, rede_ddns TEXT, rede_dsen TEXT, rede_wire TEXT, rede_wsen TEXT, serv_nome TEXT, serv_ip TEXT, serv_link TEXT, serv_log TEXT, serv_sen TEXT, serv_anydesk LONGTEXT, serv_radmin LONGTEXT, serv_google_remote LONGTEXT, serv_info_gerais LONGTEXT, impressoras_acessos LONGTEXT, cert_log TEXT, cert_sen TEXT, fin_b1 TEXT, fin_b2 TEXT, fin_b3 TEXT, pcs_acessos TEXT, faixas_ip LONGTEXT, vpn_acessos LONGTEXT, hospedagem_acessos LONGTEXT, setores LONGTEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS estoque (id INT PRIMARY KEY AUTO_INCREMENT, codigo TEXT, codigo_entrada TEXT, codigo_item INTEGER, produto TEXT, modelo TEXT, nome_generico TEXT, categoria TEXT, fileira TEXT, caixa TEXT, tem_fonte VARCHAR(5) DEFAULT 'Não', quantidade INTEGER, estoque_minimo INTEGER, valor_custo TEXT, valor_venda TEXT, fornecedor TEXT, observacoes TEXT, foto_nome TEXT, foto_mime TEXT, foto LONGBLOB)''')
    for coluna_estoque_compra, tipo_estoque_compra in (
        ("data_compra", "DATE"),
        ("ultima_nota_entrada_id", "INTEGER"),
    ):
        try:
            garantir_coluna(c, "estoque", coluna_estoque_compra, tipo_estoque_compra)
        except Exception:
            pass
    garantir_tabela_nova(conn, c, "estoque_notas_entrada", '''CREATE TABLE IF NOT EXISTS estoque_notas_entrada (
        id INT PRIMARY KEY AUTO_INCREMENT, fornecedor TEXT NOT NULL, fornecedor_documento TEXT,
        numero_nota VARCHAR(120) NOT NULL, serie VARCHAR(40), chave_acesso VARCHAR(60) UNIQUE,
        data_compra DATE NOT NULL, origem VARCHAR(30) DEFAULT 'Manual', observacoes LONGTEXT,
        criado_por TEXT, criado_em TEXT, INDEX idx_estoque_nota_fornecedor (fornecedor(120)),
        INDEX idx_estoque_nota_data (data_compra)
    )''')
    garantir_tabela_nova(conn, c, "estoque_nota_entrada_itens", '''CREATE TABLE IF NOT EXISTS estoque_nota_entrada_itens (
        id INT PRIMARY KEY AUTO_INCREMENT, nota_entrada_id INTEGER NOT NULL, produto_id INTEGER NOT NULL,
        numero_item VARCHAR(30), codigo_fornecedor VARCHAR(120), codigo_barras VARCHAR(120),
        descricao TEXT, ncm VARCHAR(30), cfop VARCHAR(20), unidade VARCHAR(20),
        quantidade DECIMAL(14,3) DEFAULT 0, valor_unitario DECIMAL(14,4) DEFAULT 0,
        valor_total DECIMAL(14,2) DEFAULT 0, INDEX idx_estoque_nota_item_nota (nota_entrada_id),
        INDEX idx_estoque_nota_item_produto (produto_id)
    )''')
    garantir_tabela_nova(conn, c, "estoque_movimentacoes", '''CREATE TABLE IF NOT EXISTS estoque_movimentacoes (
        id INT PRIMARY KEY AUTO_INCREMENT, produto_id INTEGER NOT NULL, tipo VARCHAR(60) NOT NULL,
        quantidade DECIMAL(14,3) NOT NULL, estoque_anterior DECIMAL(14,3) DEFAULT 0,
        estoque_atual DECIMAL(14,3) DEFAULT 0, cliente_id INTEGER, cliente_nome TEXT,
        fornecedor TEXT, nota_entrada_id INTEGER, origem VARCHAR(60), origem_id INTEGER,
        observacoes LONGTEXT, criado_por TEXT, criado_em TEXT,
        INDEX idx_estoque_mov_produto (produto_id), INDEX idx_estoque_mov_cliente (cliente_id),
        INDEX idx_estoque_mov_nota (nota_entrada_id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS estoque_emprestimos (
        id INT PRIMARY KEY AUTO_INCREMENT, responsavel VARCHAR(255) NOT NULL,
        cliente_id INTEGER, cliente_nome VARCHAR(255), data_retirada DATE NOT NULL,
        data_limite DATE NOT NULL, status VARCHAR(40) DEFAULT 'Em aberto', observacoes LONGTEXT,
        criado_por VARCHAR(255), criado_em VARCHAR(30), encerrado_por VARCHAR(255), encerrado_em VARCHAR(30),
        INDEX idx_emprestimos_status_limite (status, data_limite)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS estoque_emprestimo_itens (
        id INT PRIMARY KEY AUTO_INCREMENT, emprestimo_id INT NOT NULL, produto_id INT NOT NULL,
        codigo VARCHAR(255), produto VARCHAR(255), quantidade INT NOT NULL,
        status VARCHAR(40) DEFAULT 'Emprestado', resolvido_por VARCHAR(255), resolvido_em VARCHAR(30),
        observacao_resolucao LONGTEXT, INDEX idx_emprestimo_itens_emprestimo (emprestimo_id),
        INDEX idx_emprestimo_itens_status (status)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS equipamentos_os (
        id INT PRIMARY KEY AUTO_INCREMENT,
        os_id INTEGER,
        numero_item TEXT,
        letra_equipamento TEXT,
        tipo_equipamento TEXT,
        equipamento TEXT,
        marca TEXT,
        numero_serie TEXT,
        avaria TEXT,
        defeito TEXT,
        servico TEXT,
        configuracao TEXT,
        foto_nome TEXT,
        foto_mime TEXT,
        foto LONGBLOB
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS pedidos_compra (
        id INT PRIMARY KEY AUTO_INCREMENT,
        data_pedido TEXT, produto_id INTEGER, codigo TEXT, produto TEXT,
        quantidade_solicitada INTEGER, fornecedor TEXT, status TEXT, observacoes TEXT
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS atendimentos_checklist (
        id INT PRIMARY KEY AUTO_INCREMENT,
        tipo_atendimento TEXT, cliente TEXT, equipamento TEXT, 
        funcionario_atendido TEXT, maquinas_atendidas TEXT, tecnicos TEXT, 
        data_entrada TEXT, status TEXT, obs_entrada TEXT, 
        formatacao TEXT, bkp_convencionais TEXT, bkp_c TEXT, bkp_nav TEXT, bkp_email TEXT, data_backup TEXT,
        pasta_dsys TEXT, limpeza_int TEXT, limpeza_ext TEXT, verif_update TEXT, 
        soft_indesejado TEXT, confirma_soft TEXT, bkp_retornou TEXT, testado_hw TEXT, sacola TEXT, 
        verif_desempenho TEXT, obs_desempenho TEXT, detalhes_realizado TEXT, senhas_alteradas TEXT, historico TEXT,
        kanban_status VARCHAR(60) DEFAULT 'Recebido', kanban_ordem INTEGER DEFAULT 0,
        kanban_alterado_por TEXT, kanban_alterado_em TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS atendimentos_intervencoes (
        id INT PRIMARY KEY AUTO_INCREMENT,
        cliente_id INTEGER,
        cliente_nome TEXT,
        equipamento TEXT,
        identificacao TEXT,
        tipo_equipamento TEXT,
        quem_usa TEXT,
        tecnico TEXT,
        data_intervencao TEXT,
        descricao LONGTEXT,
        preventiva_prevista VARCHAR(20) DEFAULT 'Não',
        periodo_preventiva VARCHAR(60),
        preventiva_realizada VARCHAR(20) DEFAULT 'Não',
        data_preventiva TEXT,
        proxima_preventiva TEXT,
        observacoes LONGTEXT,
        criado_por TEXT,
        criado_em TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS infra_equipamentos (
        id INT PRIMARY KEY AUTO_INCREMENT,
        cliente_id INTEGER,
        cliente_nome TEXT,
        funcionario_usuario TEXT,
        funcionario_nome TEXT,
        origem VARCHAR(80),
        tipo_equipamento VARCHAR(80),
        nome_equipamento TEXT,
        ip_equipamento TEXT,
        quem_usa TEXT,
        informacoes LONGTEXT,
        criado_por TEXT,
        criado_em TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS infra_equipamentos_fotos (
        id INT PRIMARY KEY AUTO_INCREMENT,
        equipamento_id INTEGER,
        foto_nome TEXT,
        foto_mime TEXT,
        foto LONGBLOB,
        criado_em TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS infra_item_fotos (
        id INT PRIMARY KEY AUTO_INCREMENT,
        ficha_id INTEGER,
        tipo_item VARCHAR(40),
        item_indice INTEGER,
        item_nome TEXT,
        foto_nome TEXT,
        foto_mime TEXT,
        foto LONGBLOB,
        criado_em TEXT
    )''')

   
    c.execute('''CREATE TABLE IF NOT EXISTS agenda_visitas (
        id INT PRIMARY KEY AUTO_INCREMENT,
        tecnico TEXT,
        cliente_id INTEGER,
        cliente_nome TEXT,
        data_visita TEXT,
        hora_inicio TEXT,
        hora_fim TEXT,
        tipo_visita TEXT,
        descricao TEXT,
        status VARCHAR(60) DEFAULT 'Agendado',
        criado_em TEXT
    )''')
    for coluna_agenda_rec, tipo_agenda_rec in (
        ("recorrencia_id", "INTEGER"), ("recorrencia_indice", "INTEGER")
    ):
        try: garantir_coluna(c, "agenda_visitas", coluna_agenda_rec, tipo_agenda_rec)
        except Exception: pass
    c.execute('''CREATE TABLE IF NOT EXISTS agenda_tipos_atendimento (
        id INT PRIMARY KEY AUTO_INCREMENT, nome VARCHAR(120) NOT NULL UNIQUE,
        ativo VARCHAR(10) DEFAULT 'Sim', criado_por TEXT, criado_em TEXT
    )''')
    for tipo_agenda_padrao in ("Suporte Presencial", "Instalação", "Manutenção Preventiva", "Reunião", "Entrega de Equipamento", "Outro"):
        c.execute("INSERT IGNORE INTO agenda_tipos_atendimento (nome, ativo) VALUES (?, ?)", (tipo_agenda_padrao, "Sim"))
    c.execute('''CREATE TABLE IF NOT EXISTS agenda_recorrencias (
        id INT PRIMARY KEY AUTO_INCREMENT, tecnico TEXT, cliente_id INTEGER, cliente_nome TEXT,
        data_inicio TEXT, hora_inicio TEXT, hora_fim TEXT, tipo_atendimento TEXT, descricao LONGTEXT,
        periodicidade VARCHAR(40), dia_semana INTEGER, dia_mes INTEGER,
        mes_anual INTEGER, dia_anual INTEGER, modo_termino VARCHAR(40), quantidade INTEGER,
        data_fim TEXT, ativa VARCHAR(10) DEFAULT 'Sim', criado_por TEXT, criado_em TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS agenda_atividades (
        id INT PRIMARY KEY AUTO_INCREMENT, atividade LONGTEXT NOT NULL, cliente_id INTEGER,
        cliente_nome TEXT, data_execucao TEXT, hora_execucao TEXT, executor TEXT,
        status VARCHAR(40) DEFAULT 'Pendente', criado_por TEXT, criado_em TEXT,
        alterado_por TEXT, alterado_em TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS autorizacoes_cliente (
        id INT PRIMARY KEY AUTO_INCREMENT,
        cliente TEXT,
        os_id INTEGER,
        servico TEXT,
        status TEXT,
        observacao TEXT,
        criado_em TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS chamados_cliente (
        id INT PRIMARY KEY AUTO_INCREMENT,
        cliente_id INTEGER,
        cliente_nome TEXT,
        solicitante TEXT,
        area_destino VARCHAR(40) DEFAULT 'Suporte',
        tipo_atendimento TEXT,
        data_solicitada TEXT,
        hora_inicio TEXT,
        hora_fim TEXT,
        titulo TEXT,
        descricao TEXT,
        status VARCHAR(80) DEFAULT 'Novo',
        administrador VARCHAR(120) DEFAULT 'Daniel.fabio',
        funcionario_designado TEXT,
        ajuste_tipo_atendimento TEXT,
        ajuste_data TEXT,
        ajuste_hora_inicio TEXT,
        ajuste_hora_fim TEXT,
        ajuste_descricao TEXT,
        resposta_cliente TEXT,
        criado_por TEXT,
        criado_em TEXT,
        atualizado_em TEXT,
        kanban_status VARCHAR(60) DEFAULT 'Recebido',
        kanban_ordem INTEGER DEFAULT 0,
        kanban_alterado_por TEXT,
        kanban_alterado_em TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS chamados_mensagens (
        id INT PRIMARY KEY AUTO_INCREMENT,
        chamado_id INTEGER,
        autor_tipo VARCHAR(40),
        autor_nome TEXT,
        mensagem LONGTEXT,
        anexo_nome TEXT,
        anexo_mime TEXT,
        anexo LONGBLOB,
        criado_em TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS propostas_contratos_cliente (
        id INT PRIMARY KEY AUTO_INCREMENT,
        cliente_id INTEGER,
        cliente_nome TEXT,
        tipo TEXT,
        titulo TEXT,
        descricao TEXT,
        nome_arquivo TEXT,
        mime_type TEXT,
        arquivo LONGBLOB,
        status VARCHAR(80) DEFAULT 'Pendente',
        resposta_cliente TEXT,
        criado_por TEXT,
        criado_em TEXT,
        respondido_em TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS dsystem_arquivos (
        id INT PRIMARY KEY AUTO_INCREMENT,
        pasta TEXT,
        nome_arquivo TEXT,
        mime_type TEXT,
        tamanho BIGINT,
        arquivo LONGBLOB,
        caminho_arquivo TEXT,
        url_arquivo TEXT,
        armazenamento VARCHAR(40) DEFAULT 'banco',
        criado_por TEXT,
        criado_em TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS base_pesquisa (
        id INT PRIMARY KEY AUTO_INCREMENT, titulo VARCHAR(255) NOT NULL, categoria VARCHAR(120),
        palavras_chave TEXT, problema LONGTEXT, solucao LONGTEXT, criado_por TEXT, criado_em TEXT,
        alterado_por TEXT, alterado_em TEXT, INDEX idx_base_pesquisa_titulo (titulo)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS base_pesquisa_anexos (
        id INT PRIMARY KEY AUTO_INCREMENT, pesquisa_id INTEGER NOT NULL,
        nome TEXT, mime VARCHAR(255), arquivo LONGBLOB,
        INDEX idx_pesquisa_anexos (pesquisa_id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS contrato_clausulas (
        id INT PRIMARY KEY AUTO_INCREMENT,
        tipo_contrato VARCHAR(80),
        titulo TEXT,
        texto LONGTEXT,
        ativo VARCHAR(10) DEFAULT 'Sim',
        criado_por TEXT,
        criado_em TEXT,
        alterado_por TEXT,
        alterado_em TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS clientes_portal_acessos (
        id INT PRIMARY KEY AUTO_INCREMENT,
        cliente_id INTEGER,
        cliente_nome TEXT,
        portal_username TEXT,
        evento VARCHAR(80),
        ip TEXT,
        criado_em TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS cobrancas_recorrentes (
        id INT PRIMARY KEY AUTO_INCREMENT,
        cliente_id INTEGER,
        cliente_nome TEXT,
        tipo_cobranca VARCHAR(120),
        valor_financeiro DECIMAL(12,2) DEFAULT 0,
        data_emprestimo_locacao TEXT,
        motivo LONGTEXT,
        tipo_backup VARCHAR(120),
        quantidade INTEGER DEFAULT 0,
        servidor_backup TEXT,
        maquina_backup TEXT,
        data_cobranca TEXT,
        valor_cobranca DECIMAL(12,2) DEFAULT 0,
        vigencia_inicio TEXT,
        vigencia_fim TEXT,
        licencas_servidor INTEGER DEFAULT 0,
        licencas_maquinas INTEGER DEFAULT 0,
        pagamento VARCHAR(120),
        periodicidade VARCHAR(40),
        informacoes LONGTEXT,
        status VARCHAR(40) DEFAULT 'Ativa',
        criado_por TEXT,
        criado_em TEXT
    )''')
    for coluna_cobranca_contrato, tipo_cobranca_contrato in (
        ("contrato_id", "INTEGER"),
        ("origem", "VARCHAR(40) DEFAULT 'Manual'"),
    ):
        try: garantir_coluna(c, "cobrancas_recorrentes", coluna_cobranca_contrato, tipo_cobranca_contrato)
        except Exception: pass
    try:
        c.execute("CREATE UNIQUE INDEX uq_cobranca_contrato ON cobrancas_recorrentes (contrato_id)")
    except Exception:
        pass

    c.execute('''CREATE TABLE IF NOT EXISTS cobrancas_renovacoes (
        id INT PRIMARY KEY AUTO_INCREMENT,
        cobranca_id INTEGER,
        data_renovacao TEXT,
        vigencia_inicio_anterior TEXT,
        vigencia_fim_anterior TEXT,
        vigencia_inicio_nova TEXT,
        vigencia_fim_nova TEXT,
        valor_cobranca DECIMAL(12,2) DEFAULT 0,
        observacao LONGTEXT,
        criado_por TEXT,
        criado_em TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS contas_pagar (
        id INT PRIMARY KEY AUTO_INCREMENT,
        fornecedor TEXT, cpf_cnpj TEXT, numero_documento TEXT, tipo_documento TEXT,
        categoria TEXT, centro_custo TEXT, plano_contas TEXT, conta_bancaria TEXT,
        data_emissao TEXT, data_competencia TEXT, data_vencimento TEXT,
        valor_original DECIMAL(14,2) DEFAULT 0, desconto DECIMAL(14,2) DEFAULT 0,
        juros DECIMAL(14,2) DEFAULT 0, multa DECIMAL(14,2) DEFAULT 0,
        valor_total DECIMAL(14,2) DEFAULT 0, forma_pagamento TEXT,
        codigo_barras LONGTEXT, chave_pix TEXT, status VARCHAR(60) DEFAULT 'Aberto',
        observacoes LONGTEXT, data_baixa TEXT, valor_baixado DECIMAL(14,2) DEFAULT 0,
        baixado_por TEXT, criado_por TEXT, criado_em TEXT, alterado_por TEXT, alterado_em TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS contas_receber (
        id INT PRIMARY KEY AUTO_INCREMENT,
        cliente_id INTEGER, cliente TEXT, cpf_cnpj TEXT, numero_documento TEXT,
        tipo_receita TEXT, categoria TEXT, centro_receita TEXT, plano_contas TEXT,
        conta_bancaria TEXT, data_emissao TEXT, data_competencia TEXT, data_vencimento TEXT,
        valor_original DECIMAL(14,2) DEFAULT 0, desconto DECIMAL(14,2) DEFAULT 0,
        juros DECIMAL(14,2) DEFAULT 0, multa DECIMAL(14,2) DEFAULT 0,
        valor_total DECIMAL(14,2) DEFAULT 0, forma_recebimento TEXT,
        nota_fiscal TEXT, boleto TEXT, status VARCHAR(60) DEFAULT 'Aberto',
        observacoes LONGTEXT, data_baixa TEXT, valor_baixado DECIMAL(14,2) DEFAULT 0,
        baixado_por TEXT, criado_por TEXT, criado_em TEXT, alterado_por TEXT, alterado_em TEXT
    )''')
    for coluna_os_recepcao, tipo_os_recepcao in (
        ("chamado_id", "INTEGER"), ("recebido_por", "TEXT"), ("recebido_em", "TEXT"),
    ):
        try: garantir_coluna(c, "ordens_servico", coluna_os_recepcao, tipo_os_recepcao)
        except Exception: pass
    for coluna_eq_kanban, tipo_eq_kanban in (
        ("kanban_status", "VARCHAR(60) DEFAULT 'Recebido'"), ("etiqueta_codigo", "VARCHAR(80)"),
        ("kanban_arquivado", "INTEGER DEFAULT 0"),
        ("kanban_alterado_por", "TEXT"), ("kanban_alterado_em", "TEXT"), ("kanban_ordem", "INTEGER DEFAULT 0"),
    ):
        try: garantir_coluna(c, "equipamentos_os", coluna_eq_kanban, tipo_eq_kanban)
        except Exception: pass
    for tabela_kanban in ("atendimentos_checklist", "chamados_cliente"):
        for coluna_kanban, tipo_kanban in (
            ("kanban_status", "VARCHAR(60) DEFAULT 'Recebido'"),
            ("kanban_ordem", "INTEGER DEFAULT 0"),
            ("kanban_alterado_por", "TEXT"),
            ("kanban_alterado_em", "TEXT"),
            ("kanban_arquivado", "INTEGER DEFAULT 0"),
        ):
            try: garantir_coluna(c, tabela_kanban, coluna_kanban, tipo_kanban)
            except Exception: pass
    c.execute('''CREATE TABLE IF NOT EXISTS contratos (
        id INT PRIMARY KEY AUTO_INCREMENT, tipo VARCHAR(100), parte_tipo VARCHAR(40), parte_id INTEGER,
        parte_nome TEXT, nome_arquivo TEXT, mime_type TEXT, arquivo LONGBLOB,
        status VARCHAR(40) DEFAULT 'Ativo', valor TEXT, data_inicio TEXT, data_vencimento TEXT,
        observacoes LONGTEXT, criado_por TEXT, criado_em TEXT, alterado_por TEXT, alterado_em TEXT,
        INDEX idx_contratos_parte (parte_tipo, parte_id)
    )''')
    for coluna_contrato_rec, tipo_contrato_rec in (
        ("arquivo_word", "LONGBLOB"), ("nome_arquivo_word", "TEXT"),
        ("assinado", "VARCHAR(10) DEFAULT 'Não'"), ("data_assinatura", "TEXT"),
        ("gerar_recorrencia", "VARCHAR(10) DEFAULT 'Não'"),
        ("recorrencia_tipo", "TEXT"), ("recorrencia_periodicidade", "VARCHAR(40)"),
        ("recorrencia_primeiro_vencimento", "TEXT"), ("recorrencia_fim", "TEXT"),
        ("recorrencia_valor", "DECIMAL(14,2) DEFAULT 0"),
        ("recorrencia_pagamento", "TEXT"), ("cobranca_recorrente_id", "INTEGER"),
    ):
        try: garantir_coluna(c, "contratos", coluna_contrato_rec, tipo_contrato_rec)
        except Exception: pass
    c.execute('''CREATE TABLE IF NOT EXISTS cotacoes_compra (
        id INT PRIMARY KEY AUTO_INCREMENT,
        pedido_compra_id INTEGER NOT NULL,
        fornecedor TEXT NOT NULL,
        telefone TEXT,
        meio_compra TEXT NOT NULL,
        valor_item DECIMAL(15,2) NOT NULL,
        observacoes TEXT,
        escolhida INTEGER DEFAULT 0,
        criado_por TEXT,
        criado_em TEXT,
        INDEX idx_cotacoes_pedido (pedido_compra_id)
    )''')
    garantir_tabela_nova(conn, c, "garantias_clientes", '''CREATE TABLE IF NOT EXISTS garantias_clientes (
        id INT PRIMARY KEY AUTO_INCREMENT, numero VARCHAR(40) NOT NULL UNIQUE,
        cliente_id INTEGER NOT NULL, cliente TEXT NOT NULL, cliente_documento TEXT,
        faturamento_id INTEGER, data_emissao TEXT NOT NULL, origem TEXT, itens LONGTEXT,
        condicoes LONGTEXT, historico LONGTEXT, status VARCHAR(30) DEFAULT 'Emitida',
        pdf_nome TEXT, pdf_mime TEXT, pdf LONGBLOB, criado_por TEXT, criado_em TEXT,
        alterado_por TEXT, alterado_em TEXT, INDEX idx_garantia_cliente (cliente_id),
        INDEX idx_garantia_faturamento (faturamento_id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS clientes_portal_usuarios (
        id INT PRIMARY KEY AUTO_INCREMENT,
        cliente_id INTEGER NOT NULL,
        username VARCHAR(255) NOT NULL UNIQUE,
        nome TEXT,
        cargo TEXT,
        tipo VARCHAR(30) DEFAULT 'Funcionário',
        password TEXT,
        trocar_senha INTEGER DEFAULT 1,
        twofa_secret TEXT,
        twofa_ativo INTEGER DEFAULT 0,
        ultimo_login TEXT,
        ativo INTEGER DEFAULT 1,
        criado_em TEXT,
        INDEX idx_portal_usuario_cliente (cliente_id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS financeiro_impostos_taxas (
        id INT PRIMARY KEY AUTO_INCREMENT, nome VARCHAR(120) UNIQUE, tipo VARCHAR(30) DEFAULT 'Imposto',
        aliquota_padrao DECIMAL(10,4) DEFAULT 0, ativo VARCHAR(10) DEFAULT 'Sim', criado_por TEXT, criado_em TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS faturamento (
        id INT PRIMARY KEY AUTO_INCREMENT,
        data_lanc TEXT, cliente TEXT, cnpj TEXT, tipo TEXT, emite_nf TEXT, tipo_nota TEXT,
        forma_pag TEXT, itens LONGTEXT, valor_total DECIMAL(14,2) DEFAULT 0, parcelas TEXT,
        vencimento TEXT, orc_ref TEXT, obs_interna LONGTEXT, obs_nota LONGTEXT,
        nota_fiscal TEXT, boleto TEXT, status VARCHAR(60) DEFAULT 'Aberto',
        alterado_por TEXT, alterado_em TEXT
    )''')
    for coluna_medicao, tipo_medicao in (
        ("modalidade_faturamento", "VARCHAR(30) DEFAULT 'Por item'"),
        ("medicao_numero", "VARCHAR(80)"), ("medicao_inicio", "TEXT"),
        ("medicao_fim", "TEXT"), ("medicao_percentual", "DECIMAL(10,4) DEFAULT 0"),
        ("medicao_referencia", "TEXT"), ("medicao_historico", "LONGTEXT"),
        ("medicao_principal_id", "INTEGER"),
        ("documentos_entrega", "VARCHAR(40) DEFAULT 'Nota e espelho'"),
        ("emitir_automaticamente", "INTEGER DEFAULT 0"),
    ):
        try: garantir_coluna(c, "faturamento", coluna_medicao, tipo_medicao)
        except Exception: pass

    c.execute('''CREATE TABLE IF NOT EXISTS faturamento_anexos (
        id INT PRIMARY KEY AUTO_INCREMENT,
        faturamento_id INTEGER,
        tipo VARCHAR(80),
        nome_arquivo TEXT,
        mime_type TEXT,
        arquivo LONGBLOB,
        criado_por TEXT,
        criado_em TEXT
    )''')

    for coluna_fat, tipo_fat in [
        ("alterado_por", "TEXT"), ("alterado_em", "TEXT"),
        ("nota_fiscal", "TEXT"), ("boleto", "TEXT"),
        ("status", "VARCHAR(60) DEFAULT 'Aberto'"),
    ]:
        try:
            garantir_coluna(c, "faturamento", coluna_fat, tipo_fat)
        except Exception:
            pass

    garantir_tabela_nova(conn, c, "financeiro_recorrencias_v2", '''CREATE TABLE IF NOT EXISTS financeiro_recorrencias_v2 (
        id INT PRIMARY KEY AUTO_INCREMENT, tipo VARCHAR(20), parte TEXT, cpf_cnpj TEXT, descricao TEXT,
        valor DECIMAL(14,2) DEFAULT 0, frequencia VARCHAR(40), dia_vencimento INTEGER,
        data_inicial TEXT, data_final TEXT, centro TEXT, categoria TEXT, gerar_automaticamente VARCHAR(10),
        ativo VARCHAR(10) DEFAULT 'Sim', ultima_geracao TEXT, criado_por TEXT, criado_em TEXT
    )''')
    for campo_classificacao in ('categoria', 'centro', 'plano_contas', 'conta_bancaria'):
        garantir_coluna(c, 'faturamento', campo_classificacao, 'TEXT')
    for campo_classificacao in ('plano_contas', 'conta_bancaria'):
        garantir_coluna(c, 'financeiro_recorrencias_v2', campo_classificacao, 'TEXT')
    garantir_tabela_nova(conn, c, "financeiro_cobrancas_v2", '''CREATE TABLE IF NOT EXISTS financeiro_cobrancas_v2 (
        id INT PRIMARY KEY AUTO_INCREMENT, conta_receber_id INTEGER, cliente TEXT, dias_atraso INTEGER,
        valor_atualizado DECIMAL(14,2) DEFAULT 0, historico LONGTEXT, status VARCHAR(60),
        proxima_acao TEXT, responsavel TEXT, observacoes LONGTEXT, criado_em TEXT, alterado_em TEXT
    )''')
    garantir_tabela_nova(conn, c, "financeiro_renegociacoes_v2", '''CREATE TABLE IF NOT EXISTS financeiro_renegociacoes_v2 (
        id INT PRIMARY KEY AUTO_INCREMENT, tipo VARCHAR(20), parte TEXT, titulos_originais TEXT,
        valor_original DECIMAL(14,2) DEFAULT 0, valor_renegociado DECIMAL(14,2) DEFAULT 0,
        entrada DECIMAL(14,2) DEFAULT 0, parcelas INTEGER DEFAULT 1, primeiro_vencimento TEXT,
        juros DECIMAL(14,2) DEFAULT 0, multa DECIMAL(14,2) DEFAULT 0, desconto DECIMAL(14,2) DEFAULT 0,
        status VARCHAR(40) DEFAULT 'Ativo', observacoes LONGTEXT, criado_por TEXT, criado_em TEXT
    )''')

    for tabela_fin in ["contas_pagar", "contas_receber"]:
        for coluna_fin, tipo_coluna in [
            ("anexo_nome", "TEXT"), ("anexo_mime", "TEXT"), ("anexo", "LONGBLOB"),
            ("comprovante_nome", "TEXT"), ("comprovante_mime", "TEXT"), ("comprovante", "LONGBLOB"),
            ("conta_baixa", "TEXT"), ("forma_baixa", "TEXT"), ("observacao_baixa", "LONGTEXT"),
            ("taxas_baixa", "DECIMAL(14,2) DEFAULT 0"), ("juros_baixa", "DECIMAL(14,2) DEFAULT 0"),
            ("multa_baixa", "DECIMAL(14,2) DEFAULT 0"), ("desconto_baixa", "DECIMAL(14,2) DEFAULT 0"),
            ("cancelado_por", "TEXT"), ("motivo_cancelamento", "LONGTEXT"),
            ("conciliado", "VARCHAR(10) DEFAULT 'Não'"), ("data_conciliacao", "TEXT"),
            ("conciliado_por", "TEXT"),
        ]:
            try: c.execute(f"ALTER TABLE {tabela_fin} ADD COLUMN {coluna_fin} {tipo_coluna}")
            except Exception: pass
    for coluna_fatura, tipo_fatura in [
        ("fatura_cartao", "VARCHAR(10) DEFAULT 'Não'"),
        ("cartao_credito", "TEXT"),
        ("itens_fatura_cartao", "LONGTEXT"),
        ("conta_receber_origem_id", "INTEGER"),
    ]:
        try: garantir_coluna(c, "contas_pagar", coluna_fatura, tipo_fatura)
        except Exception: pass
    try:
        c.execute(
            "CREATE UNIQUE INDEX uq_pagar_origem_receber ON contas_pagar (conta_receber_origem_id)"
        )
    except Exception:
        pass
    garantir_tabela_nova(conn, c, "financeiro_fatura_cartao_itens", '''CREATE TABLE IF NOT EXISTS financeiro_fatura_cartao_itens (
        id INT PRIMARY KEY AUTO_INCREMENT, conta_pagar_id INTEGER NOT NULL, descricao TEXT,
        data_compra TEXT, categoria TEXT, valor DECIMAL(14,2) DEFAULT 0,
        criado_por TEXT, criado_em TEXT, INDEX idx_fatura_cartao_conta (conta_pagar_id)
    )''')
    for coluna_rec, tipo_rec in [
        ("regime_tributario", "VARCHAR(40) DEFAULT 'Normal'"), ("impostos", "LONGTEXT"),
        ("simples_aliquota", "DECIMAL(10,4) DEFAULT 0"), ("simples_valor", "DECIMAL(14,2) DEFAULT 0"),
        ("taxas_personalizadas", "LONGTEXT"), ("valor_impostos", "DECIMAL(14,2) DEFAULT 0"),
        ("valor_liquido", "DECIMAL(14,2) DEFAULT 0"), ("parcelado", "VARCHAR(10) DEFAULT 'Não'"),
        ("quantidade_parcelas", "INTEGER DEFAULT 1"), ("meio_parcelamento", "VARCHAR(60)"),
        ("parcelas_detalhes", "LONGTEXT"), ("bandeira_cartao", "VARCHAR(40)"),
        ("custo_tipo", "VARCHAR(20)"), ("pedido_compra_id", "INTEGER"),
        ("fornecedor_custo", "TEXT"), ("custo_unitario", "DECIMAL(14,2) DEFAULT 0"),
        ("quantidade_custo", "DECIMAL(14,3) DEFAULT 1"), ("custo_total", "DECIMAL(14,2) DEFAULT 0"),
        ("lucro_estimado", "DECIMAL(14,2) DEFAULT 0"), ("margem_lucro_percentual", "DECIMAL(10,4) DEFAULT 0"),
        ("cobranca_recorrente_id", "INTEGER"), ("cobranca_competencia", "VARCHAR(30)"),
        ("tem_terceiro", "VARCHAR(10) DEFAULT 'Não'"), ("terceiro_prestador", "TEXT"),
        ("terceiro_documento", "TEXT"), ("terceiro_valor", "DECIMAL(14,2) DEFAULT 0"),
        ("terceiro_historico", "LONGTEXT"), ("terceiro_vencimento", "TEXT"),
        ("terceiro_conta_pagar_id", "INTEGER"),
    ]:
        try: garantir_coluna(c, "contas_receber", coluna_rec, tipo_rec)
        except Exception: pass
    try:
        c.execute(
            "CREATE UNIQUE INDEX uq_conta_receber_recorrencia ON contas_receber (cobranca_recorrente_id, cobranca_competencia)"
        )
    except Exception:
        pass
    for coluna_aprovacao, tipo_aprovacao in [
        ("solicitante", "TEXT"), ("aprovador", "TEXT"), ("status_aprovacao", "VARCHAR(60) DEFAULT 'Pendente'"),
        ("motivo_reprovacao", "LONGTEXT"), ("data_aprovacao", "TEXT"),
    ]:
        try: c.execute(f"ALTER TABLE contas_pagar ADD COLUMN {coluna_aprovacao} {tipo_aprovacao}")
        except Exception: pass

    c.execute('''CREATE TABLE IF NOT EXISTS notas_fiscais (
        id INT PRIMARY KEY AUTO_INCREMENT,
        faturamento_id INTEGER, cliente TEXT, cpf_cnpj TEXT, tipo_nota TEXT,
        data_competencia TEXT, descricao LONGTEXT,
        valor_servicos DECIMAL(14,2) DEFAULT 0, aliquota_iss DECIMAL(8,4) DEFAULT 0,
        valor_iss DECIMAL(14,2) DEFAULT 0, codigo_servico TEXT, municipio_prestacao TEXT,
        status VARCHAR(60) DEFAULT 'Pendente', numero_nota TEXT, chave_acesso TEXT,
        link_nota LONGTEXT, observacoes LONGTEXT, criado_por TEXT, criado_em TEXT, emitido_em TEXT,
        xml_envio LONGTEXT, xml_retorno LONGTEXT, xml_autorizado LONGTEXT, pdf_base64 LONGTEXT,
        protocolo TEXT, mensagem_retorno LONGTEXT, numero_lote TEXT, atualizado_em TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS fiscal_emissoes_auto (
        id INT PRIMARY KEY AUTO_INCREMENT,
        faturamento_id INTEGER NOT NULL, tipo VARCHAR(20) NOT NULL,
        estado VARCHAR(40) NOT NULL DEFAULT 'Pendente', nota_id INTEGER,
        plano_json LONGTEXT, origem_hash VARCHAR(64), mensagem LONGTEXT,
        xml_envio LONGTEXT, xml_retorno LONGTEXT, autorizado_por TEXT,
        atualizado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY uq_fiscal_auto_tipo (faturamento_id, tipo)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS nfse_bh_servicos (
        id INT PRIMARY KEY AUTO_INCREMENT,
        nome TEXT,
        codigo_servico TEXT,
        item_lista_servico TEXT,
        aliquota_iss DECIMAL(8,4) DEFAULT 0,
        ativo VARCHAR(10) DEFAULT 'Sim',
        observacoes LONGTEXT
    )''')
    c.execute("SELECT COUNT(*) AS total FROM nfse_bh_servicos")
    total_nfse_servicos = c.fetchone()
    if (total_nfse_servicos.get("total") if isinstance(total_nfse_servicos, dict) else total_nfse_servicos[0]) == 0:
        c.execute(
            """INSERT INTO nfse_bh_servicos
               (nome, codigo_servico, item_lista_servico, aliquota_iss, ativo, observacoes)
               VALUES (?,?,?,?,?,?)""",
            ("Serviço Dsystem", "", "", 0, "Sim", "Cadastro inicial. Preencha o código e item da lista conforme a atividade."),
        )

    servicos_informatica_padrao = [
        ("Analise e desenvolvimento de sistemas", "01.01.01", "01.01", 0, "Sim", "Projeto, analise, desenho e desenvolvimento de sistemas sob demanda."),
        ("Desenvolvimento de sistemas sob encomenda", "01.01.02", "01.01", 0, "Sim", "Criacao de software, modulos, sistemas internos e automacoes."),
        ("Programacao", "01.02.01", "01.02", 0, "Sim", "Programacao, ajustes tecnicos e implementacao de codigo."),
        ("Consultoria em informatica", "01.06.01", "01.06", 0, "Sim", "Diagnostico, assessoria, planejamento tecnico e orientacao em TI."),
        ("Suporte tecnico em informatica", "01.07.01", "01.07", 0, "Sim", "Suporte, manutencao, instalacao, configuracao e bancos de dados."),
        ("Instalacao/configuracao de software", "01.07.02", "01.07", 0, "Sim", "Instalacao, configuracao e parametrizacao de programas."),
        ("Instalacao de Office e aplicativos", "01.07.02", "01.07", 0, "Sim", "Instalacao e configuracao de pacote Office, navegadores, antivirus e aplicativos de uso geral."),
        ("Instalacao de Windows e drivers", "01.07.02", "01.07", 0, "Sim", "Instalacao, configuracao de Windows, drivers e programas essenciais do computador."),
        ("Manutencao de software/banco de dados", "01.07.03", "01.07", 0, "Sim", "Manutencao corretiva, preventiva e atualizacao de sistemas ou banco de dados."),
        ("Formatacao e reinstalacao de sistema", "01.07.03", "01.07", 0, "Sim", "Formatacao, reinstalacao do sistema operacional, backup basico e configuracoes iniciais."),
        ("Paginas eletronicas / Web design", "01.08.01", "01.08", 0, "Sim", "Planejamento, criacao, manutencao e atualizacao de sites."),
        ("Manutencao de hardware/equipamentos", "14.01.01", "14.01", 0, "Sim", "Manutencao, reparo, limpeza, troca de pecas e revisao de computadores, notebooks e perifericos."),
    ]
    cadastrar_catalogo_ti(c, servicos_informatica_padrao)

    c.execute('''CREATE TABLE IF NOT EXISTS codigos_fiscais_produtos (
        id INT PRIMARY KEY AUTO_INCREMENT,
        nome TEXT,
        ncm VARCHAR(20),
        categoria VARCHAR(120),
        ativo VARCHAR(10) DEFAULT 'Sim',
        observacoes LONGTEXT
    )''')
    produtos_informatica_padrao = [
        ("Notebook ate 3,5 kg", "8471.30.12", "Informatica", "Computador portatil/notebook. Confirme a classificacao conforme configuracao do produto."),
        ("Notebook/outro portatil", "8471.30.19", "Informatica", "Outras maquinas automaticas portateis de processamento de dados."),
        ("Computador desktop / conjunto", "8471.49.00", "Informatica", "Computador apresentado como sistema/conjunto. Conferir se acompanha monitor/perifericos."),
        ("Monitor de informatica", "8528.52.00", "Informatica", "Monitor capaz de conexao direta a maquina de processamento de dados."),
        ("Impressora ou multifuncional", "8443.31.00", "Informatica", "Maquinas com duas ou mais funcoes, como impressao/copia/digitalizacao."),
        ("Teclado para computador", "8471.60.52", "Informatica", "Unidade de entrada: teclado."),
        ("Mouse para computador", "8471.60.53", "Informatica", "Unidade de entrada: mouse."),
        ("HD/SSD/unidade de armazenamento", "8471.70.40", "Informatica", "Unidade de memoria/armazenamento. Conferir modelo e tecnologia antes da nota."),
    ]
    for produto_padrao in produtos_informatica_padrao:
        c.execute("SELECT COUNT(*) AS total FROM codigos_fiscais_produtos WHERE ncm=?", (produto_padrao[1],))
        total_produto_padrao = c.fetchone()
        total_produto_padrao = total_produto_padrao.get("total") if isinstance(total_produto_padrao, dict) else total_produto_padrao[0]
        if not total_produto_padrao:
            c.execute(
                """INSERT INTO codigos_fiscais_produtos
                   (nome, ncm, categoria, ativo, observacoes)
                   VALUES (?,?,?,?,?)""",
                (produto_padrao[0], produto_padrao[1], produto_padrao[2], "Sim", produto_padrao[3]),
            )

    try: c.execute('ALTER TABLE usuarios ADD COLUMN perm_atendimentos INTEGER DEFAULT 0')
    except Exception: pass
    try: c.execute('ALTER TABLE usuarios ADD COLUMN perm_edit_atendimentos INTEGER DEFAULT 0')
    except Exception: pass

    try: c.execute('ALTER TABLE usuarios ADD COLUMN perm_clientes INTEGER DEFAULT 1')
    except Exception: pass
    try: c.execute("ALTER TABLE clientes ADD COLUMN cep TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE clientes ADD COLUMN emails_cobranca TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE clientes ADD COLUMN codigo_cliente TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE clientes ADD COLUMN documento_chave VARCHAR(20)")
    except Exception: pass
    try:
        c.execute("SHOW INDEX FROM clientes WHERE Key_name='nome'")
        if c.fetchone():
            c.execute("ALTER TABLE clientes DROP INDEX nome")
    except Exception:
        pass
    try:
        c.execute("SELECT cnpj FROM clientes WHERE COALESCE(cnpj,'')<>'' GROUP BY cnpj HAVING COUNT(*)=1")
        for doc_unico in [row[0] for row in c.fetchall()]:
            chave_doc = re.sub(r"\D", "", str(doc_unico or ""))
            if chave_doc:
                c.execute("UPDATE clientes SET documento_chave=? WHERE cnpj=? AND documento_chave IS NULL", (chave_doc, doc_unico))
        c.execute("CREATE UNIQUE INDEX uq_clientes_documento_chave ON clientes (documento_chave)")
    except Exception:
        pass
    try: c.execute("ALTER TABLE clientes ADD COLUMN funcionarios LONGTEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE clientes ADD COLUMN telefone_secundario TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE clientes ADD COLUMN redes_sociais LONGTEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE clientes ADD COLUMN logo_nome TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE clientes ADD COLUMN logo_mime TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE clientes ADD COLUMN logo LONGBLOB")
    except Exception: pass
    try: c.execute("ALTER TABLE clientes ADD COLUMN portal_username TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE clientes ADD COLUMN portal_password TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE clientes ADD COLUMN portal_trocar_senha INTEGER DEFAULT 1")
    except Exception: pass
    try: c.execute("ALTER TABLE clientes ADD COLUMN portal_2fa_secret TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE clientes ADD COLUMN portal_2fa_ativo INTEGER DEFAULT 0")
    except Exception: pass
    try: c.execute("ALTER TABLE clientes ADD COLUMN portal_ultimo_login TEXT")
    except Exception: pass
    for coluna_cliente_nova in [
        "pessoa", "endereco_padrao", "referencia", "codigo_ibge", "uf",
        "contato_padrao", "contato_cobranca", "contato", "estado_insc_estadual",
        "data_nascimento", "optante_simples_nacional", "ramo_atividade",
        "situacao_simples_nacional", "emite_nota_fiscal",
        "dias_antecedencia_faturamento", "dia_faturamento", "dia_vencimento",
    ]:
        try: c.execute(f"ALTER TABLE clientes ADD COLUMN {coluna_cliente_nova} TEXT")
        except Exception: pass
    try: c.execute("ALTER TABLE dsystem_arquivos ADD COLUMN caminho_arquivo TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE dsystem_arquivos ADD COLUMN url_arquivo TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE dsystem_arquivos ADD COLUMN armazenamento VARCHAR(40) DEFAULT 'banco'")
    except Exception: pass
    try: c.execute("ALTER TABLE dsystem_arquivos MODIFY COLUMN tamanho BIGINT")
    except Exception: pass
    try: c.execute("ALTER TABLE chamados_cliente ADD COLUMN area_destino VARCHAR(40) DEFAULT 'Suporte'")
    except Exception: pass
    try: c.execute("ALTER TABLE chamados_cliente ADD COLUMN funcionario_designado TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE chamados_cliente ADD COLUMN ajuste_tipo_atendimento TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE chamados_cliente ADD COLUMN ajuste_data TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE chamados_cliente ADD COLUMN ajuste_hora_inicio TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE chamados_cliente ADD COLUMN ajuste_hora_fim TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE chamados_cliente ADD COLUMN ajuste_descricao TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE chamados_cliente ADD COLUMN resposta_cliente TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE chamados_cliente ADD COLUMN administrador VARCHAR(120) DEFAULT 'Daniel.fabio'")
    except Exception: pass
    try: c.execute("ALTER TABLE ordens_servico ADD COLUMN tecnico_extra VARCHAR(255) DEFAULT ''")
    except Exception: pass
    try: c.execute("ALTER TABLE equipamentos_os ADD COLUMN numero_item TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE equipamentos_os ADD COLUMN tipo_equipamento TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE equipamentos_os ADD COLUMN avaria TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE equipamentos_os ADD COLUMN configuracao TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE equipamentos_os ADD COLUMN foto_nome TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE equipamentos_os ADD COLUMN foto_mime TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE equipamentos_os ADD COLUMN foto LONGBLOB")
    except Exception: pass
    try: c.execute("ALTER TABLE infra_v4 ADD COLUMN dvr_acessos LONGTEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE infra_v4 ADD COLUMN cameras_acessos LONGTEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE infra_v4 ADD COLUMN alarmes_acessos LONGTEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE infra_v4 ADD COLUMN aplicativos_acessos LONGTEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE infra_v4 ADD COLUMN pfsense_acessos LONGTEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE infra_v4 ADD COLUMN antivirus_acessos LONGTEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE infra_v4 ADD COLUMN setores LONGTEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE infra_v4 ADD COLUMN faixas_ip LONGTEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE infra_v4 ADD COLUMN vpn_acessos LONGTEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE infra_v4 ADD COLUMN hospedagem_acessos LONGTEXT")
    except Exception: pass
    for coluna_infra_nova in ("serv_anydesk", "serv_radmin", "serv_google_remote", "serv_info_gerais", "impressoras_acessos"):
        try: c.execute(f"ALTER TABLE infra_v4 ADD COLUMN {coluna_infra_nova} LONGTEXT")
        except Exception: pass
    try: c.execute("ALTER TABLE atendimentos_intervencoes ADD COLUMN proxima_preventiva TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE infra_equipamentos ADD COLUMN funcionario_usuario TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE infra_equipamentos ADD COLUMN funcionario_nome TEXT")
    except Exception: pass
    try: c.execute('ALTER TABLE usuarios ADD COLUMN perm_estoque INTEGER DEFAULT 1')
    except Exception: pass
    try: c.execute("ALTER TABLE estoque ADD COLUMN codigo_entrada VARCHAR(255) DEFAULT ''")
    except Exception: pass
    try: c.execute("ALTER TABLE estoque ADD COLUMN codigo_item INTEGER")
    except Exception: pass
    try: c.execute("ALTER TABLE estoque ADD COLUMN nome_generico VARCHAR(255) DEFAULT ''")
    except Exception: pass
    try: c.execute("ALTER TABLE estoque ADD COLUMN modelo VARCHAR(255) DEFAULT ''")
    except Exception: pass
    try: c.execute("ALTER TABLE estoque ADD COLUMN fileira VARCHAR(255) DEFAULT ''")
    except Exception: pass
    try: c.execute("ALTER TABLE estoque ADD COLUMN caixa VARCHAR(255) DEFAULT ''")
    except Exception: pass
    try: c.execute("ALTER TABLE estoque ADD COLUMN foto_nome TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE estoque ADD COLUMN foto_mime TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE estoque ADD COLUMN foto LONGBLOB")
    except Exception: pass
    for coluna_estoque_preco, tipo_estoque_preco in (
        ("custo_deslocamento", "DECIMAL(15,2) DEFAULT 0"),
        ("imposto_percentual", "DECIMAL(9,4) DEFAULT 0"),
        ("lucro_percentual", "DECIMAL(9,4) DEFAULT 0"),
        ("preco_revenda_automatico", "VARCHAR(5) DEFAULT 'Não'"),
        ("permitir_ajuste_preco", "INTEGER DEFAULT 0"),
        ("situacao_nota", "VARCHAR(30) DEFAULT 'Comprado com nota'"),
        ("tem_fonte", "VARCHAR(5) DEFAULT 'Não'"),
    ):
        try: c.execute(f"ALTER TABLE estoque ADD COLUMN {coluna_estoque_preco} {tipo_estoque_preco}")
        except Exception: pass
    try:
        c.execute("SELECT id, codigo_item, codigo_entrada, produto FROM estoque ORDER BY id")
        produtos_sem_codigo = [dict(item) for item in c.fetchall()]
        codigos_usados = set()
        for produto_codigo in produtos_sem_codigo:
            candidato = produto_codigo.get("codigo_item")
            if not str(candidato or "").strip().isdigit():
                parte_codigo = str(produto_codigo.get("codigo_entrada") or "").rsplit(".", 1)[-1].strip()
                candidato = parte_codigo if parte_codigo.isdigit() else None
            if not candidato and str(produto_codigo.get("produto") or "").strip().isdigit():
                candidato = str(produto_codigo.get("produto")).strip()
            candidato = int(candidato) if str(candidato or "").isdigit() else 0
            if candidato > 0 and candidato not in codigos_usados:
                produto_codigo["codigo_item"] = candidato
                codigos_usados.add(candidato)
                c.execute("UPDATE estoque SET codigo_item=? WHERE id=?", (candidato, produto_codigo.get("id")))
            else:
                produto_codigo["codigo_item"] = None
        proximo_codigo_livre = 1
        for produto_codigo in produtos_sem_codigo:
            if produto_codigo.get("codigo_item"):
                continue
            while proximo_codigo_livre in codigos_usados:
                proximo_codigo_livre += 1
            c.execute(
                "UPDATE estoque SET codigo_item=? WHERE id=?",
                (proximo_codigo_livre, produto_codigo.get("id")),
            )
            codigos_usados.add(proximo_codigo_livre)
    except Exception:
        pass
    try: c.execute('ALTER TABLE usuarios ADD COLUMN perm_faturamento INTEGER DEFAULT 0')
    except Exception: pass
    try: c.execute('ALTER TABLE usuarios ADD COLUMN modulo_gerencial INTEGER DEFAULT 0')
    except Exception: pass
    try: c.execute('ALTER TABLE usuarios ADD COLUMN modulo_financeiro INTEGER DEFAULT 0')
    except Exception: pass
    try: c.execute('ALTER TABLE usuarios ADD COLUMN modulo_faturamento INTEGER DEFAULT 0')
    except Exception: pass
    try: c.execute('ALTER TABLE usuarios ADD COLUMN modulo_operacional INTEGER DEFAULT 0')
    except Exception: pass
    try: c.execute("ALTER TABLE usuarios ADD COLUMN submodulos LONGTEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE usuarios ADD COLUMN empresas_permitidas LONGTEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE usuarios ADD COLUMN funcionario_nome TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE usuarios ADD COLUMN funcionario_cpf TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE usuarios ADD COLUMN funcionario_rj TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE usuarios ADD COLUMN funcionario_dados_bancarios TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE usuarios ADD COLUMN funcionario_telefone TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE usuarios ADD COLUMN funcionario_email TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE usuarios ADD COLUMN funcionario_endereco TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE usuarios ADD COLUMN funcionario_tipo_contrato TEXT")
    except Exception: pass
    for coluna_empresa_pj in ('funcionario_pj_razao_social','funcionario_pj_cnpj','funcionario_pj_endereco'):
        garantir_coluna(c,'usuarios',coluna_empresa_pj,'TEXT')
    try: c.execute("ALTER TABLE usuarios ADD COLUMN funcionario_forma_pagamento TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE usuarios ADD COLUMN funcionario_emite_nf TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE usuarios ADD COLUMN funcionario_deslocamento TEXT")
    except Exception: pass
    try: garantir_coluna(c, "usuarios", "trocar_senha", "INTEGER DEFAULT 0")
    except Exception: pass

 
    try: c.execute("ALTER TABLE clientes ADD COLUMN tipo VARCHAR(40) DEFAULT 'Cliente'")
    except Exception: pass
    try: c.execute("ALTER TABLE clientes ADD COLUMN insc_estadual VARCHAR(80) DEFAULT ''")
    except Exception: pass
    try: c.execute("ALTER TABLE clientes ADD COLUMN insc_municipal VARCHAR(80) DEFAULT ''")
    except Exception: pass
    try: c.execute("ALTER TABLE clientes ADD COLUMN substituto_tributario VARCHAR(20) DEFAULT 'Não'")
    except Exception: pass

 
    try: c.execute("ALTER TABLE orcamentos ADD COLUMN itens LONGTEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE orcamentos ADD COLUMN obs_pag TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE orcamentos ADD COLUMN obs_geral TEXT")
    except Exception: pass
    for coluna_orc, tipo_orc in [
        ("status", "VARCHAR(60) DEFAULT 'Aberto'"),
        ("empresa_aprovada", "TEXT"),
        ("tipo_faturamento_aprovado", "TEXT"),
        ("faturamento_id", "INTEGER"),
        ("data_validade", "VARCHAR(30)"),
        ("orcamento_origem_id", "INTEGER"),
        ("versao", "INTEGER DEFAULT 1"),
        ("enviado_email_em", "TEXT"),
        ("enviado_whatsapp_em", "TEXT"),
        ("juros_percentual", "DECIMAL(10,4) DEFAULT 0"),
        ("taxa_renegociacao", "DECIMAL(15,2) DEFAULT 0"),
        ("alterado_em", "TEXT"),
        ("alterado_por", "TEXT"),
    ]:
        try: c.execute(f"ALTER TABLE orcamentos ADD COLUMN {coluna_orc} {tipo_orc}")
        except Exception: pass

    c.execute("SELECT id FROM clientes WHERE codigo_cliente IS NULL OR codigo_cliente=''")
    clientes_sem_codigo = [row[0] for row in c.fetchall()]
    for cli_id in clientes_sem_codigo:
        c.execute("UPDATE clientes SET codigo_cliente=? WHERE id=?", (f"CLI{cli_id:05d}", cli_id))

    c.execute("SELECT * FROM usuarios WHERE is_admin=1 LIMIT 1")
    if not c.fetchone():
        admin_usuario = config_val("ADMIN_USERNAME", "Daniel.fabio")
        senha_admin = config_val("ADMIN_PASSWORD") or config_val("ADMINPASS") or config_val("SENHA_ADMIN_MASTER")
        if senha_admin:
            c.execute('''INSERT INTO usuarios (username, password, is_admin, perm_orcamentos, perm_del_orc, perm_os, perm_edit_os, perm_del_os, perm_emails, perm_edit_em, perm_del_em, perm_infra, perm_edit_infra, perm_del_infra, perm_clientes, perm_estoque, perm_faturamento) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', (admin_usuario, criar_hash_senha(senha_admin), 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1))

    usuario_recepcao = str(config_val("RECEPCAO_USERNAME", "recepcao") or "").strip()
    senha_recepcao = str(config_val("RECEPCAO_PASSWORD", "") or "")
    c.execute("SELECT id FROM usuarios WHERE LOWER(username)=LOWER(?) LIMIT 1", (usuario_recepcao,))
    recepcao_existente = c.fetchone()
    if usuario_recepcao and senha_recepcao and not recepcao_existente:
        c.execute('''INSERT INTO usuarios
            (username, password, trocar_senha, is_admin, perm_orcamentos, perm_del_orc,
             perm_os, perm_edit_os, perm_del_os, perm_emails, perm_edit_em, perm_del_em,
             perm_infra, perm_edit_infra, perm_del_infra, perm_clientes, perm_estoque,
             perm_faturamento, perm_atendimentos, perm_edit_atendimentos, submodulos,
             empresas_permitidas, funcionario_nome)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (usuario_recepcao, criar_hash_senha(senha_recepcao), 1, 0, 0, 0,
             1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0,
             0, 0, 0, json.dumps(["os.view", "os.edit", "recepcao.view", "recepcao.edit"]),
             "[]", "Recepção"))
    
    for coluna_bancaria in ("banco", "agencia", "numero_conta", "titular", "documento_titular", "chave_pix"):
        garantir_coluna(c, "financeiro_cadastros_aux", coluna_bancaria, "TEXT")
    from dsystem_erp.services.cadastros_planilha import COLUNAS
    for coluna_cadastro, tipo_cadastro in COLUNAS.items():
        garantir_coluna(c, "financeiro_cadastros_aux", coluna_cadastro, tipo_cadastro)
    # A proteção é aplicada pelo adaptador de conexão, sem exigir CREATE TRIGGER.
    registrar_migration(c, "000_schema_legado_iniciar_banco", "Schema atual criado e atualizado pelo iniciar_banco legado.")
    conn.commit()
    conn.close()
