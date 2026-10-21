# Install SFP skills. Examples:
#   .\install.ps1                          starter set into every tool found
#   .\install.ps1 --profile everything
#   .\install.ps1 list
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$py = if (Get-Command py -ErrorAction SilentlyContinue) { @('py', '-3') } elseif (Get-Command python -ErrorAction SilentlyContinue) { @('python') } else { throw 'Python 3 is required: https://www.python.org/downloads/' }
$argv = @($args)
if ($argv.Count -eq 0 -or $argv[0].StartsWith('-')) { $argv = @('install') + $argv }
& $py[0] @($py | Select-Object -Skip 1) scripts/install.py @argv
exit $LASTEXITCODE
