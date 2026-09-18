CREATE TABLE IF NOT EXISTS base_pesquisa (
  id INT AUTO_INCREMENT PRIMARY KEY,
  titulo VARCHAR(255) NOT NULL,
  categoria VARCHAR(120),
  palavras_chave TEXT,
  problema LONGTEXT,
  solucao LONGTEXT,
  criado_por VARCHAR(120),
  criado_em VARCHAR(30),
  alterado_por VARCHAR(120),
  alterado_em VARCHAR(30),
  INDEX idx_base_pesquisa_titulo (titulo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
