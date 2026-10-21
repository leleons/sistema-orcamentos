"""Provisionamento explícito da integração; nunca roda ao iniciar o ERP.

Execute como módulo: python -m scripts.inter_preparar_teste --help
Não concede permissões do ERP. Isso continua no cadastro de usuários existente.
"""
import argparse
import os
import re


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    bases = parser.add_mutually_exclusive_group(required=True)
    bases.add_argument('--confirmar-base-teste', help='Nome exato da base separada *_inter_teste')
    bases.add_argument('--confirmar-base-config', help='Base separada *_inter_config para configuração/consultas reais, sem financeiro')
    parser.add_argument('--empresa-id', required=True, type=int)
    parser.add_argument('--nome', required=True)
    parser.add_argument('--cnpj', required=True)
    parser.add_argument('--usuario', required=True, action='append', help='Login do ERP autorizado nesta empresa; pode repetir')
    args = parser.parse_args()
    if args.confirmar_base_config:
        if (not args.confirmar_base_config.endswith('_inter_config')
                or args.confirmar_base_config != os.environ.get('DSYSTEM_INTER_CONFIG_DATABASE')):
            parser.error('Confirme exatamente DSYSTEM_INTER_CONFIG_DATABASE com sufixo _inter_config.')
        from dsystem_erp.services.inter_runtime import repositorio_configuracao
        repo = repositorio_configuracao()
    else:
        if (not args.confirmar_base_teste.endswith('_inter_teste')
                or args.confirmar_base_teste != os.environ.get('DSYSTEM_INTER_TEST_DATABASE')):
            parser.error('Confirme exatamente DSYSTEM_INTER_TEST_DATABASE com sufixo _inter_teste.')
        from dsystem_erp.services.inter_runtime import repositorio_teste
        repo = repositorio_teste()
    if args.empresa_id < 1 or not re.fullmatch(r'\d{14}',args.cnpj):
        parser.error('Empresa ID positivo e CNPJ com 14 números obrigatórios.')
    repo.schema()
    with repo.transacao() as c:
        repo.executar(c,'SELECT id,nome,cnpj FROM inter_empresas WHERE id=%s',(args.empresa_id,))
        existente = c.fetchone()
        if existente and (existente['nome'] != args.nome or existente['cnpj'] != args.cnpj):
            raise ValueError('Empresa já cadastrada com dados diferentes; não será substituída.')
        if not existente:
            repo.executar(c,'INSERT INTO inter_empresas (id,nome,cnpj) VALUES (%s,%s,%s)',(args.empresa_id,args.nome,args.cnpj))
        for usuario in args.usuario:
            if not usuario.strip():
                raise ValueError('Usuário vazio.')
            repo.executar(c,'SELECT empresa_id FROM inter_acessos WHERE empresa_id=%s AND usuario=%s',(args.empresa_id,usuario))
            if not c.fetchone():
                repo.executar(c,'INSERT INTO inter_acessos (empresa_id,usuario) VALUES (%s,%s)',(args.empresa_id,usuario))
    print('Estrutura Inter preparada na base isolada. Nenhuma chamada bancária ou alteração de permissões do ERP foi realizada.')


if __name__ == '__main__':
    main()
