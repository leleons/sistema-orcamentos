# Portal individual dos funcionários dos clientes

## Cadastro e uso

Em Clientes/Fornecedores, cadastre ou edite a empresa, marque que é uma empresa
e informe nome, setor, telefone e e-mail de cada funcionário. Ao salvar, o fluxo
existente cria um login por e-mail vinculado ao ID daquela empresa. Cada conta
tem sua própria senha armazenada com hash e troca obrigatória no primeiro acesso,
com a configuração de autenticação já existente no portal. Contas existentes
não têm suas senhas alteradas por esta atualização.

O funcionário abre chamados com a empresa e o usuário obtidos da sessão de login.
Seu nome é preenchido automaticamente. Ele vê somente chamados criados por seu
login e vinculados à sua empresa: lista, contador, conversa e anexos. A mesma
regra é revalidada antes de editar, cancelar, aprovar, recusar e enviar mensagens.
Contas desativadas não conseguem listar, ler, responder ou abrir novos chamados.

O portal individual oferece abertura, acompanhamento e contato. Rotas de notas,
financeiro, documentos e ordens gerais da empresa não ficam disponíveis ao
funcionário, nem ao tentar navegar diretamente para essas seções.

Na gestão interna da D-System, a visão dos chamados permanece conforme as
permissões da equipe. A grade mostra empresa, solicitante e login de origem;
a pesquisa aceita esses campos. As respostas continuam no chamado correto.

## Histórico e limites

O isolamento usa os campos existentes cliente_id e criado_por; não altera nem
apaga registros. Chamados sem empresa identificada ficam disponíveis somente
para a equipe interna. Chamados sem autoria, mas com empresa identificada,
ficam acessíveis também ao login principal. Não são atribuídos por semelhança de
nome. Chamados antigos de um login compartilhado não são repartidos entre
funcionários automaticamente. Trocar o e-mail cria uma identidade diferente:
o histórico do e-mail anterior não é transferido automaticamente.

O login principal da empresa (dono/responsável) tem acesso ao financeiro,
notas, documentos e ordens da empresa, além de todos os chamados vinculados
ao ID da empresa, independentemente do funcionário que abriu. Não dá acesso
a chamados de outra empresa. Os funcionários permanecem restritos aos próprios
chamados, sem as áreas financeiras. A gestão interna da D-System é preservada.

Testes locais usam SQLite em memória e verificações de integração, sem acessar
o banco real ou enviar mensagens. Esta atualização não foi publicada no servidor.
