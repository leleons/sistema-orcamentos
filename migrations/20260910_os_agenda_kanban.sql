ALTER TABLE ordens_servico ADD COLUMN cliente_id INT;

CREATE TABLE IF NOT EXISTS os_tipos_aparelhos (
  id INT AUTO_INCREMENT PRIMARY KEY, nome VARCHAR(120) NOT NULL UNIQUE,
  ativo VARCHAR(10) DEFAULT 'Sim', criado_por VARCHAR(120), criado_em VARCHAR(30)
);
INSERT IGNORE INTO os_tipos_aparelhos (nome, ativo) VALUES
  ('Desktop','Sim'),('Notebook','Sim'),('Servidor','Sim'),('Impressora','Sim'),
  ('DVR','Sim'),('Câmera','Sim'),('Outro','Sim');

ALTER TABLE equipamentos_os ADD COLUMN kanban_arquivado TINYINT DEFAULT 0;
ALTER TABLE atendimentos_checklist ADD COLUMN kanban_arquivado TINYINT DEFAULT 0;
ALTER TABLE chamados_cliente ADD COLUMN kanban_arquivado TINYINT DEFAULT 0;

ALTER TABLE agenda_visitas ADD COLUMN recorrencia_id INT;
ALTER TABLE agenda_visitas ADD COLUMN recorrencia_indice INT;

CREATE TABLE IF NOT EXISTS agenda_tipos_atendimento (
  id INT AUTO_INCREMENT PRIMARY KEY, nome VARCHAR(120) NOT NULL UNIQUE,
  ativo VARCHAR(10) DEFAULT 'Sim', criado_por VARCHAR(120), criado_em VARCHAR(30)
);
INSERT IGNORE INTO agenda_tipos_atendimento (nome, ativo) VALUES
  ('Suporte Presencial','Sim'),('Instalação','Sim'),('Manutenção Preventiva','Sim'),
  ('Reunião','Sim'),('Entrega de Equipamento','Sim'),('Outro','Sim');

CREATE TABLE IF NOT EXISTS agenda_recorrencias (
  id INT AUTO_INCREMENT PRIMARY KEY, tecnico VARCHAR(255), cliente_id INT,
  cliente_nome VARCHAR(255), data_inicio VARCHAR(30), hora_inicio VARCHAR(20),
  hora_fim VARCHAR(20), tipo_atendimento VARCHAR(120), descricao LONGTEXT,
  periodicidade VARCHAR(40), dia_semana INT, dia_mes INT, mes_anual INT,
  dia_anual INT, modo_termino VARCHAR(40), quantidade INT, data_fim VARCHAR(30),
  ativa VARCHAR(10) DEFAULT 'Sim', criado_por VARCHAR(120), criado_em VARCHAR(30)
);

CREATE TABLE IF NOT EXISTS agenda_atividades (
  id INT AUTO_INCREMENT PRIMARY KEY, atividade LONGTEXT NOT NULL, cliente_id INT,
  cliente_nome VARCHAR(255), data_execucao VARCHAR(30), hora_execucao VARCHAR(20),
  executor VARCHAR(255), status VARCHAR(40) DEFAULT 'Pendente', criado_por VARCHAR(120),
  criado_em VARCHAR(30), alterado_por VARCHAR(120), alterado_em VARCHAR(30)
);

UPDATE ordens_servico os
JOIN (SELECT MIN(id) AS id, nome FROM clientes GROUP BY nome) c ON c.nome = os.cliente
SET os.cliente_id = c.id
WHERE os.cliente_id IS NULL;
