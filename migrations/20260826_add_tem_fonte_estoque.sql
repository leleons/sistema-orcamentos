ALTER TABLE estoque ADD COLUMN tem_fonte VARCHAR(5) DEFAULT 'Não';

UPDATE estoque
SET tem_fonte = 'Não'
WHERE tem_fonte IS NULL OR TRIM(tem_fonte) = '';
