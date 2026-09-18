CREATE TABLE IF NOT EXISTS garantias_clientes (
  id INT AUTO_INCREMENT PRIMARY KEY,
  numero VARCHAR(40) NOT NULL UNIQUE,
  cliente_id INT NOT NULL,
  cliente VARCHAR(255) NOT NULL,
  cliente_documento VARCHAR(60),
  faturamento_id INT,
  data_emissao VARCHAR(30) NOT NULL,
  origem VARCHAR(255),
  itens LONGTEXT,
  condicoes LONGTEXT,
  historico LONGTEXT,
  status VARCHAR(30) DEFAULT 'Emitida',
  pdf_nome TEXT,
  pdf_mime TEXT,
  pdf LONGBLOB,
  criado_por VARCHAR(120),
  criado_em VARCHAR(30),
  alterado_por VARCHAR(120),
  alterado_em VARCHAR(30),
  INDEX idx_garantia_cliente (cliente_id),
  INDEX idx_garantia_faturamento (faturamento_id)
);

ALTER TABLE faturamento
  ADD COLUMN modalidade_faturamento VARCHAR(30) DEFAULT 'Por item',
  ADD COLUMN medicao_numero VARCHAR(80),
  ADD COLUMN medicao_inicio VARCHAR(30),
  ADD COLUMN medicao_fim VARCHAR(30),
  ADD COLUMN medicao_percentual DECIMAL(10,4) DEFAULT 0,
  ADD COLUMN medicao_referencia TEXT,
  ADD COLUMN medicao_historico LONGTEXT;

ALTER TABLE contratos
  ADD COLUMN assinado VARCHAR(10) DEFAULT 'Não',
  ADD COLUMN data_assinatura VARCHAR(30),
  ADD COLUMN gerar_recorrencia VARCHAR(10) DEFAULT 'Não',
  ADD COLUMN recorrencia_tipo VARCHAR(255),
  ADD COLUMN recorrencia_periodicidade VARCHAR(40),
  ADD COLUMN recorrencia_primeiro_vencimento VARCHAR(30),
  ADD COLUMN recorrencia_fim VARCHAR(30),
  ADD COLUMN recorrencia_valor DECIMAL(14,2) DEFAULT 0,
  ADD COLUMN recorrencia_pagamento VARCHAR(120),
  ADD COLUMN cobranca_recorrente_id INT;

ALTER TABLE cobrancas_recorrentes
  ADD COLUMN contrato_id INT,
  ADD COLUMN origem VARCHAR(40) DEFAULT 'Manual';
