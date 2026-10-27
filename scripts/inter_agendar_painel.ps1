param(
    [Parameter(Mandatory=$true)][int]$Empresa,
    [Parameter(Mandatory=$true)][string]$Usuario,
    [string]$Python = ''
)
$ErrorActionPreference = 'Stop'
if ($Empresa -le 0 -or $Usuario -notmatch '^[\p{L}\p{N}_.@-]+$') {
    throw 'Informe empresa e login ERP validos.'
}
if ((Get-TimeZone).Id -ne 'E. South America Standard Time') {
    throw 'Configure o fuso do Windows como Brasilia antes de instalar os horarios 08:00 e 12:00.'
}
$interRaiz = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$interScript = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot 'inter_atualizar_painel.py')).Path
if (-not $Python) { $Python = (& python -c 'import sys; print(sys.executable)').Trim() }
$interPython = (Resolve-Path -LiteralPath $Python).Path
$interPythonJanela = Join-Path (Split-Path -Parent $interPython) 'pythonw.exe'
if (-not (Test-Path -LiteralPath $interPythonJanela)) { throw 'pythonw.exe nao encontrado junto ao Python informado.' }
$interHash = [System.Security.Cryptography.SHA256]::Create()
try {
    $interSufixo = [BitConverter]::ToString($interHash.ComputeHash([Text.Encoding]::UTF8.GetBytes($interRaiz))).Replace('-','').Substring(0,12)
} finally { $interHash.Dispose() }
$interNome = "DSystem-Inter-Consulta-$interSufixo-$Empresa"
$interArgumentos = '"{0}" --empresa {1} --usuario "{2}" --agendado' -f $interScript, $Empresa, $Usuario
$interExistente = Get-ScheduledTask -TaskName $interNome -ErrorAction SilentlyContinue
if ($interExistente -and ($interExistente.Description -notlike 'DSystem: somente saldo/extrato Inter, 08h e 12h *' -or
    $interExistente.Actions.Arguments -ne $interArgumentos -or $interExistente.Actions.Execute -ne $interPythonJanela)) {
    throw 'Ja existe uma tarefa diferente com esse nome; nenhuma tarefa foi substituida.'
}
& $interPython $interScript --empresa $Empresa --usuario $Usuario --preparar
if ($LASTEXITCODE -ne 0) { throw 'Nao foi possivel preparar a agenda segura.' }
$interWindowsUsuario = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$interAcao = New-ScheduledTaskAction -Execute $interPythonJanela -Argument $interArgumentos -WorkingDirectory $interRaiz
$interGatilhos = @(
    (New-ScheduledTaskTrigger -Daily -At '08:00'),
    (New-ScheduledTaskTrigger -Daily -At '12:00'),
    (New-ScheduledTaskTrigger -AtLogOn -User $interWindowsUsuario),
    (New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(5) -RepetitionInterval (New-TimeSpan -Minutes 5))
)
$interPrincipal = New-ScheduledTaskPrincipal -UserId $interWindowsUsuario -LogonType Interactive -RunLevel Limited
$interOpcoes = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 20) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName $interNome -Action $interAcao -Trigger $interGatilhos `
    -Principal $interPrincipal -Settings $interOpcoes `
    -Description 'DSystem: somente saldo/extrato Inter, 08h e 12h BRT.' -Force | Out-Null
& $interPython $interScript --empresa $Empresa --usuario $Usuario --ativar
if ($LASTEXITCODE -ne 0) {
    Disable-ScheduledTask -TaskName $interNome | Out-Null
    throw 'Agenda nao ativada no ERP; tarefa deixada desabilitada.'
}
Write-Output "Agenda instalada: $interNome. 08h e 12h (Brasilia), somente consultas."
Write-Output 'O PC/MySQL precisam estar ligados e o usuario Windows conectado (pode estar bloqueado). A cada 5 minutos verifica pendencias; so consulta o Inter se faltar o ultimo horario ou se o cache da conta foi invalidado. Falhas sao tentadas novamente sem repetir horarios concluidos.'
