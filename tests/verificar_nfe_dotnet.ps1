# Validação independente, local, sem rede, banco ou escrita em arquivos.
# Lê XML UTF-8 pelo stdin. verifySignatureOnly=true não consulta cadeia/CRL.
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Security
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$documento = New-Object System.Xml.XmlDocument
$documento.PreserveWhitespace = $true
$documento.XmlResolver = $null
$documento.LoadXml([Console]::In.ReadToEnd())
if ($null -ne $documento.DocumentType) { throw 'DTD nao permitida' }
$assinaturas = $documento.GetElementsByTagName('Signature', 'http://www.w3.org/2000/09/xmldsig#')
if ($assinaturas.Count -ne 1) { throw 'Esperada uma assinatura' }
$validador = New-Object System.Security.Cryptography.Xml.SignedXml($documento)
$validador.LoadXml($assinaturas[0])
$certTexto = $assinaturas[0].GetElementsByTagName('X509Certificate', 'http://www.w3.org/2000/09/xmldsig#')[0].InnerText
$certificado = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2(,[Convert]::FromBase64String($certTexto))
$valida = $validador.CheckSignature($certificado, $true)
$siDoc = New-Object System.Xml.XmlDocument
$siDoc.PreserveWhitespace = $true
$siDoc.XmlResolver = $null
$siDoc.LoadXml($validador.SignedInfo.GetXml().OuterXml)
$transform = New-Object System.Security.Cryptography.Xml.XmlDsigC14NTransform
$transform.LoadInput($siDoc)
$sha = [System.Security.Cryptography.SHA256]::Create()
try {
    $hash = [BitConverter]::ToString($sha.ComputeHash($transform.GetOutput())).Replace('-', '').ToLowerInvariant()
    @{ valida = $valida; sha256_signedinfo_c14n = $hash } | ConvertTo-Json -Compress
} finally {
    $sha.Dispose()
    $certificado.Dispose()
}
