# Taxas automáticas por produto — 07/10/2026

Implementado no projeto local, sem transmissão de notas ou publicação no servidor.

- NF-e manual busca NCM, CFOP, unidade, origem e taxas nas regras conferidas para o produto. O vínculo ao estoque tem prioridade; o nome precisa corresponder exatamente a um produto único.
- A regra corresponde ao mesmo emitente, cliente, CRT, UF de origem/destino, situação de ICMS, ambiente, operação e ano.
- Bases integrais são recalculadas pelo total atual de cada produto. Taxas zero são preservadas. Regras conflitantes, bases reduzidas ou códigos divergentes exigem conferência.
- O botão **Guardar taxas para as próximas notas → Salvar taxas dos produtos** registra a regra conferida. Ela serve ao preparo manual e ao clique de faturar com emissão automática já configurada.
- Ao conferir novamente uma taxa, combinações futuras já salvas para o mesmo produto e operação recebem a correção. Planos de emissão e notas existentes preservam sua própria conferência.
- Alíquotas integrais IBS/CBS de 2026 são preenchidas antes da assinatura, também em preparações antigas ainda não enviadas: estadual 0,1%, municipal 0% e CBS 0,9%. O enquadramento 000/000001 precisa estar selecionado. Outros enquadramentos não recebem essas taxas.
- As alíquotas variáveis ICMS/PIS/COFINS dependem da regra fiscal salva; o nome do produto por si só não informa esses valores.
- NFS-e já utiliza o ISS do serviço cadastrado e a configuração fiscal conferida para a emissão automática.

Fonte para as taxas nominais de 2026: [SEFIN-RO, tabela do Informe Técnico 2025.002](https://reformatributaria.sefin.ro.gov.br/noticias/informe-tecnico-detalha-tabelas-de-classificacao-tributaria-cst-e-credito-presumido-do-ibs-e-da-cbs).

Arquivos desta parte: `pages/faturamento.py`, `pages/nfe_tributacao_item.py`,
`services/nfe_tributacao_item.py`, `services/nfe_produto.py`,
`services/fiscal_modelos.py` e `services/fiscal_automatico.py`.

Testes executam banco e retorno fiscal simulados, assinatura com certificado de teste e geração de PDFs. Nenhuma nota real foi emitida.
