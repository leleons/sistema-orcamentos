ALTER TABLE estoque ADD COLUMN codigo_item INT;

UPDATE estoque
SET codigo_item = CAST(SUBSTRING_INDEX(codigo_entrada, '.', -1) AS UNSIGNED)
WHERE TRIM(COALESCE(codigo_entrada, '')) REGEXP '[.][0-9]+$';

UPDATE estoque
SET codigo_item = CAST(produto AS UNSIGNED)
WHERE COALESCE(codigo_item, 0) = 0
  AND TRIM(COALESCE(produto, '')) REGEXP '^[0-9]+$';
