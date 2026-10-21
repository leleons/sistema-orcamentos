"""Guarda dados fornecidos pelo operador no cofre Windows, sem tocar no MySQL.

Segredos por entrada padrão JSON (automação local) ou getpass, nunca argumentos.
"""
import argparse
import getpass
import json
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--zip', type=Path)
    parser.add_argument('--credenciais-stdin', action='store_true')
    parser.add_argument('--testar-consulta-producao', action='store_true')
    args = parser.parse_args()
    from dsystem_erp.services.inter_pendente import preparar_pendente, testar_consulta_pendente
    from dsystem_erp.services.inter_api import InterErro
    try:
        if args.testar_consulta_producao:
            print(json.dumps(testar_consulta_pendente()))
        else:
            if args.zip is None:
                parser.error('Informe --zip com o arquivo de chave e certificado.')
            if args.credenciais_stdin:
                dados = json.loads(sys.stdin.read(8192))
                client_id, client_secret = dados['client_id'], dados['client_secret']
            else:
                client_id = getpass.getpass('Client ID: ')
                client_secret = getpass.getpass('Client Secret: ')
            print(json.dumps(preparar_pendente(client_id, client_secret, args.zip.read_bytes())))
    except InterErro as erro:
        print(str(erro), file=sys.stderr)
        return 1
    except Exception:
        print('Configuração não concluída. Confira os arquivos, validade e acesso ao cofre local. Nenhum pagamento foi enviado.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
