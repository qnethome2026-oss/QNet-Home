# SPDX-License-Identifier: AGPL-3.0-or-later
# QNet Home - a privacy-first, multi-device home safety system.
# Copyright (C) 2026 QNet Home contributors. This is free software under the
# GNU Affero General Public License v3 or later, with ABSOLUTELY NO WARRANTY.
#
# packaging/make_msix.ps1 - pack dist\QNetHome into dist\QNetHome.msix (T5.3).
#
# Runs after packaging\build.ps1. Steps:
#   1. find the Windows SDK arm64 makeappx.exe / signtool.exe
#   2. stage AppxManifest.xml + generated Assets\ into the PyInstaller onedir
#   3. makeappx pack  -> dist\QNetHome.msix
#   4. best-effort self-sign; if that needs elevation, leave the package
#      UNSIGNED and point at packaging\SIGNING.md
#
# An unsigned .msix is a real, installable artifact once its cert is trusted -
# so signing failing is a documented next step, not a build failure. The script
# exits 0 with an unsigned package on purpose.
#
# Run from anywhere:
#     powershell -ExecutionPolicy Bypass -File packaging\make_msix.ps1

[CmdletBinding()]
param(
    # Skip signing entirely and just produce the unsigned package.
    [switch]$NoSign
)

$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$PayloadDir = Join-Path $RepoRoot 'dist\QNetHome'
$MsixPath   = Join-Path $RepoRoot 'dist\QNetHome.msix'
$Manifest   = Join-Path $PSScriptRoot 'AppxManifest.xml'
$CertSubject = 'CN=QNetHome'   # MUST equal Identity/@Publisher in AppxManifest.xml

Write-Host '== QNet Home :: MSIX package ==' -ForegroundColor Cyan

