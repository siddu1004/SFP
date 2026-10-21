# Install the combined skills. Run `.\install.ps1 list` to see bundles and tools.
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if ($args.Count -eq 0) { $argv = @('install') } else { $argv = $args }
$py = if (Get-Command py -ErrorAction SilentlyContinue) { @('py', '-3') } elseif (Get-Command python -ErrorAction SilentlyContinue) { @('python') } else { throw 'Python 3 is required: https://www.python.org/downloads/' }
& $py[0] @($py | Select-Object -Skip 1) scripts/install.py @argv
exit $LASTEXITCODE
