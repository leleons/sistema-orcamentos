param(
    [string]$HostName = '2.25.130.92',
    [string]$User = 'root',
    [switch]$Diagnostico,
    [switch]$DryRun
)
$ErrorActionPreference = 'Stop'
if ($HostName -notmatch '^[A-Za-z0-9][A-Za-z0-9.-]*$' -or $User -notmatch '^[A-Za-z_][A-Za-z0-9_-]*$') {
    throw 'Servidor ou usuario SSH invalido.'
}
$interDestino = "$User@$HostName"
$interArquivo = Join-Path $PSScriptRoot 'scripts\inter_configurar_servidor.py'
if (-not (Test-Path -LiteralPath $interArquivo -PathType Leaf)) { throw 'Preparador Inter nao encontrado.' }
function Executar-ConfiguracaoInter {
    param([string]$Programa, [string[]]$Argumentos)
    Write-Host "$Programa $($Argumentos -join ' ')"
    if ($DryRun) { return }
    & $Programa @Argumentos
    if ($LASTEXITCODE -ne 0) { throw 'Configuracao interrompida. Nao apague chaves ou bases para tentar novamente. Envie somente a mensagem de erro, sem segredos.' }
}
Write-Host 'Envia apenas o preparador Inter. Preserva credenciais existentes e nao executa transacoes bancarias.'
if ($DryRun) { Write-Host 'SIMULACAO: nenhum acesso ao servidor.' }
# Nome dedicado: nao substitui os modulos do ERP nem envia o .env local.
Executar-ConfiguracaoInter -Programa 'scp' -Argumentos @($interArquivo, "${interDestino}:/opt/orcamento/scripts/inter_configurar_servidor.py")
$interModo = if ($Diagnostico) { '--diagnostico-mysql' } else { '--confirmar CONFIGURAR' }
Executar-ConfiguracaoInter -Programa 'ssh' -Argumentos @($interDestino,
    "cd /opt/orcamento && ./.venv/bin/python scripts/inter_configurar_servidor.py --usuario Daniel.fabio --empresa 1 $interModo")
if (-not $DryRun) {
    if ($Diagnostico) { Write-Host 'Diagnostico concluido. Nenhuma configuracao foi aplicada.' }
    else { Write-Host 'Preparo concluido. Acesse a configuracao de chaves pelo HTTPS ou tunel SSH; nunca envie chaves por HTTP publico.' }
}
