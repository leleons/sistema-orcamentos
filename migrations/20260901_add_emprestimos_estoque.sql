CREATE TABLE IF NOT EXISTS estoque_emprestimos (
    id INT PRIMARY KEY AUTO_INCREMENT,
    responsavel VARCHAR(255) NOT NULL,
    cliente_id INTEGER,
    cliente_nome VARCHAR(255),
    data_retirada DATE NOT NULL,
    data_limite DATE NOT NULL,
    status VARCHAR(40) DEFAULT 'Em aberto',
    observacoes LONGTEXT,
    criado_por VARCHAR(255),
    criado_em VARCHAR(30),
    encerrado_por VARCHAR(255),
    encerrado_em VARCHAR(30),
    INDEX idx_emprestimos_status_limite (status, data_limite)
);

CREATE TABLE IF NOT EXISTS estoque_emprestimo_itens (
    id INT PRIMARY KEY AUTO_INCREMENT,
    emprestimo_id INT NOT NULL,
    produto_id INT NOT NULL,
    codigo VARCHAR(255),
    produto VARCHAR(255),
    quantidade INT NOT NULL,
    status VARCHAR(40) DEFAULT 'Emprestado',
    resolvido_por VARCHAR(255),
    resolvido_em VARCHAR(30),
    observacao_resolucao LONGTEXT,
    INDEX idx_emprestimo_itens_emprestimo (emprestimo_id),
    INDEX idx_emprestimo_itens_status (status)
);
