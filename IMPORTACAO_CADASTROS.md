# Importação de cadastros financeiros

Em **Financeiro → Cadastros Financeiros**, abra **Importar planilha de cadastros (.xlsx)**.
Envie o arquivo, confira a prévia e confirme a importação. Exige acesso e edição de cadastros financeiros.

São lidas exclusivamente as abas **Plano de contas**, **Centros de custo** e **Naturezas financeiras**.
Abas de exemplos e instruções não são importadas. O arquivo original não é alterado.

- Plano: código, nome, pai, nível, sintética/analítica, natureza do saldo, classe, grupo DRE, permissão de lançamento, ativo e observação.
- Centro: código, nome, pai, nível, sintética/analítica, permissão de lançamento, ativo, responsável, critério de rateio e observação.
- Natureza: código, nome, pai, nível, sintética/analítica, fluxo, conta e centro sugeridos, impacto/grupo DRE, permissão de lançamento, ativo e regra de uso.

Os códigos devem ser células de texto, preservando zeros e pontos. Fórmulas não são aceitas.
Validação rejeita códigos duplicados, pais ausentes/não sintéticos, níveis incompatíveis e sugestões que não apontam a contas/centros analíticos aptos a lançamento.
É possível importar uma aba isolada se os pais e vínculos já existirem no banco.

## Preservação dos cadastros existentes

A chave de importação é **tipo de cadastro + código**, não o nome. Registros iguais não são duplicados.
Alterações exigem confirmação adicional, com comparativo antes/depois, e preservam o ID.
Dados ausentes do arquivo não são excluídos. Nomes iguais com códigos diferentes continuam registros distintos.
Cadastros antigos sem código não são automaticamente fundidos aos importados.
Para editar/desativar cadastros estruturados, altere a linha no XLSX e reimporte; o editor simples fica bloqueado para não quebrar vínculos.

A importação inteira usa uma transação. Falhas desfazem todas as gravações dessa tentativa.
Se o banco mudar após a prévia, uma nova conferência é exigida. MySQL utiliza trava de importação e bloqueio de linhas.
O adaptador de auditoria existente continua registrando escritas, com autor/data nos próprios cadastros.

## Uso no financeiro

Contas a pagar/receber, recorrências e faturamento usam os seletores compartilhados.
As naturezas aparecem em **Categoria / natureza financeira**, preservando categorias antigas.
Cadastros importados aparecem como **código — nome**. Somente ativos, analíticos e habilitados aparecem para novas seleções; valores históricos continuam disponíveis ao editar.
Vínculos sugeridos e regras ficam consultáveis nas abas próprias. Não são lançamentos automáticos nem regras tributárias e não substituem o campo de conta bancária.

Não cria bancos, saldos, pagamentos ou lançamentos contábeis. Não recalcula DRE, não faz rateios e não altera títulos/contratos/notas existentes.
Reutiliza a tabela `financeiro_cadastros_aux`; novas colunas são adicionadas na inicialização normal do ERP, sem apagar dados. Mantém o escopo compartilhado atual desse cadastro; não cria uma nova separação por empresa.

Implementação e testes locais, sem carga no banco real ou publicação no servidor.
