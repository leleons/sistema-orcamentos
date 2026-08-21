CREATE DATABASE IF NOT EXISTS banco_dsystem CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE banco_dsystem;

CREATE TABLE IF NOT EXISTS logs_sistema (
  id INT AUTO_INCREMENT PRIMARY KEY,
  criado_em DATETIME,
  usuario VARCHAR(120),
  acao VARCHAR(40),
  tabela VARCHAR(120),
  registro_id VARCHAR(80),
  cliente VARCHAR(255),
  pagina VARCHAR(255),
  detalhes LONGTEXT,
  ip TEXT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS financeiro_cadastros_aux (
  id INT AUTO_INCREMENT PRIMARY KEY,
  tipo VARCHAR(80),
  nome TEXT,
  codigo TEXT,
  ativo VARCHAR(10) DEFAULT 'Sim',
  observacoes LONGTEXT,
  criado_por TEXT,
  criado_em TEXT,
  alterado_por TEXT,
  alterado_em TEXT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS clientes (
  id INT AUTO_INCREMENT PRIMARY KEY,
  nome VARCHAR(255),
  telefone VARCHAR(60),
  email VARCHAR(255),
  emails_cobranca TEXT,
  cnpj VARCHAR(60),
  rg_mei VARCHAR(120),
  endereco TEXT,
  numero VARCHAR(30),
  complemento VARCHAR(255),
  bairro VARCHAR(120),
    cidade_estado VARCHAR(120),
    cep VARCHAR(30),
    pessoa VARCHAR(40),
    endereco_padrao VARCHAR(20),
    referencia VARCHAR(255),
    codigo_ibge VARCHAR(40),
    uf VARCHAR(80),
    contato_padrao VARCHAR(20),
    contato_cobranca VARCHAR(20),
    contato VARCHAR(255),
    estado_insc_estadual VARCHAR(120),
    data_nascimento VARCHAR(30),
    optante_simples_nacional VARCHAR(20),
    ramo_atividade VARCHAR(255),
    dias_antecedencia_faturamento VARCHAR(30),
    dia_faturamento VARCHAR(30),
    dia_vencimento VARCHAR(30),
    funcionarios LONGTEXT,
  tipo VARCHAR(40) DEFAULT 'Cliente',
  insc_estadual VARCHAR(80) DEFAULT '',
  insc_municipal VARCHAR(80) DEFAULT '',
  substituto_tributario VARCHAR(20) DEFAULT 'Não',
  codigo_cliente VARCHAR(30),
  documento_chave VARCHAR(20) UNIQUE,
  telefone_secundario VARCHAR(60),
  redes_sociais LONGTEXT,
  logo_nome TEXT,
  logo_mime TEXT,
  logo LONGBLOB,
  portal_username VARCHAR(120),
  portal_password VARCHAR(255),
  portal_trocar_senha TINYINT DEFAULT 1,
  portal_2fa_secret VARCHAR(255),
  portal_2fa_ativo TINYINT DEFAULT 0,
  portal_ultimo_login VARCHAR(30)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS clientes_portal_usuarios (
  id INT AUTO_INCREMENT PRIMARY KEY,
  cliente_id INT NOT NULL,
  username VARCHAR(255) NOT NULL UNIQUE,
  nome VARCHAR(255),
  cargo VARCHAR(255),
  tipo VARCHAR(30) DEFAULT 'Funcionário',
  password VARCHAR(255),
  trocar_senha TINYINT DEFAULT 1,
  twofa_secret VARCHAR(255),
  twofa_ativo TINYINT DEFAULT 0,
  ultimo_login VARCHAR(30),
  ativo TINYINT DEFAULT 1,
  criado_em VARCHAR(30),
  INDEX idx_portal_usuario_cliente (cliente_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS usuarios (
  id INT AUTO_INCREMENT PRIMARY KEY,
  username VARCHAR(120) UNIQUE,
  password VARCHAR(255),
  trocar_senha TINYINT DEFAULT 0,
  is_admin TINYINT DEFAULT 0,
  perm_orcamentos TINYINT DEFAULT 0,
  perm_del_orc TINYINT DEFAULT 0,
  perm_os TINYINT DEFAULT 0,
  perm_edit_os TINYINT DEFAULT 0,
  perm_del_os TINYINT DEFAULT 0,
  perm_emails TINYINT DEFAULT 1,
  perm_edit_em TINYINT DEFAULT 0,
  perm_del_em TINYINT DEFAULT 0,
  perm_infra TINYINT DEFAULT 1,
  perm_edit_infra TINYINT DEFAULT 0,
  perm_del_infra TINYINT DEFAULT 0,
  perm_clientes TINYINT DEFAULT 1,
  perm_estoque TINYINT DEFAULT 1,
  perm_faturamento TINYINT DEFAULT 0,
  perm_atendimentos TINYINT DEFAULT 0,
  perm_edit_atendimentos TINYINT DEFAULT 0,
  modulo_gerencial TINYINT DEFAULT 0,
  modulo_financeiro TINYINT DEFAULT 0,
  modulo_faturamento TINYINT DEFAULT 0,
  modulo_operacional TINYINT DEFAULT 0,
  submodulos LONGTEXT,
  empresas_permitidas LONGTEXT,
  funcionario_nome VARCHAR(255),
  funcionario_cpf VARCHAR(60),
  funcionario_rj VARCHAR(60),
  funcionario_dados_bancarios TEXT,
  funcionario_telefone VARCHAR(60),
  funcionario_email VARCHAR(255),
  funcionario_endereco TEXT,
  funcionario_tipo_contrato VARCHAR(80),
  funcionario_forma_pagamento VARCHAR(80),
  funcionario_emite_nf VARCHAR(20),
  funcionario_deslocamento LONGTEXT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS orcamentos (
  orc_id INT AUTO_INCREMENT PRIMARY KEY,
  numero VARCHAR(60),
  data_orc VARCHAR(30),
  cliente VARCHAR(255),
  cpf_cnpj VARCHAR(60),
  valor_total VARCHAR(60),
  forma_pagamento VARCHAR(120),
  itens LONGTEXT,
  obs_pag TEXT,
  obs_geral TEXT,
  status VARCHAR(60) DEFAULT 'Aberto',
  empresa_aprovada TEXT,
  tipo_faturamento_aprovado TEXT,
  faturamento_id INT,
  data_validade VARCHAR(30),
  orcamento_origem_id INT,
  versao INT DEFAULT 1,
  enviado_email_em TEXT,
  enviado_whatsapp_em TEXT,
  juros_percentual DECIMAL(10,4) DEFAULT 0,
  taxa_renegociacao DECIMAL(15,2) DEFAULT 0,
  alterado_em TEXT,
  alterado_por TEXT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS orcamento_pdfs (
  id INT AUTO_INCREMENT PRIMARY KEY,
  orc_id INT,
  empresa VARCHAR(80),
  nome_arquivo TEXT,
  mime_type TEXT,
  arquivo LONGBLOB,
  criado_por TEXT,
  criado_em TEXT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS ordens_servico (
  os_id INT AUTO_INCREMENT PRIMARY KEY,
  data_os VARCHAR(30),
  cliente VARCHAR(255),
  cpf_cnpj VARCHAR(60),
  endereco TEXT,
  equipamento LONGTEXT,
  marca LONGTEXT,
  avaria LONGTEXT,
  servico LONGTEXT,
  atendente VARCHAR(255),
  so VARCHAR(120),
  formatar VARCHAR(20),
  backup VARCHAR(20),
  aplicativos VARCHAR(20),
  fonte VARCHAR(20),
  hd_ssd VARCHAR(120),
  ram VARCHAR(120),
  cpu VARCHAR(120),
  gpu VARCHAR(120),
  placa_mae VARCHAR(255),
  gabinete VARCHAR(120),
  chave_so VARCHAR(255),
  app_especifico_check VARCHAR(20),
  app_especifico_nome VARCHAR(255),
  tecnico_extra VARCHAR(255) DEFAULT '',
  chamado_id INT,
  recebido_por VARCHAR(255),
  recebido_em VARCHAR(30)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS emails_clientes (
  id INT AUTO_INCREMENT PRIMARY KEY,
  cliente_vinculado VARCHAR(255),
  funcionario VARCHAR(255),
  email VARCHAR(255),
  senha VARCHAR(255),
  aliases TEXT,
  provedor VARCHAR(120),
  config_entrada TEXT,
  config_saida TEXT,
  capacidade VARCHAR(120),
  data_verificacao VARCHAR(30),
  backup_realizado VARCHAR(20),
  data_backup VARCHAR(30)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS infra_v4 (
  id INT AUTO_INCREMENT PRIMARY KEY,
  cliente_vinc VARCHAR(255),
  fantasia VARCHAR(255),
  razao VARCHAR(255),
  cnpj VARCHAR(60),
  endereco TEXT,
  contato VARCHAR(255),
  email_prin VARCHAR(255),
  tel_prin VARCHAR(60),
  tel_prov VARCHAR(60),
  contrato_data VARCHAR(30),
  pagto VARCHAR(120),
  venc VARCHAR(30),
  sys_dados LONGTEXT,
  sys_serial LONGTEXT,
  sys_cod LONGTEXT,
  sys_adm LONGTEXT,
  sys_senha LONGTEXT,
  sys_sec LONGTEXT,
  rede_prov LONGTEXT,
  rede_ip LONGTEXT,
  rede_log LONGTEXT,
  rede_sen LONGTEXT,
  rede_ddns LONGTEXT,
  rede_dsen LONGTEXT,
  rede_wire LONGTEXT,
  rede_wsen LONGTEXT,
  serv_nome LONGTEXT,
  serv_ip LONGTEXT,
  serv_link LONGTEXT,
  serv_log LONGTEXT,
  serv_sen LONGTEXT,
  cert_log LONGTEXT,
  cert_sen LONGTEXT,
  fin_b1 LONGTEXT,
  fin_b2 LONGTEXT,
  fin_b3 LONGTEXT,
  pcs_acessos LONGTEXT,
  dvr_acessos LONGTEXT,
  cameras_acessos LONGTEXT,
  alarmes_acessos LONGTEXT,
  aplicativos_acessos LONGTEXT,
  pfsense_acessos LONGTEXT,
  antivirus_acessos LONGTEXT,
  faixas_ip LONGTEXT,
  vpn_acessos LONGTEXT,
  hospedagem_acessos LONGTEXT,
  setores LONGTEXT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS estoque (
  id INT AUTO_INCREMENT PRIMARY KEY,
    codigo VARCHAR(120),
    codigo_entrada VARCHAR(120),
    produto VARCHAR(255),
    nome_generico VARCHAR(255),
    categoria VARCHAR(120),
  fileira VARCHAR(120),
  caixa VARCHAR(120),
  quantidade INT DEFAULT 0,
  estoque_minimo INT DEFAULT 0,
  valor_custo VARCHAR(60),
  valor_venda VARCHAR(60),
  custo_deslocamento DECIMAL(15,2) DEFAULT 0,
  imposto_percentual DECIMAL(9,4) DEFAULT 0,
  lucro_percentual DECIMAL(9,4) DEFAULT 0,
  preco_revenda_automatico VARCHAR(5) DEFAULT 'Não',
  permitir_ajuste_preco INTEGER DEFAULT 0,
  situacao_nota VARCHAR(30) DEFAULT 'Comprado com nota',
  fornecedor VARCHAR(255),
  observacoes TEXT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS pedidos_compra (
  id INT AUTO_INCREMENT PRIMARY KEY,
  data_pedido VARCHAR(30),
  produto_id INT,
  codigo VARCHAR(120),
  produto VARCHAR(255),
  quantidade_solicitada INT,
  fornecedor VARCHAR(255),
  status VARCHAR(60),
  observacoes TEXT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS cotacoes_compra (
  id INT AUTO_INCREMENT PRIMARY KEY,
  pedido_compra_id INT NOT NULL,
  fornecedor VARCHAR(255) NOT NULL,
  telefone VARCHAR(80),
  meio_compra VARCHAR(40) NOT NULL,
  valor_item DECIMAL(15,2) NOT NULL,
  observacoes TEXT,
  escolhida INTEGER DEFAULT 0,
  criado_por VARCHAR(255),
  criado_em VARCHAR(30),
  INDEX idx_cotacoes_pedido (pedido_compra_id),
  CONSTRAINT fk_cotacoes_pedido FOREIGN KEY (pedido_compra_id) REFERENCES pedidos_compra(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS faturamento (
  id INT AUTO_INCREMENT PRIMARY KEY,
  data_lanc VARCHAR(30),
  cliente VARCHAR(255),
  cnpj VARCHAR(60),
  tipo VARCHAR(60),
  emite_nf VARCHAR(20),
  tipo_nota VARCHAR(60),
  forma_pag VARCHAR(120),
  itens LONGTEXT,
  valor_total DECIMAL(12,2) DEFAULT 0,
  parcelas VARCHAR(30),
  vencimento VARCHAR(30),
  orc_ref VARCHAR(60),
  obs_interna TEXT,
  obs_nota TEXT,
  nota_fiscal TEXT,
  boleto TEXT,
  status VARCHAR(60) DEFAULT 'Aberto',
  alterado_por TEXT,
  alterado_em TEXT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS faturamento_anexos (
  id INT AUTO_INCREMENT PRIMARY KEY,
  faturamento_id INT,
  tipo VARCHAR(80),
  nome_arquivo TEXT,
  mime_type TEXT,
  arquivo LONGBLOB,
  criado_por TEXT,
  criado_em TEXT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS notas_fiscais (
  id INT AUTO_INCREMENT PRIMARY KEY,
  faturamento_id INT,
  cliente VARCHAR(255),
  cpf_cnpj VARCHAR(60),
  tipo_nota VARCHAR(60),
  data_competencia VARCHAR(30),
  descricao LONGTEXT,
  valor_servicos DECIMAL(14,2) DEFAULT 0,
  aliquota_iss DECIMAL(8,4) DEFAULT 0,
  valor_iss DECIMAL(14,2) DEFAULT 0,
  codigo_servico VARCHAR(120),
  municipio_prestacao VARCHAR(255),
  status VARCHAR(60) DEFAULT 'Pendente',
  numero_nota VARCHAR(120),
  chave_acesso VARCHAR(255),
  link_nota LONGTEXT,
  observacoes LONGTEXT,
  criado_por VARCHAR(120),
  criado_em VARCHAR(30),
  emitido_em VARCHAR(30),
  xml_envio LONGTEXT,
  xml_retorno LONGTEXT,
  xml_autorizado LONGTEXT,
  pdf_base64 LONGTEXT,
  protocolo TEXT,
  mensagem_retorno LONGTEXT,
  numero_lote TEXT,
  atualizado_em TEXT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS cobrancas_recorrentes (
  id INT AUTO_INCREMENT PRIMARY KEY,
  cliente_id INT,
  cliente_nome VARCHAR(255),
  tipo_cobranca VARCHAR(120),
  valor_financeiro DECIMAL(12,2) DEFAULT 0,
  data_emprestimo_locacao VARCHAR(30),
  motivo LONGTEXT,
  tipo_backup VARCHAR(120),
  quantidade INT DEFAULT 0,
  servidor_backup TEXT,
  maquina_backup TEXT,
  data_cobranca VARCHAR(30),
  valor_cobranca DECIMAL(12,2) DEFAULT 0,
  vigencia_inicio VARCHAR(30),
  vigencia_fim VARCHAR(30),
  licencas_servidor INT DEFAULT 0,
  licencas_maquinas INT DEFAULT 0,
  pagamento VARCHAR(120),
  periodicidade VARCHAR(40),
  informacoes LONGTEXT,
  status VARCHAR(40) DEFAULT 'Ativa',
  criado_por VARCHAR(120),
  criado_em VARCHAR(30)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS cobrancas_renovacoes (
  id INT AUTO_INCREMENT PRIMARY KEY,
  cobranca_id INT,
  data_renovacao VARCHAR(30),
  vigencia_inicio_anterior VARCHAR(30),
  vigencia_fim_anterior VARCHAR(30),
  vigencia_inicio_nova VARCHAR(30),
  vigencia_fim_nova VARCHAR(30),
  valor_cobranca DECIMAL(12,2) DEFAULT 0,
  observacao LONGTEXT,
  criado_por VARCHAR(120),
  criado_em VARCHAR(30)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS contas_pagar (
  id INT AUTO_INCREMENT PRIMARY KEY,
  fornecedor VARCHAR(255), cpf_cnpj VARCHAR(60), numero_documento VARCHAR(120), tipo_documento VARCHAR(80),
  categoria VARCHAR(120), centro_custo VARCHAR(120), plano_contas VARCHAR(120), conta_bancaria VARCHAR(120),
  data_emissao VARCHAR(30), data_competencia VARCHAR(30), data_vencimento VARCHAR(30),
  valor_original DECIMAL(14,2) DEFAULT 0, desconto DECIMAL(14,2) DEFAULT 0, juros DECIMAL(14,2) DEFAULT 0,
  multa DECIMAL(14,2) DEFAULT 0, valor_total DECIMAL(14,2) DEFAULT 0, forma_pagamento VARCHAR(80),
  codigo_barras LONGTEXT, chave_pix VARCHAR(255), status VARCHAR(60) DEFAULT 'Aberto', observacoes LONGTEXT,
  data_baixa VARCHAR(30), valor_baixado DECIMAL(14,2) DEFAULT 0, baixado_por VARCHAR(120),
  criado_por VARCHAR(120), criado_em VARCHAR(30), alterado_por VARCHAR(120), alterado_em VARCHAR(30),
  anexo_nome TEXT, anexo_mime TEXT, anexo LONGBLOB, comprovante_nome TEXT, comprovante_mime TEXT, comprovante LONGBLOB,
  conta_baixa TEXT, forma_baixa TEXT, observacao_baixa LONGTEXT, taxas_baixa DECIMAL(14,2) DEFAULT 0,
  juros_baixa DECIMAL(14,2) DEFAULT 0, multa_baixa DECIMAL(14,2) DEFAULT 0, desconto_baixa DECIMAL(14,2) DEFAULT 0,
  cancelado_por TEXT, motivo_cancelamento LONGTEXT, solicitante TEXT, aprovador TEXT,
  status_aprovacao VARCHAR(60) DEFAULT 'Pendente', motivo_reprovacao LONGTEXT, data_aprovacao TEXT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS contas_receber (
  id INT AUTO_INCREMENT PRIMARY KEY,
  cliente_id INT, cliente VARCHAR(255), cpf_cnpj VARCHAR(60), numero_documento VARCHAR(120),
  tipo_receita VARCHAR(120), categoria VARCHAR(120), centro_receita VARCHAR(120), plano_contas VARCHAR(120),
  conta_bancaria VARCHAR(120), data_emissao VARCHAR(30), data_competencia VARCHAR(30), data_vencimento VARCHAR(30),
  valor_original DECIMAL(14,2) DEFAULT 0, desconto DECIMAL(14,2) DEFAULT 0, juros DECIMAL(14,2) DEFAULT 0,
  multa DECIMAL(14,2) DEFAULT 0, valor_total DECIMAL(14,2) DEFAULT 0, forma_recebimento VARCHAR(80),
  nota_fiscal VARCHAR(120), boleto LONGTEXT, status VARCHAR(60) DEFAULT 'Aberto', observacoes LONGTEXT,
  data_baixa VARCHAR(30), valor_baixado DECIMAL(14,2) DEFAULT 0, baixado_por VARCHAR(120),
  criado_por VARCHAR(120), criado_em VARCHAR(30), alterado_por VARCHAR(120), alterado_em VARCHAR(30),
  anexo_nome TEXT, anexo_mime TEXT, anexo LONGBLOB, comprovante_nome TEXT, comprovante_mime TEXT, comprovante LONGBLOB,
  conta_baixa TEXT, forma_baixa TEXT, observacao_baixa LONGTEXT, taxas_baixa DECIMAL(14,2) DEFAULT 0,
  juros_baixa DECIMAL(14,2) DEFAULT 0, multa_baixa DECIMAL(14,2) DEFAULT 0, desconto_baixa DECIMAL(14,2) DEFAULT 0,
  cancelado_por TEXT, motivo_cancelamento LONGTEXT,
  regime_tributario VARCHAR(40) DEFAULT 'Normal', impostos LONGTEXT, simples_aliquota DECIMAL(10,4) DEFAULT 0,
  simples_valor DECIMAL(14,2) DEFAULT 0, taxas_personalizadas LONGTEXT, valor_impostos DECIMAL(14,2) DEFAULT 0,
  valor_liquido DECIMAL(14,2) DEFAULT 0, parcelado VARCHAR(10) DEFAULT 'Não', quantidade_parcelas INT DEFAULT 1,
  meio_parcelamento VARCHAR(60), parcelas_detalhes LONGTEXT, bandeira_cartao VARCHAR(40),
  custo_tipo VARCHAR(20), pedido_compra_id INT, fornecedor_custo VARCHAR(255),
  custo_unitario DECIMAL(14,2) DEFAULT 0, quantidade_custo DECIMAL(14,3) DEFAULT 1,
  custo_total DECIMAL(14,2) DEFAULT 0, lucro_estimado DECIMAL(14,2) DEFAULT 0,
  margem_lucro_percentual DECIMAL(10,4) DEFAULT 0,
  cobranca_recorrente_id INT, cobranca_competencia VARCHAR(30),
  UNIQUE KEY uq_conta_receber_recorrencia (cobranca_recorrente_id, cobranca_competencia)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS financeiro_impostos_taxas (
  id INT AUTO_INCREMENT PRIMARY KEY, nome VARCHAR(120) UNIQUE, tipo VARCHAR(30) DEFAULT 'Imposto',
  aliquota_padrao DECIMAL(10,4) DEFAULT 0, ativo VARCHAR(10) DEFAULT 'Sim', criado_por TEXT, criado_em TEXT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS contratos (
  id INT AUTO_INCREMENT PRIMARY KEY, tipo VARCHAR(100), parte_tipo VARCHAR(40), parte_id INT,
  parte_nome VARCHAR(255), nome_arquivo TEXT, mime_type VARCHAR(120), arquivo LONGBLOB,
  status VARCHAR(40) DEFAULT 'Ativo', valor VARCHAR(80), data_inicio VARCHAR(30),
  data_vencimento VARCHAR(30), observacoes LONGTEXT, criado_por VARCHAR(120), criado_em VARCHAR(30),
  alterado_por VARCHAR(120), alterado_em VARCHAR(30), INDEX idx_contratos_parte (parte_tipo, parte_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS financeiro_recorrencias_v2 (
  id INT AUTO_INCREMENT PRIMARY KEY, tipo VARCHAR(20), parte VARCHAR(255), cpf_cnpj VARCHAR(60),
  descricao TEXT, valor DECIMAL(14,2) DEFAULT 0, frequencia VARCHAR(40), dia_vencimento INT,
  data_inicial VARCHAR(30), data_final VARCHAR(30), centro VARCHAR(120), categoria VARCHAR(120),
  gerar_automaticamente VARCHAR(10), ativo VARCHAR(10) DEFAULT 'Sim', ultima_geracao VARCHAR(30),
  criado_por VARCHAR(120), criado_em VARCHAR(30)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS financeiro_cobrancas_v2 (
  id INT AUTO_INCREMENT PRIMARY KEY, conta_receber_id INT, cliente VARCHAR(255), dias_atraso INT,
  valor_atualizado DECIMAL(14,2) DEFAULT 0, historico LONGTEXT, status VARCHAR(60),
  proxima_acao VARCHAR(30), responsavel VARCHAR(120), observacoes LONGTEXT,
  criado_em VARCHAR(30), alterado_em VARCHAR(30)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS financeiro_renegociacoes_v2 (
  id INT AUTO_INCREMENT PRIMARY KEY, tipo VARCHAR(20), parte VARCHAR(255), titulos_originais TEXT,
  valor_original DECIMAL(14,2) DEFAULT 0, valor_renegociado DECIMAL(14,2) DEFAULT 0,
  entrada DECIMAL(14,2) DEFAULT 0, parcelas INT DEFAULT 1, primeiro_vencimento VARCHAR(30),
  juros DECIMAL(14,2) DEFAULT 0, multa DECIMAL(14,2) DEFAULT 0, desconto DECIMAL(14,2) DEFAULT 0,
  status VARCHAR(40) DEFAULT 'Ativo', observacoes LONGTEXT, criado_por VARCHAR(120), criado_em VARCHAR(30)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS atendimentos_checklist (
  id INT AUTO_INCREMENT PRIMARY KEY,
  tipo_atendimento VARCHAR(120),
  cliente VARCHAR(255),
  equipamento VARCHAR(255),
  funcionario_atendido VARCHAR(255),
  maquinas_atendidas TEXT,
  tecnicos VARCHAR(255),
  data_entrada VARCHAR(30),
  status VARCHAR(60),
  obs_entrada TEXT,
  formatacao VARCHAR(20),
  bkp_convencionais VARCHAR(20),
  bkp_c VARCHAR(20),
  bkp_nav VARCHAR(20),
  bkp_email VARCHAR(20),
  data_backup VARCHAR(30),
  pasta_dsys VARCHAR(20),
  limpeza_int VARCHAR(20),
  limpeza_ext VARCHAR(20),
  verif_update VARCHAR(20),
  soft_indesejado VARCHAR(20),
  confirma_soft VARCHAR(20),
  bkp_retornou VARCHAR(20),
  testado_hw VARCHAR(20),
  sacola VARCHAR(20),
  verif_desempenho VARCHAR(20),
  obs_desempenho TEXT,
  detalhes_realizado TEXT,
  senhas_alteradas TEXT,
  historico LONGTEXT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS atendimentos_intervencoes (
  id INT AUTO_INCREMENT PRIMARY KEY,
  cliente_id INT,
  cliente_nome VARCHAR(255),
  equipamento VARCHAR(255),
  identificacao VARCHAR(255),
  tipo_equipamento VARCHAR(120),
  quem_usa VARCHAR(255),
  tecnico VARCHAR(255),
  data_intervencao VARCHAR(30),
  descricao LONGTEXT,
  preventiva_prevista VARCHAR(20) DEFAULT 'Não',
  periodo_preventiva VARCHAR(60),
  preventiva_realizada VARCHAR(20) DEFAULT 'Não',
  data_preventiva VARCHAR(30),
  proxima_preventiva VARCHAR(30),
  observacoes LONGTEXT,
  criado_por VARCHAR(120),
  criado_em VARCHAR(30)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS agenda_visitas (
  id INT AUTO_INCREMENT PRIMARY KEY,
  tecnico VARCHAR(255),
  cliente_id INT,
  cliente_nome VARCHAR(255),
  data_visita VARCHAR(30),
  hora_inicio VARCHAR(20),
  hora_fim VARCHAR(20),
  tipo_visita VARCHAR(120),
  descricao TEXT,
  status VARCHAR(60) DEFAULT 'Agendado',
  criado_em VARCHAR(30)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS infra_equipamentos (
  id INT AUTO_INCREMENT PRIMARY KEY,
  cliente_id INT,
  cliente_nome VARCHAR(255),
  funcionario_usuario VARCHAR(120),
  funcionario_nome VARCHAR(255),
  origem VARCHAR(80),
  tipo_equipamento VARCHAR(80),
  nome_equipamento VARCHAR(255),
  ip_equipamento VARCHAR(80),
  quem_usa VARCHAR(255),
  informacoes LONGTEXT,
  criado_por VARCHAR(120),
  criado_em VARCHAR(30)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS infra_equipamentos_fotos (
  id INT AUTO_INCREMENT PRIMARY KEY,
  equipamento_id INT,
  foto_nome TEXT,
  foto_mime TEXT,
  foto LONGBLOB,
  criado_em VARCHAR(30)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS infra_item_fotos (
  id INT AUTO_INCREMENT PRIMARY KEY,
  ficha_id INT,
  tipo_item VARCHAR(40),
  item_indice INT,
  item_nome TEXT,
  foto_nome TEXT,
  foto_mime TEXT,
  foto LONGBLOB,
  criado_em VARCHAR(30)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS autorizacoes_cliente (
  id INT AUTO_INCREMENT PRIMARY KEY,
  cliente VARCHAR(255),
  os_id INT,
  servico TEXT,
  status VARCHAR(60),
  observacao TEXT,
  criado_em VARCHAR(30)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS chamados_cliente (
  id INT AUTO_INCREMENT PRIMARY KEY,
  cliente_id INT,
  cliente_nome VARCHAR(255),
  solicitante VARCHAR(255),
  tipo_atendimento VARCHAR(80),
  data_solicitada VARCHAR(30),
  hora_inicio VARCHAR(20),
  hora_fim VARCHAR(20),
  titulo VARCHAR(255),
  descricao TEXT,
  status VARCHAR(80) DEFAULT 'Novo',
  administrador VARCHAR(120) DEFAULT 'Daniel.fabio',
  funcionario_designado VARCHAR(120),
  ajuste_tipo_atendimento VARCHAR(80),
  ajuste_data VARCHAR(30),
  ajuste_hora_inicio VARCHAR(20),
  ajuste_hora_fim VARCHAR(20),
  ajuste_descricao TEXT,
  resposta_cliente TEXT,
  criado_por VARCHAR(120),
  criado_em VARCHAR(30),
  atualizado_em VARCHAR(30)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS chamados_mensagens (
  id INT AUTO_INCREMENT PRIMARY KEY,
  chamado_id INT,
  autor_tipo VARCHAR(40),
  autor_nome VARCHAR(255),
  mensagem LONGTEXT,
  anexo_nome TEXT,
  anexo_mime TEXT,
  anexo LONGBLOB,
  criado_em VARCHAR(30)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS propostas_contratos_cliente (
  id INT AUTO_INCREMENT PRIMARY KEY,
  cliente_id INT,
  cliente_nome VARCHAR(255),
  tipo VARCHAR(60),
  titulo VARCHAR(255),
  descricao TEXT,
  nome_arquivo VARCHAR(255),
  mime_type VARCHAR(120),
  arquivo LONGBLOB,
  status VARCHAR(80) DEFAULT 'Pendente',
  resposta_cliente TEXT,
  criado_por VARCHAR(120),
  criado_em VARCHAR(30),
  respondido_em VARCHAR(30)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS contrato_clausulas (
  id INT AUTO_INCREMENT PRIMARY KEY,
  tipo_contrato VARCHAR(80),
  titulo TEXT,
  texto LONGTEXT,
  ativo VARCHAR(10) DEFAULT 'Sim',
  criado_por VARCHAR(120),
  criado_em VARCHAR(30),
  alterado_por VARCHAR(120),
  alterado_em VARCHAR(30)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS dsystem_arquivos (
  id INT AUTO_INCREMENT PRIMARY KEY,
  pasta VARCHAR(255),
  nome_arquivo VARCHAR(255),
  mime_type VARCHAR(120),
  tamanho BIGINT,
  arquivo LONGBLOB,
  caminho_arquivo TEXT,
  url_arquivo TEXT,
  armazenamento VARCHAR(40) DEFAULT 'banco',
  criado_por VARCHAR(120),
  criado_em VARCHAR(30)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS checklist_interno (
  id INT AUTO_INCREMENT PRIMARY KEY,
  cliente VARCHAR(255),
  tipo_atendimento VARCHAR(120),
  equipamento VARCHAR(255),
  tecnicos VARCHAR(255),
  data_entrada VARCHAR(30),
  status VARCHAR(60),
  obs_entrada TEXT,
  formatacao VARCHAR(20),
  bkp_convencionais VARCHAR(20),
  bkp_c VARCHAR(20),
  bkp_nav VARCHAR(20),
  bkp_email VARCHAR(20),
  pasta_dsys VARCHAR(20),
  limpeza_int VARCHAR(20),
  limpeza_ext VARCHAR(20),
  verif_update VARCHAR(20),
  soft_indesejado VARCHAR(20),
  confirma_soft VARCHAR(20),
  bkp_retornou VARCHAR(20),
  testado_hw VARCHAR(20),
  sacola VARCHAR(20),
  historico LONGTEXT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS equipamentos_os (
  id INT AUTO_INCREMENT PRIMARY KEY,
  os_id INT,
  numero_item VARCHAR(30),
  letra_equipamento VARCHAR(10),
  tipo_equipamento VARCHAR(60),
  equipamento VARCHAR(255),
  marca VARCHAR(255),
  numero_serie VARCHAR(255),
  avaria VARCHAR(20),
  defeito TEXT,
  servico TEXT,
  configuracao LONGTEXT,
  kanban_status VARCHAR(60) DEFAULT 'Recebido',
  etiqueta_codigo VARCHAR(80),
  kanban_alterado_por VARCHAR(255),
  kanban_alterado_em VARCHAR(30),
  kanban_ordem INT DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS funcionarios (
  id INT AUTO_INCREMENT PRIMARY KEY,
  codigo_funcionario INT,
  nome VARCHAR(255),
  cargo VARCHAR(120),
  telefone VARCHAR(60),
  email VARCHAR(255),
  modulo_gerencial TINYINT DEFAULT 0,
  modulo_financeiro TINYINT DEFAULT 0,
  modulo_faturamento TINYINT DEFAULT 0,
  modulo_operacional TINYINT DEFAULT 0,
  submodulos LONGTEXT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS infraestrutura_ti (
  id INT AUTO_INCREMENT PRIMARY KEY,
  cliente_vinculado VARCHAR(255),
  tipo VARCHAR(120),
  equipamento VARCHAR(255),
  marca VARCHAR(255),
  modelo VARCHAR(255),
  serial VARCHAR(255),
  ip VARCHAR(120),
  usuario VARCHAR(255),
  senha VARCHAR(255),
  wifi_nome VARCHAR(255),
  wifi_senha VARCHAR(255),
  remote_acesso VARCHAR(255),
  remote_email VARCHAR(255),
  remote_maquina VARCHAR(255),
  tipo_computador VARCHAR(120),
  observacoes TEXT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS solicitacoes_compra (
  id INT AUTO_INCREMENT PRIMARY KEY,
  produto VARCHAR(255),
  quantidade INT,
  fornecedor VARCHAR(255),
  status VARCHAR(60),
  data_solicitacao VARCHAR(30)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
