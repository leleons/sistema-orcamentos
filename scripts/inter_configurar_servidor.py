"""Provisionamento Linux do Inter; sem rede bancária e sem alterar o financeiro ERP.

Cria somente configuração ausente, tabelas inter_* e vínculo do administrador.
Credenciais bancárias são cadastradas depois pelo formulário seguro do ERP.
"""
import argparse
import base64
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dsystem_erp.config import config_val
from dsystem_erp.db import mysql_connection_config
from dsystem_erp.repositories.inter import RepositorioInter
from dsystem_erp.services.permissions import usuario_tem_permissao

ENV = Path('/etc/dsystem/inter.env')
MARCA = '# DSystem: configuracao Inter gerenciada, nao remover a chave mestra\n'

ETAPAS = {
    'validacao': 'validar serviço, empresa e configuração existente',
    'cofre': 'preservar/criar o arquivo protegido do cofre',
    'certificados': 'preparar diretório de certificados',
    'base': 'criar a base isolada no MySQL',
    'tabelas': 'preparar as tabelas Inter',
    'vinculo': 'registrar empresa e acesso do administrador',
    'systemd': 'preparar configuração do serviço',
    'reload': 'recarregar configuração do systemd',
    'restart': 'reiniciar o ERP',
    'status': 'verificar se o ERP iniciou',
}


def diagnostico_seguro(erro, etapa):
    """Nunca expõe str/repr da exceção, SQL, comando, caminhos ou segredos."""
    descricao = ETAPAS.get(etapa, 'etapa não identificada')
    codigo = getattr(erro, 'errno', None)
    detalhe = ''
    if type(codigo) is int and 0 <= codigo <= 65535:
        detalhe = f' Código: {codigo}.'
        if codigo in (1044, 1045, 1142, 1227):
            detalhe += ' Confira as permissões do usuário MySQL para a base Inter; não altere as chaves.'
        elif codigo == 1071:
            detalhe += ' O MySQL recusou o tamanho de um índice; é necessário revisar a compatibilidade das tabelas.'
        elif codigo == 1064:
            detalhe += ' O MySQL recusou a sintaxe de uma instrução; é necessário revisar a compatibilidade do schema.'
        elif codigo in (2002, 2003, 2006, 2013):
            detalhe += ' Confira a disponibilidade do MySQL.'
        elif isinstance(erro, OSError) and codigo in (1, 13, 28, 30):
            detalhe += ' Confira permissões, espaço livre e acesso de escrita no servidor.'
    elif isinstance(erro, subprocess.CalledProcessError) and type(erro.returncode) is int:
        detalhe = f' Saída do serviço: {erro.returncode}.'
    return (f'Configuração interrompida ao {descricao}.{detalhe} '
            'Segredos preservados; não apague o cofre nem as bases. Envie esta mensagem para diagnóstico.')


def escolher_base(configurada, existentes, banco_erp):
    if configurada:
        base = configurada
    elif len(existentes) == 1:
        base = existentes[0]
    elif existentes:
        raise ValueError('Há várias bases Inter. Configure explicitamente DSYSTEM_INTER_CONFIG_DATABASE antes de continuar.')
    else:
        base = 'dsystem_inter_config'
    if not re.fullmatch(r'[A-Za-z0-9_]+_inter_config', base) or base == banco_erp:
        raise ValueError('A base Inter deve ser separada do ERP e terminar em _inter_config.')
    return base


def escolher_chave(atual, possui_cifrados):
    if atual:
        try:
            if len(base64.b64decode(atual, validate=True)) == 32:
                return atual
        except (ValueError, TypeError):
            pass
        raise ValueError('A chave mestra existente é inválida. Ela não será substituída.')
    if possui_cifrados:
        raise ValueError('Já existem dados Inter cifrados. Recupere a chave mestra original; nenhuma chave nova foi gerada.')
    return base64.b64encode(os.urandom(32)).decode('ascii')


