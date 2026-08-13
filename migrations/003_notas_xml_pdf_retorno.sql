CREATE TABLE IF NOT EXISTS notas_fiscais (
    id INT PRIMARY KEY AUTO_INCREMENT,
    faturamento_id INTEGER,
    cliente TEXT,
    cpf_cnpj TEXT,
    tipo_nota TEXT,
    data_competencia TEXT,
    descricao LONGTEXT,
    valor_servicos DECIMAL(14,2) DEFAULT 0,
    aliquota_iss DECIMAL(8,4) DEFAULT 0,
    valor_iss DECIMAL(14,2) DEFAULT 0,
    codigo_servico TEXT,
    municipio_prestacao TEXT,
    status VARCHAR(60) DEFAULT 'Pendente',
    numero_nota TEXT,
    chave_acesso TEXT,
    link_nota LONGTEXT,
    observacoes LONGTEXT,
    criado_por TEXT,
    criado_em TEXT,
    emitido_em TEXT,
    xml_envio LONGTEXT,
    xml_retorno LONGTEXT,
    xml_autorizado LONGTEXT,
    pdf_base64 LONGTEXT,
    protocolo TEXT,
    mensagem_retorno LONGTEXT,
    numero_lote TEXT,
    atualizado_em TEXT
);

ALTER TABLE notas_fiscais ADD COLUMN xml_envio LONGTEXT;
ALTER TABLE notas_fiscais ADD COLUMN xml_retorno LONGTEXT;
ALTER TABLE notas_fiscais ADD COLUMN xml_autorizado LONGTEXT;
ALTER TABLE notas_fiscais ADD COLUMN pdf_base64 LONGTEXT;
ALTER TABLE notas_fiscais ADD COLUMN protocolo TEXT;
ALTER TABLE notas_fiscais ADD COLUMN mensagem_retorno LONGTEXT;
ALTER TABLE notas_fiscais ADD COLUMN numero_lote TEXT;
ALTER TABLE notas_fiscais ADD COLUMN atualizado_em TEXT;
