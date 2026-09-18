ALTER TABLE estoque
  ADD COLUMN data_compra DATE,
  ADD COLUMN ultima_nota_entrada_id INT;

CREATE TABLE IF NOT EXISTS estoque_notas_entrada (
  id INT AUTO_INCREMENT PRIMARY KEY,
  fornecedor VARCHAR(255) NOT NULL,
  fornecedor_documento VARCHAR(60),
  numero_nota VARCHAR(120) NOT NULL,
  serie VARCHAR(40),
  chave_acesso VARCHAR(60) UNIQUE,
  data_compra DATE NOT NULL,
  origem VARCHAR(30) DEFAULT 'Manual',
  observacoes LONGTEXT,
  criado_por VARCHAR(120),
  criado_em VARCHAR(30),
  INDEX idx_estoque_nota_fornecedor (fornecedor),
  INDEX idx_estoque_nota_data (data_compra)
);

CREATE TABLE IF NOT EXISTS estoque_nota_entrada_itens (
  id INT AUTO_INCREMENT PRIMARY KEY,
  nota_entrada_id INT NOT NULL,
  produto_id INT NOT NULL,
  numero_item VARCHAR(30),
  codigo_fornecedor VARCHAR(120),
  codigo_barras VARCHAR(120),
  descricao TEXT,
  ncm VARCHAR(30),
  cfop VARCHAR(20),
  unidade VARCHAR(20),
  quantidade DECIMAL(14,3) DEFAULT 0,
  valor_unitario DECIMAL(14,4) DEFAULT 0,
  valor_total DECIMAL(14,2) DEFAULT 0,
  INDEX idx_estoque_nota_item_nota (nota_entrada_id),
  INDEX idx_estoque_nota_item_produto (produto_id)
);

CREATE TABLE IF NOT EXISTS estoque_movimentacoes (
  id INT AUTO_INCREMENT PRIMARY KEY,
  produto_id INT NOT NULL,
  tipo VARCHAR(60) NOT NULL,
  quantidade DECIMAL(14,3) NOT NULL,
  estoque_anterior DECIMAL(14,3) DEFAULT 0,
  estoque_atual DECIMAL(14,3) DEFAULT 0,
  cliente_id INT,
  cliente_nome VARCHAR(255),
  fornecedor VARCHAR(255),
  nota_entrada_id INT,
  origem VARCHAR(60),
  origem_id INT,
  observacoes LONGTEXT,
  criado_por VARCHAR(120),
  criado_em VARCHAR(30),
  INDEX idx_estoque_mov_produto (produto_id),
  INDEX idx_estoque_mov_cliente (cliente_id),
  INDEX idx_estoque_mov_nota (nota_entrada_id)
);
