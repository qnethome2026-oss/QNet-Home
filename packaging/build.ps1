# SPDX-License-Identifier: AGPL-3.0-or-later
# QNet Home - a privacy-first, multi-device home safety system.
# Copyright (C) 2026 QNet Home contributors. This is free software under the
# GNU Affero General Public License v3 or later, with ABSOLUTELY NO WARRANTY.
#
# packaging/build.ps1 - PyInstaller build of the dashboard app (T5.3, DESIGN S14).
#
# Produces dist\QNetHome\QNetHome.exe from qnet\app.py.
#
#   --onedir, NOT --onefile, and that is DESIGN S14's call, not a default:
#   onefile unpacks the whole bundle to a temp dir on every launch, which costs
#   seconds before anything appears on screen. This app's entire job is to put
#   the dashboard on screen, so launch latency is the only performance number it
#   has. onedir also makes the MSIX honest - makeappx packs a real directory
#   layout instead of one opaque blob.
#
# Run from the repo root:
#     powershell -ExecutionPolicy Bypass -File packaging\build.ps1
#
# Requires the [dev] extra (pyinstaller). Nothing here is a runtime dependency
# of qnet itself - the shipped app imports stdlib only.

[CmdletBinding()]
param(
    # Skip the post-build launch check (which opens a browser tab for 5s).
    [switch]$NoVerify
)

$ErrorActionPreference = 'Stop'

# Repo root is this script's parent's parent - so the build works from any cwd.
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Python = Join-Path $RepoRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $Python)) {
    throw "No venv python at $Python. Create .venv and `pip install -e .[dev]` first."
}

Write-Host '== QNet Home :: PyInstaller build ==' -ForegroundColor Cyan
& $Python -c "import PyInstaller, sys; print('PyInstaller', PyInstaller.__version__, '| python', sys.version.split()[0], sys.platform)"
if ($LASTEXITCODE -ne 0) { throw 'pyinstaller not installed. pip install -e .[dev]' }

# Data files, as source-relative-path => destination-dir-in-bundle. The
# destinations mirror the repo layout so qnet/app.py's bundle_root() lookup is
# identical in dev and frozen - see DASHBOARD_REL / FIXTURE_REL there.
$DataFiles = @{
    'dashboard\index.html'             = 'dashboard'
    'dev\fixtures\replay_demo.jsonl'   = 'dev\fixtures'
}

# Sources must be ABSOLUTE: --specpath puts the spec in packaging\, and
# PyInstaller resolves relative `datas` against the spec's directory, not the
# cwd - so 'dashboard\index.html' would be looked up as packaging\dashboard\...
$AddData = @()
foreach ($src in $DataFiles.Keys) {
    if (-not (Test-Path $src)) { throw "Data file missing: $src" }
    $AddData += ('{0};{1}' -f (Resolve-Path $src).Path, $DataFiles[$src])
}

# A clean tree every time: a stale dist\QNetHome is how a build "passes" while
# shipping last week's dashboard.
foreach ($dir in @('dist\QNetHome', 'build\QNetHome')) {
    if (Test-Path $dir) { Remove-Item -Recurse -Force $dir }
}

$args = @(
    '-m', 'PyInstaller',
    '--noconfirm',
    '--onedir',
    '--console',
    '--name', 'QNetHome',
    '--distpath', 'dist',
    '--workpath', 'build',
    '--specpath', 'packaging'
)
foreach ($pair in $AddData) { $args += @('--add-data', $pair) }
$args += 'qnet\app.py'

Write-Host "-> $Python $($args -join ' ')" -ForegroundColor DarkGray
& $Python @args
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE" }

$Exe = Join-Path $RepoRoot 'dist\QNetHome\QNetHome.exe'
if (-not (Test-Path $Exe)) { throw "Build reported success but $Exe does not exist" }

$bytes = (Get-ChildItem -Recurse -File 'dist\QNetHome' | Measure-Object -Property Length -Sum).Sum
$files = (Get-ChildItem -Recurse -File 'dist\QNetHome' | Measure-Object).Count
Write-Host ''
Write-Host ('BUILD OK  {0}' -f $Exe) -ForegroundColor Green
Write-Host ('  dist size : {0:N1} MB across {1} files' -f ($bytes / 1MB), $files)

# Confirm the bundled data files landed where app.py will look for them.
foreach ($rel in @('_internal\dashboard\index.html', '_internal\dev\fixtures\replay_demo.jsonl')) {
    $p = Join-Path 'dist\QNetHome' $rel
    if (Test-Path $p) {
        Write-Host ('  bundled   : {0} ({1:N0} bytes)' -f $rel, (Get-Item $p).Length)
    } else {
        throw "Data file did not make it into the bundle: $rel"
    }
}

if (-not $NoVerify) {
    Write-Host ''
    Write-Host '== launch check (--self-close 5) ==' -ForegroundColor Cyan
    & $Exe --self-close 5
    if ($LASTEXITCODE -ne 0) { throw "Launch check failed with exit code $LASTEXITCODE" }
    Write-Host 'LAUNCH OK' -ForegroundColor Green
}

Write-Host ''
Write-Host 'Next: packaging\make_msix.ps1 to pack dist\QNetHome into dist\QNetHome.msix'
