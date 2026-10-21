# QR atualizado e etiquetas de O.S.

## Uso

- **Aparelho / identificação**: nome que distingue o aparelho (ex.: câmera da entrada). Tipo é a categoria; marca/modelo tem campo próprio.
- Ao ler o QR, faça login com usuário que tenha acesso à Recepção. A ficha mostra cliente, aparelho, série, etapa e **o que fazer**, incluindo as tarefas marcadas.
- Em Recepção/Kanban, abra o cartão e use **Editar serviço a fazer**. Na edição da O.S., os serviços e tarefas são separados por aparelho.
- Cada leitura consulta o banco. Na ficha já aberta, use **Atualizar ficha**. O mesmo QR permanece válido depois de editar o equipamento; o papel já impresso não muda.
- A edição mantém IDs, números, fotos e etapas dos aparelhos. Não exclui/reinsere nem renumera equipamentos já etiquetados. Novos aparelhos recebem outra etiqueta.
- Links antigos com O.S./item também são aceitos. QR antigo que contenha só texto (sem URL) não pode ser transformado remotamente: precisa de nova etiqueta uma vez.
- Acesso não é público: exige login e permissão `recepcao.view`; edição exige `recepcao.edit` no Kanban ou a permissão existente de edição de O.S.

## Impressão — Elgin i8

1. O perfil padrão agora é **Elgin i8 — cupom em bobina de 80 mm**, tanto na entrada da O.S. como no Kanban. Medidas antigas de 100 × 50 mm não são aplicadas à i8.
2. O ERP gera **PDF de 80 × 60 mm**, um aparelho por página, com margens laterais de 4 mm (conteúdo dentro de 72 mm). Os 60 mm são comprimento escolhido pelo layout, não altura de etiqueta adesiva.
3. Em **Configurações do Sistema > Empresa**, salve uma URL estável acessível pelo celular. O resumo do serviço sai no cupom; o QR abre o serviço completo e atualizado após login.
4. Instale o driver oficial da i8 no **computador que imprimirá**, não apenas no servidor do site. Abra o PDF e selecione Elgin i8, papel/formulário personalizado **80 × 60 mm**, orientação retrato, **100% / tamanho real**, sem ajustar à folha. Confira a prévia e use o mesmo tamanho no driver. A disponibilidade de formulário personalizado deve ser conferida no driver instalado.
5. O corte por página/documento depende das preferências e do driver da impressora. O PDF não envia comandos de guilhotina, não configura portas USB/rede e não imprime silenciosamente.
6. Teste a leitura no celular antes de imprimir em quantidade. Endereço local só funciona na rede/VPN que alcança o servidor. Se o endereço mudar, mantenha um redirecionamento do antigo.

**Atenção ao papel:** a Elgin i8 é impressora de cupom, não deve ser tratada automaticamente como etiquetadora adesiva. O manual informa papel térmico padrão, largura 79,5 ± 0,5 mm, espessura 0,06 a 0,08 mm. Não use papel adesivo sem confirmação do fabricante. Para identificar o equipamento com cupom comum, ele pode ficar no saquinho/ficha que acompanha o aparelho; não é uma etiqueta autocolante.

Fontes do fabricante:
- [Manual Elgin i8, instalação e especificações](https://d2u2qhufg0q9tn.cloudfront.net/assets/arquivos/imgCard_2a2228fd-72b1-4b99-8b66-8177650aaef5_Manual_do_Usu%C3%A1rio_i8.pdf)
- [Central oficial de downloads Elgin — procure i8](https://www.elgin.com.br/download-center)

O perfil **Etiquetadora / tamanho personalizado** continua disponível para outro equipamento: largura de 70 a 150 mm, altura de 40 a 150 mm.

Sem URL válida, a tela não oferece impressão de um QR estático por engano. `localhost` não é aceito para a etiqueta.

**Pendente:** instalação do driver, conexão da impressora e teste físico de impressão/leitura. O modelo foi informado como Elgin i8, mas não foi instalado driver nem enviada impressão. A preparação do PDF não substitui essa validação.

## Arquivos desta alteração

- `orcamento.py`: navegação após login e medidas salvas nas configurações da empresa.
- `dsystem_erp/services/recepcao_kanban.py`: link por ID, consulta atual, checklist, edição preservando identidade, PDF dimensionado.
- `dsystem_erp/pages/recepcao_kanban.py`: ficha QR e edição de instruções.
- `dsystem_erp/pages/ordens_servico.py`: orientação do campo, etiqueta na entrada e sincronização dos aparelhos na edição.
- `dsystem_erp/pages/etiquetas_os.py`: impressão compartilhada e orientação de escala.
- `tests/test_os_qr_dinamico.py`: testes isolados, sem banco real nem impressora.
- `scripts/validar_etiqueta_os.py`: amostras fictícias em `tmp/pdfs/etiqueta-os`.

## Atualização do servidor pelo usuário

Nenhum envio foi executado. O comando abaixo utiliza o deploy completo já existente e inclui outras alterações locais do projeto:

```powershell
cd C:\Users\Leonel\Desktop\ProgramaPythom
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\deploy.ps1 -HostName 2.25.130.92
```

Não ignore falhas dos testes. Após atualizar, confira a URL e as medidas nas configurações antes de imprimir.
