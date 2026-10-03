$ErrorActionPreference = 'Stop'
$appRoot = $PSScriptRoot
$toolRoot = Split-Path -Parent $appRoot
& (Join-Path $appRoot 'build_icon.ps1')
New-Item -ItemType Directory -Force -Path (Join-Path $toolRoot 'runtime\build') | Out-Null
Push-Location (Join-Path $toolRoot 'runtime\build')
try {
    & rc.exe /nologo /I $appRoot /fo launcher.res (Join-Path $appRoot 'launcher.rc')
    if ($LASTEXITCODE -ne 0) { throw 'Icon resource compilation failed' }
    & cl /nologo /std:c++17 /MT /EHsc /O2 (Join-Path $appRoot 'launcher.cpp') "/Fe:$(Join-Path $toolRoot 'CyTools_MeshStudio.exe')" /link /SUBSYSTEM:WINDOWS user32.lib launcher.res
    if ($LASTEXITCODE -ne 0) { throw 'Compilation du lanceur echouee' }
} finally { Pop-Location }
