UPDATE estoque
SET codigo_entrada = CONCAT(
    CASE codigo
        WHEN '1-01 Novo' THEN '01'
        WHEN '1-02 Usado' THEN '02'
        ELSE LPAD(TRIM(codigo), 2, '0')
    END,
    '.',
    CASE categoria
        WHEN '2-01 Informática' THEN '01'
        WHEN '2-02 CFTV' THEN '02'
        WHEN '2-03 Alarme' THEN '03'
        WHEN '2-04 Infraestrutura' THEN '04'
        ELSE LPAD(TRIM(categoria), 2, '0')
    END,
    '.',
    CASE
        WHEN COALESCE(codigo_item, 0) > 0 THEN CAST(codigo_item AS CHAR)
        ELSE TRIM(produto)
    END
)
WHERE (COALESCE(codigo_item, 0) > 0 OR TRIM(COALESCE(produto, '')) <> '')
  AND (
      codigo IN ('1-01 Novo', '1-02 Usado')
      OR TRIM(codigo) IN ('1', '01', '2', '02')
  )
  AND (
      categoria IN (
          '2-01 Informática', '2-02 CFTV', '2-03 Alarme', '2-04 Infraestrutura'
      )
      OR TRIM(categoria) IN ('1', '01', '2', '02', '3', '03', '4', '04')
  );
