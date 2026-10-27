"""Executor somente leitura do painel Inter; não importa o startup do ERP."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dsystem_erp.services.inter_painel import PainelInter, carregar_usuario
from dsystem_erp.services.inter_runtime import ConsultasInterProducao, repositorio_configuracao
from dsystem_erp.services.permissions import usuario_tem_permissao


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--empresa', type=int, required=True)
    parser.add_argument('--usuario', required=True)
    modo = parser.add_mutually_exclusive_group(required=True)
    for opcao in ('preparar', 'ativar', 'desativar', 'verificar', 'agendado', 'atualizar'):
        modo.add_argument('--'+opcao, action='store_true')
    args = parser.parse_args(argv)
    consultas = None
    try:
        usuario = carregar_usuario(args.usuario)
        if not usuario_tem_permissao('inter.view', usuario):
            raise PermissionError
        repo = repositorio_configuracao()
        if args.preparar:
            if str(usuario.get('is_admin', 0)).lower() not in ('1', 'true') or not usuario_tem_permissao('inter.configurar', usuario):
                raise PermissionError
            with repo.transacao() as c:
                repo.exigir_empresa(c, args.empresa, usuario['username'])
            repo.schema()  # Apenas base isolada *_inter_config, nunca financeiro ERP.
        consultas = ConsultasInterProducao(repo)
        painel = PainelInter(repo, consultas)
        if args.verificar:
            from dsystem_erp.services.inter_runtime import chave_mestra, validar_par_certificado
            from dsystem_erp.services.inter_api import decifrar_credencial
            with repo.transacao() as c:
                repo.exigir_empresa(c, args.empresa, usuario['username'])
                repo.executar(c, 'SELECT credencial_secret FROM inter_contas WHERE empresa_id=%s AND ambiente=%s', (args.empresa, 'producao'))
                row = c.fetchone()
            dados = decifrar_credencial(row['credencial_secret'], args.empresa, chave_mestra(), 'credencial:producao')
            if 'extrato.read' not in dados['escopos']:
                raise PermissionError
            validar_par_certificado(Path(dados['certificado']).read_bytes(), Path(dados['chave']).read_bytes())
            print('Cofre, certificado e acesso local verificados. Nenhuma chamada bancária executada.')
        elif args.preparar or args.ativar or args.desativar:
            painel.configurar_agenda(args.empresa, usuario, ativo=args.ativar)
            print('Agenda configurada. Nenhuma chamada bancária executada.')
        else:
            resultado = painel.atualizar(args.empresa, usuario, agendado=args.agendado)
            print('Painel Inter: ' + resultado + '. Somente consultas; nenhuma movimentação.')
        return 0
    except Exception:
        print('Falha na atualização/configuração do painel Inter. Verifique MySQL, acesso do usuário, cofre e certificados. Dados bancários não foram exibidos.', file=sys.stderr)
        return 1
    finally:
        if consultas is not None:
            consultas.fechar()


if __name__ == '__main__':
    raise SystemExit(main())
