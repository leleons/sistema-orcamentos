param(
    [string]$HostName = $env:DSYSTEM_DEPLOY_HOST,
    [string]$User = "root",
    [string]$AppDir = "/opt/orcamento",
    [string]$ServiceName = "orcamento",
    [switch]$SkipBackup,
    [switch]$SkipTests,
    [switch]$SkipRestart,
    [switch]$CleanRemote,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Invoke-Checked {
    param(
        [string]$Label,
        [string[]]$Command
    )
    Write-Host "[$Label] $($Command -join ' ')" -ForegroundColor DarkGray
    if ($DryRun) {
        return
    }
    & $Command[0] @($Command[1..($Command.Length - 1)])
    if ($LASTEXITCODE -ne 0) {
        throw "Falha em: $Label"
    }
}

function Invoke-Remote {
    param(
        [string]$Label,
        [string]$RemoteCommand
    )
    Invoke-Checked $Label @("ssh", $Remote, $RemoteCommand)
}

function Send-File {
    param(
        [string]$Path,
        [string]$Destination
    )
    if (-not (Test-Path -LiteralPath $Path)) {
        Write-Host "Ignorando ausente: $Path" -ForegroundColor Yellow
        return
    }
    Invoke-Checked "scp $Path" @("scp", $Path, "${Remote}:$Destination")
}

function Send-Directory {
    param(
        [string]$Path,
        [string]$Destination
    )
    if (-not (Test-Path -LiteralPath $Path)) {
        Write-Host "Ignorando ausente: $Path" -ForegroundColor Yellow
        return
    }
    Invoke-Checked "scp -r $Path" @("scp", "-r", $Path, "${Remote}:$Destination")
}

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot
if ([string]::IsNullOrWhiteSpace($HostName)) {
    throw "Informe o servidor com -HostName ou defina DSYSTEM_DEPLOY_HOST."
}
$Remote = "$User@$HostName"

Write-Step "Deploy Dsystem ERP"
Write-Host "Projeto local: $ProjectRoot"
Write-Host "Servidor:      $Remote"
Write-Host "Destino:       $AppDir"
Write-Host "Servico:       $ServiceName"
if ($DryRun) {
    Write-Host "Modo DryRun: nenhum comando sera executado." -ForegroundColor Yellow
}

Write-Step "Validando arquivos locais"
$requiredFiles = @("orcamento.py", "requirements.txt", "mysql_schema.sql")
foreach ($file in $requiredFiles) {
    if (-not (Test-Path -LiteralPath $file)) {
        throw "Arquivo obrigatorio nao encontrado: $file"
    }
}

if (-not $SkipBackup) {
    Write-Step "Gerando backup no servidor antes do deploy"
    Invoke-Remote "backup pre-deploy" "cd $AppDir && mkdir -p backups/deploy_files && SNAP=backups/deploy_files/antes_`$(date +%Y%m%d_%H%M%S) && mkdir -p `"`$SNAP`" && cp -a orcamento.py requirements.txt mysql_schema.sql dsystem_erp migrations modules scripts tests static modelos_contratos *.png `"`$SNAP`" 2>/dev/null || true && if [ -f scripts/backup_mysql.py ]; then ./.venv/bin/python scripts/backup_mysql.py pre-deploy || true; fi && ls -1dt backups/deploy_files/antes_* 2>/dev/null | tail -n +3 | xargs -r rm -rf --"
}

Write-Step "Preparando pastas no servidor"
Invoke-Remote "mkdir app dirs" "mkdir -p $AppDir $AppDir/.streamlit $AppDir/static $AppDir/dsystem_erp $AppDir/tests $AppDir/scripts $AppDir/migrations $AppDir/modules $AppDir/modelos_contratos"

if ($CleanRemote) {
    Write-Step "Limpando pastas antigas no servidor"
    Invoke-Remote "clean known dirs" "case '$AppDir' in /opt/orcamento|/opt/orcamento/) rm -rf $AppDir/dsystem_erp $AppDir/migrations $AppDir/modules $AppDir/scripts $AppDir/tests $AppDir/static $AppDir/modelos_contratos ;; *) echo 'AppDir nao permitido para limpeza: $AppDir' >&2; exit 2 ;; esac && mkdir -p $AppDir/.streamlit $AppDir/static $AppDir/dsystem_erp $AppDir/tests $AppDir/scripts $AppDir/migrations $AppDir/modules $AppDir/modelos_contratos"
}

Write-Step "Enviando arquivos principais"
Send-File ".\orcamento.py" "$AppDir/orcamento.py"
Send-File ".\requirements.txt" "$AppDir/requirements.txt"
Send-File ".\mysql_schema.sql" "$AppDir/mysql_schema.sql"
Send-File ".\logo_dsystem.png" "$AppDir/logo_dsystem.png"
Send-File ".\logo_gt.png" "$AppDir/logo_gt.png"
Send-File ".\logo_lc_printer.jpg" "$AppDir/logo_lc_printer.jpg"
Send-File ".\.streamlit\config.toml" "$AppDir/.streamlit/config.toml"

Write-Step "Enviando pastas do sistema"
Send-Directory ".\dsystem_erp" "$AppDir/"
Send-Directory ".\migrations" "$AppDir/"
Send-Directory ".\modules" "$AppDir/"
Send-Directory ".\scripts" "$AppDir/"
Send-Directory ".\tests" "$AppDir/"
Send-Directory ".\static" "$AppDir/"
Send-Directory ".\modelos_contratos" "$AppDir/"

Write-Step "Instalando dependencias no servidor"
Invoke-Remote "pip install" "cd $AppDir && ./.venv/bin/python -m pip install -r requirements.txt"

if (-not $SkipTests) {
    Write-Step "Rodando testes no servidor"
    Invoke-Remote "unittest" "cd $AppDir && ./.venv/bin/python -m unittest discover -s tests"
}

if (-not $SkipRestart) {
    Write-Step "Reiniciando servico"
    Invoke-Remote "restart service" "systemctl restart $ServiceName && systemctl status $ServiceName --no-pager"
}

Write-Step "Deploy finalizado"
Write-Host "URL: http://$HostName`:8501" -ForegroundColor Green
