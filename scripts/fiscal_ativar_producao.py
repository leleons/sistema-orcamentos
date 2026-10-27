"""Configura NF-e/NFS-e em produção, sem importar o ERP nem transmitir notas."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dsystem_erp.config import config_val
from dsystem_erp.db import mysql_connection_config
from dsystem_erp.services.nfse_nacional import ENDPOINT_PRODUCAO, ENDPOINT_HOMOLOGACAO


def configurar(conn, usuario, *, aplicar=False, config=config_val):
    """Alteração atômica só de preferências; não toca notas, modelos ou sequências."""
    cur = conn.cursor(dictionary=True)
    try:
        conn.start_transaction()
        cur.execute('SELECT is_admin FROM usuarios WHERE username=%s', (usuario,))
        row = cur.fetchone()
        if not row or str(row['is_admin']).lower() not in ('1', 'true'):
            raise PermissionError('Informe um administrador cadastrado no ERP.')
        chaves = ('NFSE_MODO_EMISSAO', 'NFSE_NACIONAL_ENDPOINT')
        cur.execute('SELECT chave,valor FROM configuracoes_sistema WHERE chave IN (%s,%s) FOR UPDATE', chaves)
        existentes = {r['chave']: r['valor'] for r in cur.fetchall()}
        def valor(chave, padrao):
            return existentes.get(chave) or config(chave, padrao) or padrao
        if valor('NFSE_MODO_EMISSAO', 'nacional') != 'nacional':
            raise ValueError('NFS-e municipal: confirme o endpoint de produção da prefeitura antes de alterar. Nada foi salvo.')
        endpoint = str(valor('NFSE_NACIONAL_ENDPOINT', '')).strip().rstrip('/')
        if endpoint not in ('', ENDPOINT_PRODUCAO, ENDPOINT_HOMOLOGACAO):
            raise ValueError('Endpoint NFS-e personalizado: revise antes de alterar. Nada foi salvo.')
        alteracoes = {'NFE_AMBIENTE': 'producao', 'NFSE_AMBIENTE': 'producao',
                      'NFSE_NACIONAL_ENDPOINT': ENDPOINT_PRODUCAO}
        if aplicar:
            for chave, valor_novo in alteracoes.items():
                cur.execute('''INSERT INTO configuracoes_sistema
                    (chave,valor,descricao,atualizado_por,atualizado_em) VALUES (%s,%s,%s,%s,NOW())
                    ON DUPLICATE KEY UPDATE valor=VALUES(valor),descricao=VALUES(descricao),
                    atualizado_por=VALUES(atualizado_por),atualizado_em=NOW()''',
                    (chave, valor_novo, 'Produção ativada explicitamente; sem emissão automática por este comando.', usuario))
            conn.commit()
        else:
            conn.rollback()
        return alteracoes
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--usuario', required=True)
    parser.add_argument('--confirmar', choices=['PRODUCAO'], help='Sem esta opção, apenas valida e mostra o plano.')
    args = parser.parse_args(argv)
    conn = None
    try:
        import mysql.connector
        conn = mysql.connector.connect(**mysql_connection_config(config_val('MYSQL_DATABASE', 'banco_dsystem')))
        alteracoes = configurar(conn, args.usuario, aplicar=args.confirmar == 'PRODUCAO')
        print('Aplicado:' if args.confirmar else 'Prévia (nada alterado):')
        for chave, valor in alteracoes.items():
            print(f'{chave}={valor}')
        print('Nenhuma nota emitida. Histórico, preparações existentes e numeração preservados. Reabra a tela de emissão.')
        return 0
    except (ValueError, PermissionError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception:
        print('Falha de configuração. Verifique MySQL e o cadastro do administrador. Nenhuma emissão realizada.', file=sys.stderr)
        return 1
    finally:
        if conn is not None:
            conn.close()


if __name__ == '__main__':
    raise SystemExit(main())
