# Stops only this folder's OpenAmika processes:
#   1. whatever the launcher recorded in logs\instance.json: the launcher itself and the services it started (TTS,
#      the MQTT broker, zigbee2mqtt, Hermes, nanoMuse - matched by pid AND executable path, so a reused pid is never hit);
#   2. the core components, by script path on the command line (launcher, brain, speech, embedder, vision, messengers,
#      her desktop pet window);
#   3. a launcher started with a relative "launch.py" by this folder's brain python (settings.json brain_python).
# Never by port or window title, so other python processes and other OpenAmika checkouts are untouched.
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$stopped = 0
# taskkill /T lists the whole tree before it kills it. A venv's python.exe takes its interpreter along when it dies, so
# some of those children are gone by their turn ("There is no running instance of the task"): that is not shown.
# Any other refusal (for one, "Access is denied" for a process started from an administrator window) is.
function Stop-Tree([int]$procId) {
    # its SUCCESS lines (standard output) are dropped as before; its refusals come on standard error
    $refusals = @(& taskkill /PID $procId /T /F 2>&1 | Where-Object { $_ -is [System.Management.Automation.ErrorRecord] } |
                  ForEach-Object { "$_".Trim() } | Where-Object { $_ })
    for ($i = 0; $i -lt $refusals.Count; $i++) {
        $text = $refusals[$i]
        if ($i + 1 -lt $refusals.Count -and $refusals[$i + 1] -like 'Reason:*') {
            $i++
            $text = "$text $($refusals[$i])"
        }
        if ($text -notlike '*no running instance*') { Write-Host "  $text" }
    }
}
$settings = $null
try { $settings = Get-Content (Join-Path $root 'settings.json') -Raw | ConvertFrom-Json } catch {}
$instance = Join-Path $root 'logs\instance.json'
if (Test-Path $instance) {
    try { $record = Get-Content $instance -Raw | ConvertFrom-Json } catch { $record = $null }
    # the launcher itself, whatever its command line looks like (its console may have run a relative "launch.py")
    if ($record -and $record.launcher_pid) {
        $live = Get-CimInstance Win32_Process -Filter "ProcessId=$($record.launcher_pid)" -ErrorAction SilentlyContinue
        if ($live -and $live.Name -like 'python*' -and $live.CommandLine -and $live.CommandLine.ToLower().Contains('launch.py')) {
            Write-Host ("Stopping PID {0}: launcher" -f $record.launcher_pid)
            Stop-Tree $record.launcher_pid
            $stopped++
        }
    }
    foreach ($entry in @($record.processes)) {
        if (-not $entry -or -not $entry.pid) { continue }
        $live = Get-CimInstance Win32_Process -Filter "ProcessId=$($entry.pid)" -ErrorAction SilentlyContinue
        if (-not $live) { continue }
        $exe = [string]$entry.exe
        $match = ($live.ExecutablePath -and $exe -and ($live.ExecutablePath.ToLower() -eq $exe.ToLower())) -or
                 ($live.CommandLine -and $exe -and $live.CommandLine.ToLower().Contains($exe.ToLower()))
        if ($match) {
            Write-Host ("Stopping PID {0}: {1}" -f $entry.pid, $entry.name)
            Stop-Tree $entry.pid
            $stopped++
        }
    }
    Remove-Item $instance -ErrorAction SilentlyContinue
}
$targets = @(
    (Join-Path $root 'launch.py'),
    (Join-Path $root 'brain\webui.py'),
    (Join-Path $root 'speech\api.py'),
    (Join-Path $root 'brain\embed_server.py'),
    (Join-Path $root 'vision\vlm_service.py'),
    (Join-Path $root 'messengers\service.py'),
    (Join-Path $root 'pet.py')
)
# this folder's brain python, which runs its launcher (Start_OpenAmika.bat passes launch.py by its full path; a console
# may have run "envs\brain\Scripts\python.exe launch.py" instead)
$brainPy = $null
if ($settings -and $settings.brain_python) {
    $p = [string]$settings.brain_python
    if (-not [System.IO.Path]::IsPathRooted($p)) { $p = Join-Path $root $p }
    try { $brainPy = [System.IO.Path]::GetFullPath($p).ToLower() } catch {}
}
$ownLauncher = (Join-Path $root 'launch.py').ToLower()
Get-CimInstance Win32_Process -Filter "Name LIKE 'python%'" | ForEach-Object {
    $cl = $_.CommandLine
    if (-not $cl) { return }
    $lower = $cl.ToLower()
    $hit = $null
    foreach ($t in $targets) {
        if ($lower.Contains($t.ToLower())) { $hit = $t; break }
    }
    $tree = $false
    if (-not $hit -and $brainPy -and $_.ExecutablePath -and $_.ExecutablePath.ToLower() -eq $brainPy -and $lower.Contains('launch.py')) {
        # a launcher run by this folder's brain python; one that names another folder's launch.py is left alone
        $named = @([regex]::Matches($cl, '(?i)"([a-z]:\\[^"]*?launch\.py)"|([a-z]:\\[^"\s]*?launch\.py)') |
                   ForEach-Object { ($_.Groups[1].Value + $_.Groups[2].Value).ToLower() })
        if ($named.Count -eq 0 -or ($named -contains $ownLauncher)) { $hit = 'launch.py (started from this folder)'; $tree = $true }
    }
    if ($hit) {
        Write-Host ("Stopping PID {0}: {1}" -f $_.ProcessId, $hit)
        if ($tree) {
            Stop-Tree $_.ProcessId
            $script:stopped++
        } else {
            try { Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop; $script:stopped++ } catch {
                Write-Host ("  could not stop PID {0}: {1}" -f $_.ProcessId, $_.Exception.Message)
            }
        }
    }
}
Write-Host ("OpenAmika stop complete. Processes stopped: {0}" -f $stopped)
# A component started from an administrator window is invisible to a normal shell (its command line cannot be read),
# so it survives the matching above. If one of this folder's ports is still held by python.exe, say whose it is.
try {
    Start-Sleep -Seconds 2      # let the stopped processes release their ports before looking
    $ports = @()
    if ($settings.messengers_port) { $ports += [int]$settings.messengers_port } else { $ports += 5215 }
    if ($settings.brain_port) { $ports += [int]$settings.brain_port } else { $ports += 5202 }
    if ($settings.chat_port) { $ports += [int]$settings.chat_port } else { $ports += 53000 }
    if ($settings.embedder -and $settings.embedder.port) { $ports += [int]$settings.embedder.port }
    if ($settings.vision -and $settings.vision.port -and $settings.vision.enabled -ne $false) { $ports += [int]$settings.vision.port }
    $holders = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $ports -contains $_.LocalPort } |
        Select-Object LocalPort, OwningProcess -Unique
    foreach ($h in @($holders)) {
        $p = Get-CimInstance Win32_Process -Filter "ProcessId=$($h.OwningProcess)" -ErrorAction SilentlyContinue
        if (-not $p -or $p.Name -notlike 'python*') { continue }
        if (-not $p.CommandLine) {
            Write-Host ("Still running: python pid {0} holds port {1} and was started from an administrator window. " -f $h.OwningProcess, $h.LocalPort) -NoNewline
            Write-Host "Run Stop_OpenAmika.bat as administrator (right-click) or close that window."
        } elseif ($p.CommandLine.ToLower().Contains($root.ToLower())) {
            Write-Host ("Still running: python pid {0} of this OpenAmika holds port {1}; it could not be stopped (see above)." -f $h.OwningProcess, $h.LocalPort)
        } else {
            Write-Host ("Port {0} is held by python pid {1}, which is not this folder's OpenAmika (another program or another OpenAmika folder): left alone." -f $h.LocalPort, $h.OwningProcess)
        }
    }
} catch {}
