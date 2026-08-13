CREATE TABLE IF NOT EXISTS configuracoes_sistema (
    chave VARCHAR(160) PRIMARY KEY,
    valor LONGTEXT,
    descricao TEXT,
    atualizado_por VARCHAR(120),
    atualizado_em DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tentativas_login (
    id INT PRIMARY KEY AUTO_INCREMENT,
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    usuario VARCHAR(160),
    tipo VARCHAR(40),
    sucesso INTEGER DEFAULT 0,
    ip TEXT,
    mensagem TEXT
);

CREATE TABLE IF NOT EXISTS nfse_envios (
    id INT PRIMARY KEY AUTO_INCREMENT,
    nota_id INTEGER,
    faturamento_id INTEGER,
    ambiente VARCHAR(40),
    status VARCHAR(80),
    protocolo TEXT,
    mensagem LONGTEXT,
    xml_envio LONGTEXT,
    xml_retorno LONGTEXT,
    criado_por VARCHAR(120),
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP
);
