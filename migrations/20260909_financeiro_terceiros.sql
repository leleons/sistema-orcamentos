ALTER TABLE contas_pagar
  ADD COLUMN conta_receber_origem_id INT;

ALTER TABLE contas_receber
  ADD COLUMN tem_terceiro VARCHAR(10) DEFAULT 'Não',
  ADD COLUMN terceiro_prestador VARCHAR(255),
  ADD COLUMN terceiro_documento VARCHAR(60),
  ADD COLUMN terceiro_valor DECIMAL(14,2) DEFAULT 0,
  ADD COLUMN terceiro_historico LONGTEXT,
  ADD COLUMN terceiro_vencimento VARCHAR(30),
  ADD COLUMN terceiro_conta_pagar_id INT;
