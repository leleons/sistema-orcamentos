# Impostos — versão 1.4

Implementação local baseada em `IMPLEMENTAÇÕES - VERSIONADO - VERSÃO 1.4-Final.docx`.
Não executa pagamentos, recolhimentos, emissão em teste real ou publicação no servidor.

## Uso

- **Cadastros → Cadastrar impostos**: nome exato usado no faturamento, tipo, CNAE, anexo e parâmetros fiscais. Requer `impostos.edit`; consulta requer `impostos.view`. Não há enquadramento presumido pelo nome. CNPJ é o emitente configurado no ERP, não o destinatário.
- **Cadastros → Impostos do Simples**: selecione competência e confirme RBT12/FS12 com a contabilidade. Apenas o acesso foi movido para Cadastros; o cálculo mensal, o pró-labore e o cadastro fiscal mantêm o funcionamento anterior.
- **Pró-labore**: por beneficiário, valor fixo mensal ou percentual do faturamento com nota. Os dois valores ficam separados ao trocar de modo. Nenhum percentual é predefinido. Preferências por empresa/mês.
- Notas novas exigem cadastro antes da transmissão manual/automática. Parâmetros são aplicados **antes da assinatura**. Alterar o cadastro invalida a conferência anterior; o XML assinado nunca é editado.
- ISS: a taxa e o parâmetro para informar `pAliq` são distintos. O cadastro não força `pAliq` em regimes em que a API não admite esse campo; confirme a exigência do município/regime no cadastro.
- Emissão captura os parâmetros utilizados por nota. Classificação histórica não muda com a edição do cadastro atual. Para NF-e antigas sem histórico, é possível autorizar expressamente o uso do cadastro atual **somente na estimativa**.
- Notas antigas sem histórico (incluindo NFS-e) podem ser classificadas no painel, mediante confirmação e permissão de edição. A soma precisa fechar com o total autorizado; XML/status permanecem intactos, com autoria da classificação. Histórico existente não é sobrescrito.
- No cadastro, a data `01/02/4751` do Word não foi usada como CNAE. O código de comércio de informática precisa ser confirmado; referência CONCLA: `4751-2/01`.

## Critérios e limites (visíveis na tela)

Somente NF-e processada com protocolo autorizado e NFS-e Nacional autorizada, ambiente produção, emitente correspondente e competência selecionada. Duplicatas por chave são eliminadas e cancelamentos conhecidos prevalecem. Sem XML/segregação verificável, a nota fica pendente. Sem classificação completa, o total é explicitamente **parcial**.

O regime do emitente é conferido no XML: CRT 1 para produto e ME/EPP optante (`opSimpNac=3`) para serviço. MEI e regime normal não são calculados como DAS do Simples desta tela.

Estimativa gerencial, **não apuração oficial nem geração de DAS**. O pedido usa somente receita com nota; a obrigação legal pode incluir outras receitas. RBT12 global deve ser informada/confirmada, inclusive proporcionalização em início de atividade. FS12 não é substituída pelo pró-labore atual.

Tabelas 2026: anexos I/III/V, Fator R de 28%, até RBT12 de R$ 3,6 milhões. Acima disso, anexo IV/outros, retenções, ST, monofásicos, exportações e outros ajustes ficam pendentes de apuração específica. Regime de caixa e outras particularidades não são calculados automaticamente.

INSS pró-labore: 11%, teto 2026 de R$ 8.475,55, descontando base declarada de outros vínculos. IRPF por pessoa: dedução legal ou simplificada mais favorável, tabela mensal e redução de 2026. CPP fora do DAS, complementação ao mínimo e ajustes por outras fontes não estão incluídos. IRPF/INSS retidos já compõem o bruto e não são somados de novo ao desembolso.

**Limites atuais do emissor**: produtos CRT 1 / CSOSN 102 ou CRT 3 / ICMS 00; PIS/COFINS CST 01 e bases integrais. CSOSN 500 é cadastrável, mas bloqueia emissão porque o gerador existente não implementa ICMS-ST. Retenção de INSS em serviços é cadastrável, mas bloqueia o envio até tratamento específico do XML. Não é confundida com INSS do pró-labore. Fluxo municipal legado não está integrado ao novo cadastro; NFS-e Nacional está. Não anunciar cobertura integral de todas as situações fiscais.

Operações marcadas como especiais e ISS retido pelo intermediário também bloqueiam o emissor comum. Consultar o pacote oficial de XSD de NFS-e retornou HTTP 403 nesta sessão; não foi presumida compatibilidade de um novo grupo de retenções sem validar o leiaute.

## Persistência e segurança

Reutiliza `configuracoes_sistema`, com prefixos `IMPOSTO_ITEM_<CNPJ>_...`, `IMPOSTO_NOTA_<CNPJ>_<id>` e `IMPOSTOS_MES_<CNPJ>_<AAAAMM>`. Não modifica schema nem reprocessa notas antigas. Cadastro contém versão, autor e data. Fluxos existentes de confirmação, trava e proteção contra duplicidade permanecem. A separação por CNPJ acompanha o emitente configurado do ERP; não representa uma nova ACL multiempresa.

## Fontes oficiais consultadas em 17/10/2026

- [LC 123/2006 — tabelas e regras do Simples](https://www.planalto.gov.br/ccivil_03/leis/lcp/lcp123.htm).
- [Manual PGDAS-D](https://www8.receita.fazenda.gov.br/SimplesNacional/Arquivos/manual/MANUAL_PGDAS-D_2018_V4.pdf).
- [Receita Federal — IRPF 2026](https://www.gov.br/receitafederal/pt-br/assuntos/meu-imposto-de-renda/tabelas/2026).
- [INSS — tabela de contribuição mensal](https://www.gov.br/inss/pt-br/direitos-e-deveres/inscricao-e-contribuicao/tabela-de-contribuicao-mensal).
- [Caixa — pró-labore](https://www.caixa.gov.br/educacao-financeira/empresa/pro-labore/Paginas/default.aspx).
- [CONCLA/IBGE — CNAE](https://concla.ibge.gov.br/busca-online-cnae.html).

## Testes isolados

`python -m unittest tests.test_impostos_v14 tests.test_fiscal_automatico tests.test_faturamento_manual tests.test_fiscal_modelos -q`

Não importe `orcamento.py` para testar: o entrypoint inicializa o banco real. Os testes usam SQLite em memória, mocks e Streamlit AppTest.
