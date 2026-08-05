<!--
SPDX-License-Identifier: AGPL-3.0-or-later
QNet Home - a privacy-first, multi-device home safety system.
Copyright (C) 2026 QNet Home contributors. This is free software under the
GNU Affero General Public License v3 or later, with ABSOLUTELY NO WARRANTY.
-->

# Installing the QNet Home MSIX (T5.3)

`packaging/make_msix.ps1` already **packed and signed** `dist/QNetHome.msix`
with a self-signed certificate (`CN=QNetHome`), and exported that certificate's
public half to `dist/QNetHome.cer`. Both of those steps run fine in a normal,
non-elevated shell.

What is left is the one thing that genuinely needs Administrator: telling
Windows to **trust** that certificate. A self-signed root is not trusted by
anything until a human says so, and installing a root certificate is a
machine-wide change — by design, no build script can do it silently.

So `signtool verify /pa` on the package currently reports:

```
Signing Certificate Chain:
    Issued to: QNetHome
    Issued by: QNetHome
    SHA1 hash: B228573080D135A4DB3E951326522564342E9F8D
SignTool Error: A certificate chain processed, but terminated in a root
        certificate which is not trusted by the trust provider.
```

That is the expected state. The signature is real; the trust is not there yet.

## The two commands

Open **PowerShell as Administrator**, `cd` to the repo root, and run:

```powershell
# 1. Trust the signing certificate (machine-wide; needs Administrator)
Import-Certificate -FilePath .\dist\QNetHome.cer `
                   -CertStoreLocation Cert:\LocalMachine\Root

# 2. Install the package
Add-AppxPackage .\dist\QNetHome.msix
```

Then launch **QNet Home** from the Start menu. Between step 1 and step 2 you can
confirm the trust took by re-running the verify — it should now exit 0:

```powershell
& "C:\Program Files (x86)\Windows Kits\10\bin\10.0.26100.0\arm64\signtool.exe" `
    verify /pa .\dist\QNetHome.msix
```

## Uninstalling

```powershell
Get-AppxPackage QNetHome.Dashboard | Remove-AppxPackage
```

The app also leaves a per-user working copy of the dashboard at
`%LOCALAPPDATA%\QNetHome` (see `qnet/app.py` — it stages the HTML there so a
browser can read it regardless of `WindowsApps` ACLs). That folder is not
removed by `Remove-AppxPackage`; delete it by hand if you want a truly clean
uninstall:

```powershell
Remove-Item -Recurse -Force $env:LOCALAPPDATA\QNetHome
```

To also undo the trust decision:

```powershell
# elevated
Get-ChildItem Cert:\LocalMachine\Root |
    Where-Object { $_.Subject -eq 'CN=QNetHome' } | Remove-Item
```

## If you would rather not trust a root certificate

Two alternatives that avoid step 1 entirely:

- **Just run the EXE.** `dist\QNetHome\QNetHome.exe` is the same application,
  needs no install, no certificate and no elevation. The MSIX exists because the
  hackathon asks for a packaged installer, not because the app needs one.
- **Enable sideloading developer mode** (Settings → System → For developers).
  This still will not accept an untrusted *root*, so in practice step 1 is the
  shorter path.

## Notes for a real release

The package is signed but **not timestamped** (`signtool` reported "File is not
timestamped"), so the signature stops validating when the certificate expires in
2027. A shipping build would add `/tr http://timestamp.digicert.com /td SHA256`
to the `signtool sign` call in `make_msix.ps1` and use a certificate from a real
CA, at which point the trust step disappears for end users. Neither is worth
doing for a demo whose certificate is self-signed anyway.