def conferir_empresa(existente, nome, cnpj):
    cnpj = re.sub(r'\D', '', str(cnpj or ''))
    if not nome or len(cnpj) != 14 or len(set(cnpj)) == 1:
        raise ValueError('Salve nome e CNPJ reais em Configurações do Sistema → Empresa antes de configurar o Inter.')
    if existente and (existente['nome'] != nome or existente['cnpj'] != cnpj):
        raise ValueError('O ID bancário já pertence a outra identificação empresarial. Nada será substituído.')
    return cnpj


def arquivo_protegido(caminho):
    if caminho.is_symlink() or (caminho.exists() and (not caminho.is_file() or caminho.stat().st_mode & 0o077 or caminho.stat().st_uid != 0)):
        raise ValueError('Arquivo de configuração inseguro. Confira proprietário/permissões antes de continuar.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--usuario', default='Daniel.fabio')
    parser.add_argument('--empresa', type=int, default=1)
    parser.add_argument('--servico', default='orcamento.service')
    modo = parser.add_mutually_exclusive_group()
    modo.add_argument('--confirmar', choices=['CONFIGURAR'])
    modo.add_argument('--diagnostico-mysql', action='store_true',
                      help='Mostra apenas a conta autenticada com a configuração do serviço; não aplica mudanças.')
    args = parser.parse_args(argv)
    if os.name != 'posix' or os.geteuid() != 0:
        parser.error('Execute como root no servidor Linux. Não execute no Windows.')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.@-]*', args.servico) or args.empresa < 1:
        parser.error('Serviço ou empresa inválidos.')
    conn = None
    etapa = 'validacao'
    try:
        import mysql.connector
        import pwd
        from dotenv import dotenv_values
        def propriedade(chave):
            return subprocess.check_output(['systemctl', 'show', args.servico, '-p', chave, '--value'], text=True).strip()
        if propriedade('WorkingDirectory') != str(ROOT):
            raise ValueError('O serviço informado não usa este diretório do ERP.')
        dono = pwd.getpwnam(propriedade('User') or 'root')
        arquivos_ambiente = propriedade('EnvironmentFiles')
        esperado = f'{ENV} (ignore_errors=no)'
        if arquivos_ambiente and arquivos_ambiente != esperado:
            raise ValueError('O serviço usa outro arquivo de ambiente. É necessário revisar essa configuração antes de criar o cofre; nada foi alterado.')
        for atribuicao in shlex.split(propriedade('Environment')):
            chave, separador, valor = atribuicao.partition('=')
            if separador and (chave.startswith('MYSQL_') or chave.startswith('DSYSTEM_INTER_')):
                os.environ[chave] = valor
        arquivo_protegido(ENV)
        if ENV.exists():
            if not ENV.read_text().startswith(MARCA):
                raise ValueError('Já existe arquivo de cofre não gerenciado. Não será substituído.')
            # EnvironmentFile tem precedência sobre Environment no systemd.
            valores_cofre = dict(dotenv_values(ENV))
            if not all(valores_cofre.get(k) for k in ('DSYSTEM_INTER_CONFIG_DATABASE', 'DSYSTEM_INTER_MASTER_KEY', 'DSYSTEM_INTER_CERT_DIR')):
                raise ValueError('O arquivo de cofre existente está incompleto. Recupere a configuração original; nada será substituído.')
            os.environ.update({k: v for k, v in valores_cofre.items() if v is not None})
        banco_erp = config_val('MYSQL_DATABASE', 'banco_dsystem')
        conn = mysql.connector.connect(**mysql_connection_config(banco_erp))
        cur = conn.cursor(dictionary=True)
        if args.diagnostico_mysql:
            cur.execute('SELECT CURRENT_USER() AS conta_mysql')
            conta = cur.fetchone()['conta_mysql']
            # Saída de diagnóstico não é SQL executável e não inclui credenciais.
            print('Conta MySQL autenticada do ERP: ' + str(conta).replace('\n', '').replace('\r', ''))
            print('Diagnóstico somente leitura. Nenhuma base, chave, permissão ou serviço foi alterado.')
            return 0
        cur.execute('SELECT username,is_admin,submodulos FROM usuarios WHERE username=%s', (args.usuario,))
        usuario = cur.fetchone()
        if (not usuario or str(usuario['is_admin']).lower() not in ('1', 'true')
                or not usuario_tem_permissao('inter.configurar', usuario)
                or not usuario_tem_permissao('inter.view', usuario)):
            raise ValueError('Informe administrador autorizado a configurar e consultar o Inter.')
        cur.execute("SELECT chave,valor FROM configuracoes_sistema WHERE chave IN ('DSYSTEM_NOME','NFSE_CNPJ')")
        empresa = {r['chave']: r['valor'] for r in cur.fetchall()}
        nome = empresa.get('DSYSTEM_NOME') or config_val('DSYSTEM_NOME', '')
        cnpj = conferir_empresa(None, nome, empresa.get('NFSE_CNPJ') or config_val('NFSE_CNPJ', ''))
        cur.execute('SHOW DATABASES')
        bases = [next(iter(r.values())) for r in cur.fetchall() if next(iter(r.values())).endswith('_inter_config')]
        base = escolher_base(config_val('DSYSTEM_INTER_CONFIG_DATABASE', ''), bases, banco_erp)
        cifrados = False
        existente = None
        for candidata in sorted(set(bases) | {base}):
            if not re.fullmatch(r'[A-Za-z0-9_]+_inter_config', candidata):
                raise ValueError('Base Inter existente com nome não suportado; revise antes de continuar.')
            cur.execute('SELECT TABLE_NAME,ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=%s', (candidata,))
            tabelas = {r['TABLE_NAME']: r['ENGINE'] for r in cur.fetchall()}
            if candidata == base and any(not t.startswith('inter_') or str(e).upper() != 'INNODB' for t,e in tabelas.items()):
                raise ValueError('A base selecionada contém tabelas incompatíveis. Nada será convertido.')
            for tabela, coluna in (('inter_contas','credencial_secret'), ('inter_operacoes','payload_secret'), ('inter_painel','snapshot_secret')):
                if tabela in tabelas:
                    cur.execute(f'SELECT 1 FROM `{candidata}`.`{tabela}` WHERE `{coluna}` IS NOT NULL LIMIT 1')
                    cifrados = bool(cur.fetchone()) or cifrados
            if candidata == base and 'inter_empresas' in tabelas:
                cur.execute(f'SELECT id,nome,cnpj FROM `{base}`.inter_empresas WHERE id=%s OR cnpj=%s', (args.empresa, cnpj))
                rows = cur.fetchall()
                if any(r['id'] != args.empresa for r in rows):
                    raise ValueError('Esse CNPJ já usa outro ID bancário. Informe o ID existente.')
                existente = rows[0] if rows else None
        conferir_empresa(existente, nome, cnpj)
        chave_atual = config_val('DSYSTEM_INTER_MASTER_KEY', '')
        if not chave_atual and ENV.exists():
            raise ValueError('O cofre existente não possui chave mestra. Recupere a configuração original.')
        chave = escolher_chave(chave_atual, cifrados)
        cert_dir = Path(config_val('DSYSTEM_INTER_CERT_DIR', '') or '/var/lib/dsystem-inter-certificados')
        if (not cert_dir.is_absolute() or cert_dir.is_symlink() or cert_dir.resolve().is_relative_to(ROOT)
                or cert_dir.resolve() != cert_dir or any(p.is_symlink() for p in cert_dir.parents)
                or not re.fullmatch(r'/[A-Za-z0-9_./-]+', str(cert_dir))):
            raise ValueError('Diretório de certificados deve ser absoluto e externo ao projeto.')
        if not cert_dir.parent.is_dir():
            raise ValueError('Crie primeiro a pasta pai do diretório de certificados com permissões adequadas ao usuário do ERP.')
        if cert_dir.exists() and (not cert_dir.is_dir() or cert_dir.stat().st_uid != dono.pw_uid or cert_dir.stat().st_mode & 0o077):
            raise ValueError('O diretório de certificados existente tem proprietário/permissões incompatíveis; ele não foi alterado.')
        dropin = Path('/etc/systemd/system') / (args.servico+'.d') / '90-dsystem-inter.conf'
        texto_dropin = MARCA + f'[Service]\nEnvironmentFile={ENV}\n'
        if dropin.is_symlink() or (dropin.exists() and dropin.read_text() != texto_dropin):
            raise ValueError('Já existe um ajuste systemd diferente. Não será substituído.')
        print(f'Base isolada: {base}. Empresa {args.empresa}: {nome}. Acesso: {usuario["username"]}.')
        if not args.confirmar:
            print('Prévia aprovada. Use --confirmar CONFIGURAR para aplicar. Nenhuma alteração ou chamada bancária.')
            return 0
        os.umask(0o077)
        etapa = 'cofre'
        ENV.parent.mkdir(parents=True, exist_ok=True)
        if not ENV.exists():
            with ENV.open('x', encoding='utf-8') as f:
                f.write(MARCA + f'DSYSTEM_INTER_CONFIG_DATABASE={base}\nDSYSTEM_INTER_MASTER_KEY={chave}\nDSYSTEM_INTER_CERT_DIR={cert_dir}\n')
            ENV.chmod(0o600)
        # Chave é salva ANTES de criar dados; uma interrupção não gera nova chave.
        etapa = 'certificados'
        cert_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chown(cert_dir, dono.pw_uid, dono.pw_gid)
        etapa = 'base'
        cur.execute(f'CREATE DATABASE IF NOT EXISTS `{base}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci')
        conn.commit()
        etapa = 'tabelas'
        repo = RepositorioInter(lambda: mysql.connector.connect(**mysql_connection_config(base)))
        repo.schema()
        etapa = 'vinculo'
        with repo.transacao() as c:
            repo.executar(c, 'SELECT id,nome,cnpj FROM inter_empresas WHERE id=%s FOR UPDATE', (args.empresa,))
            atual = c.fetchone()
            conferir_empresa(atual, nome, cnpj)
            if not atual:
                repo.executar(c, 'INSERT INTO inter_empresas (id,nome,cnpj) VALUES (%s,%s,%s)', (args.empresa,nome,cnpj))
            repo.executar(c, 'SELECT usuario FROM inter_acessos WHERE empresa_id=%s AND usuario=%s', (args.empresa,usuario['username']))
            if not c.fetchone():
                repo.executar(c, 'INSERT INTO inter_acessos (empresa_id,usuario) VALUES (%s,%s)', (args.empresa,usuario['username']))
            repo.registrar(c,args.empresa,'producao',usuario['username'],'ESTRUTURA_SERVIDOR_CONFIGURADA')
        etapa = 'systemd'
        dropin.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
        if not dropin.exists():
            with dropin.open('x', encoding='utf-8') as f:
                f.write(texto_dropin)
            dropin.chmod(0o644)
        etapa = 'reload'
        subprocess.run(['systemctl','daemon-reload'],check=True)
        etapa = 'restart'
        subprocess.run(['systemctl','restart',args.servico],check=True)
        etapa = 'status'
        subprocess.run(['systemctl','is-active',args.servico],check=True)
        print('Base, cofre e vínculo prontos. Nenhuma chamada bancária ou alteração de pagamentos. Cadastre as chaves pelo acesso seguro ao ERP.')
        print('Para o agendador Linux, use --arquivo-ambiente /etc/dsystem/inter.env.')
        return 0
    except ValueError as erro:
        print(str(erro),file=sys.stderr)
        return 1
    except Exception as erro:
        print(diagnostico_seguro(erro, etapa),file=sys.stderr)
        return 1
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                print('Não foi possível encerrar a conexão MySQL normalmente.', file=sys.stderr)


if __name__ == '__main__':
    raise SystemExit(main())