# ---- 1. locate the SDK tools -------------------------------------------------
# DESIGN S14 expects them under the 10.0.26100.0 arm64 folder. Check that first,
# then fall back to a search, so this still works on a machine with a different
# SDK build installed. Newest version wins.
function Find-SdkTool([string]$Name) {
    $preferred = "C:\Program Files (x86)\Windows Kits\10\bin\10.0.26100.0\arm64\$Name"
    if (Test-Path $preferred) { return $preferred }
    $found = Get-ChildItem -Path 'C:\Program Files (x86)\Windows Kits\10\bin' `
        -Filter $Name -Recurse -ErrorAction SilentlyContinue |
        Where-Object { $_.DirectoryName -like '*\arm64' } |
        Sort-Object -Property FullName -Descending
    if ($found) { return $found[0].FullName }
    return $null
}

$MakeAppx = Find-SdkTool 'makeappx.exe'
$SignTool = Find-SdkTool 'signtool.exe'

if (-not $MakeAppx) {
    Write-Host 'BLOCKED: makeappx.exe (arm64) not found under Windows Kits\10\bin\*\arm64.' -ForegroundColor Red
    Write-Host 'Install the Windows 10/11 SDK ("MSIX Packaging Tools" workload) and re-run.'
    exit 3
}
Write-Host "  makeappx : $MakeAppx"
Write-Host ("  signtool : {0}" -f $(if ($SignTool) { $SignTool } else { '(not found - package will be unsigned)' }))

# ---- 2. stage manifest + assets into the payload ----------------------------
if (-not (Test-Path (Join-Path $PayloadDir 'QNetHome.exe'))) {
    throw "No build at $PayloadDir\QNetHome.exe. Run packaging\build.ps1 first."
}

$Python = Join-Path $RepoRoot '.venv\Scripts\python.exe'
Write-Host ''
Write-Host '-- assets --'
& $Python (Join-Path $PSScriptRoot 'make_logo.py') (Join-Path $PayloadDir 'Assets')
if ($LASTEXITCODE -ne 0) { throw 'logo generation failed' }

Copy-Item $Manifest (Join-Path $PayloadDir 'AppxManifest.xml') -Force
Write-Host "  staged AppxManifest.xml into $PayloadDir"

# ---- 3. pack ----------------------------------------------------------------
Write-Host ''
Write-Host '-- makeappx pack --'
if (Test-Path $MsixPath) { Remove-Item -Force $MsixPath }
& $MakeAppx pack /o /d $PayloadDir /p $MsixPath
if ($LASTEXITCODE -ne 0) { throw "makeappx failed with exit code $LASTEXITCODE" }
if (-not (Test-Path $MsixPath)) { throw 'makeappx reported success but produced no file' }

$msixMb = (Get-Item $MsixPath).Length / 1MB
Write-Host ('PACK OK   {0} ({1:N1} MB)' -f $MsixPath, $msixMb) -ForegroundColor Green

if ($NoSign) {
    Write-Host 'PACKAGE IS UNSIGNED (-NoSign). See packaging\SIGNING.md.' -ForegroundColor Yellow
    exit 0
}

# ---- 4. best-effort self-sign -----------------------------------------------
# Creating a cert in CurrentUser\My does not need elevation; TRUSTING it
# (importing to LocalMachine\Root) does. So this can legitimately get as far as
# a signed package that Windows still refuses to install until a human runs the
# one elevated trust command in SIGNING.md.
Write-Host ''
Write-Host '-- signing --'
if (-not $SignTool) {
    Write-Host 'UNSIGNED: no arm64 signtool.exe. See packaging\SIGNING.md.' -ForegroundColor Yellow
    exit 0
}

$cert = $null
try {
    $existing = Get-ChildItem Cert:\CurrentUser\My -ErrorAction Stop |
        Where-Object { $_.Subject -eq $CertSubject -and $_.NotAfter -gt (Get-Date) }
    if ($existing) {
        $cert = $existing[0]
        Write-Host "  reusing existing cert $($cert.Thumbprint)"
    } else {
        $cert = New-SelfSignedCertificate -Type CodeSigningCert -Subject $CertSubject `
            -KeyUsage DigitalSignature -FriendlyName 'QNet Home (self-signed, dev)' `
            -CertStoreLocation 'Cert:\CurrentUser\My' `
            -TextExtension @('2.5.29.37={text}1.3.6.1.5.5.7.3.3', '2.5.29.19={text}Subject Type:End Entity') `
            -ErrorAction Stop
        Write-Host "  created cert $($cert.Thumbprint)"
    }
} catch {
    Write-Host "UNSIGNED: could not create/read a signing certificate: $($_.Exception.Message)" -ForegroundColor Yellow
    Write-Host 'This usually means an elevated shell is needed. See packaging\SIGNING.md.'
    exit 0
}

try {
    & $SignTool sign /fd SHA256 /sha1 $cert.Thumbprint $MsixPath
    if ($LASTEXITCODE -ne 0) { throw "signtool exit code $LASTEXITCODE" }
    Write-Host 'SIGN OK (self-signed)' -ForegroundColor Green

    # Export the PUBLIC certificate next to the package. No private key, so this
    # needs no elevation - and it turns the human's remaining elevated step into
    # a one-liner against a file instead of a thumbprint hunt (SIGNING.md).
    $CerPath = Join-Path $RepoRoot 'dist\QNetHome.cer'
    Export-Certificate -Cert $cert -FilePath $CerPath -Type CERT | Out-Null
    Write-Host "  exported public cert -> $CerPath"

    Write-Host 'The certificate still has to be TRUSTED before Windows will install' -ForegroundColor Yellow
    Write-Host 'the package - that step needs an elevated shell: packaging\SIGNING.md.' -ForegroundColor Yellow
} catch {
    Write-Host "UNSIGNED: signtool failed: $($_.Exception.Message)" -ForegroundColor Yellow
    Write-Host 'See packaging\SIGNING.md for the manual commands.'
    exit 0
}

exit 0
