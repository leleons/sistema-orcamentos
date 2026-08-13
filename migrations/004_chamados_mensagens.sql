CREATE TABLE IF NOT EXISTS chamados_mensagens (
    id INT PRIMARY KEY AUTO_INCREMENT,
    chamado_id INTEGER,
    autor_tipo VARCHAR(40),
    autor_nome TEXT,
    mensagem LONGTEXT,
    anexo_nome TEXT,
    anexo_mime TEXT,
    anexo LONGBLOB,
    criado_em TEXT
);
