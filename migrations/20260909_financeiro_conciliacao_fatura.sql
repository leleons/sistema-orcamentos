ALTER TABLE contas_pagar
  ADD COLUMN conciliado VARCHAR(10) DEFAULT 'Não',
  ADD COLUMN data_conciliacao VARCHAR(30),
  ADD COLUMN conciliado_por VARCHAR(120),
  ADD COLUMN fatura_cartao VARCHAR(10) DEFAULT 'Não',
  ADD COLUMN cartao_credito VARCHAR(255),
  ADD COLUMN itens_fatura_cartao LONGTEXT;

ALTER TABLE contas_receber
  ADD COLUMN conciliado VARCHAR(10) DEFAULT 'Não',
  ADD COLUMN data_conciliacao VARCHAR(30),
  ADD COLUMN conciliado_por VARCHAR(120);

CREATE TABLE IF NOT EXISTS financeiro_fatura_cartao_itens (
  id INT AUTO_INCREMENT PRIMARY KEY,
  conta_pagar_id INT NOT NULL,
  descricao TEXT,
  data_compra VARCHAR(30),
  categoria VARCHAR(120),
  valor DECIMAL(14,2) DEFAULT 0,
  criado_por VARCHAR(120),
  criado_em VARCHAR(30),
  INDEX idx_fatura_cartao_conta (conta_pagar_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
