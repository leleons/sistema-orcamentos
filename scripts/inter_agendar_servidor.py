"""Instala timer systemd somente de consulta. Executar NO servidor, como root."""
import argparse
import os
from pathlib import Path
import re
import subprocess

MARCA = '# Gerenciado por DSystem: agenda Inter somente leitura\n'


def unidades(raiz, empresa, usuario, usuario_sistema, grupo='', arquivo_ambiente=''):
    # Não aceitar sintaxe de expansão de systemd ou argumentos injetados.
    for valor in (str(raiz), usuario, usuario_sistema, grupo, arquivo_ambiente):
        if valor and not re.fullmatch(r'[\w./@-]+', valor, flags=re.ASCII):
            raise ValueError('Caminho/login incompatível com a configuração segura do timer.')
    if empresa <= 0 or not str(raiz).startswith('/') or not usuario or not usuario_sistema:
        raise ValueError('Empresa, diretório e usuários obrigatórios.')
    nome = f'dsystem-inter-painel-{empresa}'
    ambiente = f'EnvironmentFile={arquivo_ambiente}\n' if arquivo_ambiente else ''
    grupo_linha = f'Group={grupo}\n' if grupo else ''
    servico = MARCA + f'''[Unit]
Description=DSystem Inter - somente saldo e extrato (empresa {empresa})
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User={usuario_sistema}
{grupo_linha}WorkingDirectory={raiz}
{ambiente}ExecStart={raiz}/.venv/bin/python {raiz}/scripts/inter_atualizar_painel.py --empresa {empresa} --usuario {usuario} --agendado
TimeoutStartSec=20min
UMask=0077
NoNewPrivileges=true
'''
    timer = MARCA + f'''[Unit]
Description=DSystem Inter - 08h/12h Brasilia e recuperacao de pendencias

[Timer]
OnCalendar=*-*-* 08,12:00:00 America/Sao_Paulo
OnBootSec=2min
OnUnitActiveSec=5min
Persistent=true
AccuracySec=1s
Unit={nome}.service

[Install]
WantedBy=timers.target
'''
    return nome, servico, timer


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--empresa', type=int, required=True)
    parser.add_argument('--usuario', required=True, help='Administrador ERP com inter.view/configurar e vínculo à empresa')
    parser.add_argument('--servico-erp', default='orcamento.service')
    parser.add_argument('--arquivo-ambiente', default='', help='Arquivo de ambiente protegido, se o serviço ERP o utiliza')
    parser.add_argument('--instalar', action='store_true', help='Sem esta opção, somente mostra as unidades propostas')
    args = parser.parse_args(argv)
    if os.name != 'posix' or os.geteuid() != 0:
        parser.error('Execute como root no Linux do servidor; não execute no Windows.')
    if not re.fullmatch(r'[A-Za-z0-9_.@-]+', args.servico_erp) or args.servico_erp.startswith('-'):
        parser.error('Nome de serviço inválido.')
    raiz = Path(__file__).resolve().parents[1]
    def propriedade(chave):
        return subprocess.check_output(['systemctl', 'show', args.servico_erp,
                                        '--property='+chave, '--value'], text=True).strip()
    if propriedade('WorkingDirectory') != str(raiz):
        parser.error('O serviço ERP deve existir e usar este diretório de trabalho. Nada instalado.')
    usuario_sistema, grupo = propriedade('User') or 'root', propriedade('Group')
    if (propriedade('Environment') or propriedade('EnvironmentFiles')) and not args.arquivo_ambiente:
        parser.error('O ERP usa ambiente do systemd. Informe --arquivo-ambiente protegido com a mesma configuração necessária ao banco/cofre.')
    if args.arquivo_ambiente:
        arq = Path(args.arquivo_ambiente)
        if not arq.is_absolute() or not arq.is_file() or arq.stat().st_mode & 0o077:
            parser.error('Arquivo de ambiente deve ser absoluto, existente e restrito (chmod 600).')
    nome, servico, timer = unidades(raiz, args.empresa, args.usuario, usuario_sistema, grupo, args.arquivo_ambiente)
    if not args.instalar:
        print(servico + '\n' + timer)
        return 0
    destinos = {Path('/etc/systemd/system') / (nome+'.service'): servico,
                Path('/etc/systemd/system') / (nome+'.timer'): timer}
    for caminho in destinos:
        if caminho.is_symlink() or (caminho.exists() and not caminho.read_text().startswith(MARCA)):
            raise ValueError('Uma unidade não gerenciada já existe. Nada foi substituído.')
    # Mesmo usuário/ambiente do futuro timer. Validação não acessa o Inter.
    base = ['systemd-run', '--quiet', '--wait', '--pipe', '--collect',
            '-p', f'User={usuario_sistema}', '-p', f'WorkingDirectory={raiz}']
    if grupo:
        base += ['-p', f'Group={grupo}']
    if args.arquivo_ambiente:
        base += ['-p', f'EnvironmentFile={args.arquivo_ambiente}']
    base += [str(raiz/'.venv/bin/python'), str(raiz/'scripts/inter_atualizar_painel.py'),
             '--empresa', str(args.empresa), '--usuario', args.usuario]
    subprocess.run([*base, '--verificar'], check=True)
    subprocess.run([*base, '--preparar'], check=True)
    for caminho, conteudo in destinos.items():
        caminho.write_text(conteudo, encoding='utf-8')
        caminho.chmod(0o644)
    subprocess.run(['systemctl', 'daemon-reload'], check=True)
    subprocess.run([*base, '--ativar'], check=True)
    subprocess.run(['systemctl', 'enable', '--now', nome+'.timer'], check=True)
    print('Timer instalado. Apenas saldo/extrato; pendências são verificadas a cada 5 minutos.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
