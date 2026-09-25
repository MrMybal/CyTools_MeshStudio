$ErrorActionPreference = 'Stop'
$appRoot = $PSScriptRoot
$toolRoot = Split-Path -Parent $appRoot
New-Item -ItemType Directory -Force -Path (Join-Path $toolRoot 'runtime\build') | Out-Null
Push-Location (Join-Path $toolRoot 'runtime\build')
try {
    & cl /nologo /std:c++17 /MT /EHsc /O2 (Join-Path $appRoot 'launcher.cpp') "/Fe:$(Join-Path $toolRoot 'CyTools_MeshStudio.exe')" /link /SUBSYSTEM:WINDOWS user32.lib
    if ($LASTEXITCODE -ne 0) { throw 'Compilation du lanceur echouee' }
} finally { Pop-Location }
