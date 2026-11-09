# OpenAmika setup for Windows: her brain, her ears (speech recognition), her memory and her eyes, with their models,
# settings.json and brain\.env. Her voice and her Live2D model come next, from scripts\setup_tts.py.
#
# Run it in PowerShell from the OpenAmika folder:
#
#   powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1 --cpu           # no NVIDIA GPU
#   powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1 --vision off    # without her camera eyes
#   powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1 --check         # what is missing; changes nothing
#
# This script only finds Python 3.11 (else 3.12) and runs scripts\setup_core.py with it (every option above is passed
# through); that one does the work and ends with a summary: one OK / -- / !! line per part, each !! with its fix.
# Running it again is safe: what is already installed is checked and skipped, and downloads resume.
#
# The commands after it (scripts\setup_tts.py, Start_OpenAmika.bat) are relative to the OpenAmika folder, so the folder
# and the program this was started from are passed on: when the window is elsewhere (the outer folder of GitHub's ZIP,
# OpenAmika-main\OpenAmika-main, or C:\Windows\System32), the summary prints the exact cd line first.

$root = Split-Path -Parent $PSScriptRoot
$callerDir = (Get-Location).ProviderPath
$callerShell = ''
try {
    $me = Get-CimInstance Win32_Process -Filter "ProcessId=$PID" -ErrorAction Stop
    $parent = Get-CimInstance Win32_Process -Filter "ProcessId=$($me.ParentProcessId)" -ErrorAction Stop
    $callerShell = [string]$parent.Name
} catch {}
Set-Location -LiteralPath $root
if (-not (Test-Path -LiteralPath (Join-Path $root 'launch.py'))) {
    Write-Host '[setup] This script belongs in the scripts folder of OpenAmika; run it from there.'
    exit 1
}
$env:OPENAMIKA_CALLER_DIR = $callerDir
$env:OPENAMIKA_CALLER_SHELL = $callerShell
# "Run with PowerShell" from Explorer closes the window at the end: keep it open so the summary can be read
$fromExplorer = $callerShell -ieq 'explorer.exe'

$elevated = $false
try {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $elevated = (New-Object Security.Principal.WindowsPrincipal($identity)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
} catch {}
if ($elevated) {
    Write-Host '[setup] NOTE: this window runs as administrator. The setup works, but start her later from a normal'
    Write-Host '        window (or by double-clicking Start_OpenAmika.bat): what an administrator window starts cannot be'
    Write-Host '        stopped from a normal one.'
}

# Python 3.11 (the tested one), else 3.12 (every package has wheels for it): the py launcher first (python.org
# installs it), then python3.11 / python3.12 / python on PATH. The Microsoft Store placeholder "python" (it only
# opens the Store) prints nothing and is skipped. 3.13 and newer cannot run her voice server (numpy 1.26.4).
$python = $null
foreach ($want in @('3.11', '3.12')) {
    foreach ($candidate in @("py -$want", "python$want", 'python')) {
        $parts = $candidate -split ' '
        $exe = $parts[0]
        $pre = @($parts | Select-Object -Skip 1)
        if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) { continue }
        $version = & $exe @pre -c 'import sys; print(sys.version_info[0], sys.version_info[1])' 2>$null
        if ($LASTEXITCODE -eq 0 -and "$version".Trim() -eq ($want -replace '\.', ' ')) {
            $python = @($exe) + $pre
            break
        }
    }
    if ($python) { break }
}

if (-not $python) {
    Write-Host ''
    Write-Host '[setup] Python 3.11 was not found. OpenAmika needs Python 3.11 (64-bit; 3.12 works too):'
    Write-Host '          - from python.org: https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe'
    Write-Host '            (run it and tick "Add python.exe to PATH" on its first page, then Install Now)'
    Write-Host '          - or in this window:  winget install -e --id Python.Python.3.11'
    Write-Host '        Python 3.13 and newer do not work: her voice server needs numpy 1.26.4, which has no wheels for'
    Write-Host '        them. Another Python can stay installed next to 3.11.'
    Write-Host '        Then open a NEW PowerShell window in this folder and run this script again:'
    Write-Host ('          cd "' + $root + '"')
    Write-Host '          powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1'
    if ($fromExplorer) { Read-Host 'Press Enter to close this window' | Out-Null }
    exit 1
}

$exe = $python[0]
$pre = @($python | Select-Object -Skip 1)
Write-Host ("[setup] using " + ($python -join ' '))
& $exe @pre -X utf8 (Join-Path $root 'scripts\setup_core.py') @args
$code = $LASTEXITCODE
if ($fromExplorer) { Read-Host 'Press Enter to close this window' | Out-Null }
exit $code
