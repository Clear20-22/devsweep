<#
.SYNOPSIS
    devsweep launcher for Windows PowerShell
#>
[CmdletBinding()]
param(
    [Parameter(Position=0, ValueFromRemainingArguments=$true)]
    [string[]]$ArgsList
)

$RootDir = $PSScriptRoot
$VenvPython = Join-Path $RootDir ".venv\Scripts\python.exe"
$VenvPip = Join-Path $RootDir ".venv\Scripts\pip.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Host "`n  🧹 devsweep: Initialising virtual environment..." -ForegroundColor Cyan
    $py = Get-Command python, py -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $py) {
        Write-Error "Python 3.8 or newer is required but was not found. Please install Python from https://python.org"
        exit 1
    }
    & $py.Source -m venv (Join-Path $RootDir ".venv")
    if (Test-Path (Join-Path $RootDir "requirements.txt")) {
        & $VenvPip install -r (Join-Path $RootDir "requirements.txt") --quiet
    } else {
        & $VenvPip install "rich>=13.0.0" --quiet
    }
    Write-Host "  ✔ Setup complete!`n" -ForegroundColor Green
}

$first = if ($ArgsList.Count -gt 0) { $ArgsList[0] } else { "" }
$second = if ($ArgsList.Count -gt 1) { $ArgsList[1] } else { "" }

switch ($first) {
    "help" {
        & $VenvPython (Join-Path $RootDir "devsweep.py") --help
    }
    "scan" {
        & $VenvPython (Join-Path $RootDir "devsweep.py") --skip-projects
    }
    "full" {
        if ($second) {
            & $VenvPython (Join-Path $RootDir "devsweep.py") --scan-projects $second
        } else {
            & $VenvPython (Join-Path $RootDir "devsweep.py")
        }
    }
    "report" {
        $outFile = if ($second) { $second } else { "audit-report.md" }
        & $VenvPython (Join-Path $RootDir "devsweep.py") --markdown $outFile --redact
    }
    "json" {
        $outFile = if ($second) { $second } else { "audit-report.json" }
        & $VenvPython (Join-Path $RootDir "devsweep.py") --json $outFile --redact
    }
    "script" {
        $outFile = if ($second) { $second } else { "cleanup.ps1" }
        & $VenvPython (Join-Path $RootDir "devsweep.py") --generate-script $outFile
    }
    "clean" {
        $outFile = Join-Path $RootDir "cleanup.ps1"
        & $VenvPython (Join-Path $RootDir "devsweep.py") --generate-script $outFile
        if (Test-Path $outFile) {
            & powershell -ExecutionPolicy Bypass -File $outFile
        }
    }
    default {
        if ($ArgsList.Count -eq 0) {
            & $VenvPython (Join-Path $RootDir "devsweep.py")
        } else {
            & $VenvPython (Join-Path $RootDir "devsweep.py") @ArgsList
        }
    }
}
