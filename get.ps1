# SFP bootstrap for Windows PowerShell. Clones (or updates) SFP into ~\.sfp\SFP and runs the installer.
#   irm https://raw.githubusercontent.com/siddu1004/SFP/main/get.ps1 | iex
#   & ([scriptblock]::Create((irm https://raw.githubusercontent.com/siddu1004/SFP/main/get.ps1))) --profile frontend-dev --tools cursor
# Set $env:SFP_DIR to use another folder.
$ErrorActionPreference = 'Stop'
$dir = if ($env:SFP_DIR) { $env:SFP_DIR } else { Join-Path $HOME '.sfp\SFP' }
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw 'git is required: https://git-scm.com/downloads' }
if (Test-Path (Join-Path $dir '.git')) {
  git -C $dir pull -q --ff-only
} else {
  New-Item -ItemType Directory -Force -Path (Split-Path $dir) | Out-Null
  git clone -q --depth 1 https://github.com/siddu1004/SFP.git $dir
}
& (Join-Path $dir 'install.ps1') @args
exit $LASTEXITCODE
