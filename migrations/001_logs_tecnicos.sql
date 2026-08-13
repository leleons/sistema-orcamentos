CREATE TABLE IF NOT EXISTS logs_tecnicos (
    id INT PRIMARY KEY AUTO_INCREMENT,
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    nivel VARCHAR(30),
    origem VARCHAR(160),
    mensagem TEXT,
    detalhes LONGTEXT
);
