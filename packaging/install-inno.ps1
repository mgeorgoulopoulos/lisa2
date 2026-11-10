$ErrorActionPreference = 'Stop'
$tools = Join-Path $PSScriptRoot '../build/inno-tools'
$compiler = Join-Path $tools 'compiler'
New-Item -ItemType Directory -Path $tools -Force | Out-Null
$setup = Join-Path $tools 'setup.exe'
if (-not (Test-Path (Join-Path $compiler 'ISCC.exe'))) {
    Invoke-WebRequest -Uri 'https://github.com/jrsoftware/issrc/releases/download/is-7_1_1/innosetup-7.1.1-x64.exe' -OutFile $setup
    $signature = Get-AuthenticodeSignature $setup
    if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notlike '*O=Pyrsys B.V.*') {
        throw 'Unexpected or invalid Inno Setup installer signature'
    }
    $process = Start-Process -FilePath $setup -ArgumentList '/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/PORTABLE=1','/CURRENTUSER',"/DIR=`"$compiler`"" -Wait -PassThru -WindowStyle Hidden
    if ($process.ExitCode -ne 0) { throw "Inno Setup compiler extraction failed: $($process.ExitCode)" }
}
if (-not (Test-Path (Join-Path $compiler 'ISCC.exe'))) { throw 'ISCC.exe is missing' }
if ($env:GITHUB_PATH) { (Resolve-Path $compiler).Path | Out-File -FilePath $env:GITHUB_PATH -Append -Encoding utf8 }
Write-Output (Join-Path (Resolve-Path $compiler).Path 'ISCC.exe')
