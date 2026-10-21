param(
    [Parameter(Mandatory=$true)][string]$Imagem,
    [Parameter(Mandatory=$true)][string]$Zip
)
# Importação local de captura fornecida pelo operador. Nunca imprime texto OCR,
# segredos ou argumentos sensíveis. O Python cifra usando DPAPI do usuário atual.
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType=WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType=WindowsRuntime]
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType=WindowsRuntime]
$null = [Windows.Storage.Streams.IRandomAccessStream, Windows.Storage.Streams, ContentType=WindowsRuntime]
$null = [Windows.Graphics.Imaging.SoftwareBitmap, Windows.Graphics.Imaging, ContentType=WindowsRuntime]
$null = [Windows.Media.Ocr.OcrResult, Windows.Foundation, ContentType=WindowsRuntime]
$taskMethod = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetParameters().Count -eq 1 -and
    $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
} | Select-Object -First 1
function Wait-WinRT($Operation, [Type]$ResultType) {
    $task = $taskMethod.MakeGenericMethod($ResultType).Invoke($null, @($Operation))
    $task.Wait()
    return $task.Result
}
$arquivo = Wait-WinRT ([Windows.Storage.StorageFile]::GetFileFromPathAsync((Resolve-Path -LiteralPath $Imagem).Path)) ([Windows.Storage.StorageFile])
$stream = Wait-WinRT ($arquivo.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
try {
    $decoder = Wait-WinRT ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
    $transform = New-Object Windows.Graphics.Imaging.BitmapTransform
    $transform.ScaledWidth = $decoder.PixelWidth * 2
    $transform.ScaledHeight = $decoder.PixelHeight * 2
    $bitmap = Wait-WinRT ($decoder.GetSoftwareBitmapAsync(
        [Windows.Graphics.Imaging.BitmapPixelFormat]::Bgra8,
        [Windows.Graphics.Imaging.BitmapAlphaMode]::Ignore, $transform,
        [Windows.Graphics.Imaging.ExifOrientationMode]::IgnoreExifOrientation,
        [Windows.Graphics.Imaging.ColorManagementMode]::DoNotColorManage)) ([Windows.Graphics.Imaging.SoftwareBitmap])
    $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
    $resultado = Wait-WinRT ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
    $texto = $resultado.Text -replace '\s*[-\u2212\u2014\u2013]\s*','-'
    $texto = $texto -replace '\s+', ''
    # UUIDs sao hexadecimais. OCR Windows pode ler o algarismo zero como O.
    $padrao = '[a-fA-F0-9O]{8}(?:-[a-fA-F0-9O]{4}){3}-[a-fA-F0-9O]{12}'
    $identificadores = @([regex]::Matches($texto, $padrao) | ForEach-Object { $_.Value.ToLowerInvariant().Replace('o','0') } | Select-Object -Unique)
    $segredo = [regex]::Match($texto, '(?i)clientSecret:\s*(' + $padrao + ')')
    if ($identificadores.Count -ne 2 -or -not $segredo.Success) {
        throw 'OCR inconclusivo. Use o cadastro manual protegido; nenhum segredo foi salvo.'
    }
    $secret = $segredo.Groups[1].Value.ToLowerInvariant().Replace('o','0')
    $client = @($identificadores | Where-Object { $_ -ne $secret })
    if ($client.Count -ne 1) { throw 'Identificadores ambiguos. Nada foi salvo.' }
    $dados = @{client_id=$client[0];client_secret=$secret} | ConvertTo-Json -Compress
    $resolvedZip = (Resolve-Path -LiteralPath $Zip).Path
    if ($resolvedZip.Contains('"')) { throw 'Caminho invalido.' }
    $processo = New-Object System.Diagnostics.Process
    $processo.StartInfo.FileName = (Get-Command python -ErrorAction Stop).Source
    $processo.StartInfo.Arguments = '-m scripts.inter_preparar_local --credenciais-stdin --zip "' + $resolvedZip + '"'
    $processo.StartInfo.WorkingDirectory = Split-Path -Parent $PSScriptRoot
    $processo.StartInfo.UseShellExecute = $false
    $processo.StartInfo.CreateNoWindow = $true
    $processo.StartInfo.RedirectStandardInput = $true
    $null = $processo.Start()
    $processo.StandardInput.Write($dados)
    $processo.StandardInput.Close()
    $processo.WaitForExit()
    if ($processo.ExitCode -ne 0) { throw 'Nao foi possivel concluir o cadastro protegido.' }
} finally {
    $texto = $dados = $secret = $client = $identificadores = $resultado = $segredo = $null
    if ($bitmap) { $bitmap.Dispose() }
    $stream.Dispose()
}
