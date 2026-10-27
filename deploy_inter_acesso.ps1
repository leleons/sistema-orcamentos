param(
    [string]$HostName = '2.25.130.92',
    [string]$User = 'root',
    [switch]$DryRun
)
$ErrorActionPreference = 'Stop'
if ($HostName -notmatch '^[A-Za-z0-9][A-Za-z0-9.-]*$' -or $User -notmatch '^[A-Za-z_][A-Za-z0-9_-]*$') {
    throw 'Servidor ou usuario SSH invalido.'
}
$destinoInter = "$User@$HostName"
$raizInter = $PSScriptRoot
$arquivosInter = @(
    'dsystem_erp/services/permissions.py',
    'dsystem_erp/services/inter_acessos.py',
    'dsystem_erp/pages/usuarios.py',
    'tests/test_permissions.py',
    'tests/test_inter_api.py'
)
foreach ($arquivoInter in $arquivosInter) {
    if (-not (Test-Path -LiteralPath (Join-Path $raizInter $arquivoInter) -PathType Leaf)) {
        throw "Arquivo obrigatorio ausente: $arquivoInter"
    }
}
function Executar-Inter {
    param([string]$Programa, [string[]]$Argumentos)
    Write-Host "$Programa $($Argumentos -join ' ')"
    if ($DryRun) { return }
    & $Programa @Argumentos
    if ($LASTEXITCODE -ne 0) {
        throw 'Envio interrompido. Nenhuma etapa seguinte foi executada. Se os arquivos ja foram copiados, use o backup indicado para recuperacao; nao ha rollback automatico.'
    }
}
Write-Host 'Atualizacao pontual: 3 arquivos de codigo e 2 testes. Sem banco de dados, chaves, certificados ou outros modulos.'
if ($DryRun) { Write-Host 'SIMULACAO: nenhum acesso ao servidor.' }
$backupInter = 'cd /opt/orcamento && mkdir -p backups_codigo && b=$(mktemp /opt/orcamento/backups_codigo/inter-acesso-XXXXXX.tar.gz) && tar -czf "$b" -- ' + ($arquivosInter -join ' ') + ' && echo "Backup: $b"'
Executar-Inter -Programa 'ssh' -Argumentos @($destinoInter, $backupInter)
foreach ($arquivoInter in $arquivosInter) {
    Executar-Inter -Programa 'scp' -Argumentos @((Join-Path $raizInter $arquivoInter), "${destinoInter}:/opt/orcamento/$arquivoInter")
}
Executar-Inter -Programa 'ssh' -Argumentos @($destinoInter,
    'cd /opt/orcamento && ./.venv/bin/python -m py_compile dsystem_erp/services/permissions.py dsystem_erp/services/inter_acessos.py dsystem_erp/pages/usuarios.py && ./.venv/bin/python -m unittest tests.test_permissions tests.test_inter_api -q && systemctl restart orcamento && systemctl is-active orcamento')
if (-not $DryRun) {
    Write-Host 'Correcao pontual enviada e testada. Saia e entre novamente como Daniel.fabio.'
}
