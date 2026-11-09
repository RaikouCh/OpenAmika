# Updates OpenAmika in place and keeps her memory. Update_OpenAmika.bat runs it (double-click that file).
#
#   1. Refuses while she is running from this folder (her launcher, brain, speech, embedder, vision or messengers):
#      stop her first (Stop_OpenAmika.bat, or Ctrl+C in her window).
#   2. Backs up her memory and your settings into backups\update-<yyyyMMdd-HHmm>.zip:
#        memory_f\, brain\memories\, settings.json, brain\.env, config\seed.json, config\ollama.json,
#        config\voice_map.json, config\tools.json, config\messengers.json, and the tracked files the pages change
#        (config\build_f.json, config\word_replace.json, config\llm_roles.json, brain\*.txt, brain\scenes.json).
#   3. git stash, git pull --ff-only, git stash pop. Her memory and your settings are git-ignored, so the pull never
#      touches them. A file you edited that the update changed too (her persona, most often) keeps your version; the
#      update's version of a persona file is in brain\defaults\.
#   4. Checks her setup (scripts\setup_windows.ps1 --check, scripts\setup_tts.py --verify) and runs the setup
#      when something changed (it installs only what is new).
# A folder that is not a git clone (the ZIP) gets the ZIP steps of README.md instead.

$root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $root
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}

function Say([string]$text) { Write-Host $text }

Say "OpenAmika update - $root"

# ---- 1. not while she runs ----------------------------------------------------------------------------------------
$targets = @('launch.py', 'brain\webui.py', 'speech\api.py', 'brain\embed_server.py', 'vision\vlm_service.py',
             'messengers\service.py') | ForEach-Object { (Join-Path $root $_).ToLower() }
$running = @()
try {
    Get-CimInstance Win32_Process -Filter "Name LIKE 'python%'" -ErrorAction Stop | ForEach-Object {
        $cl = [string]$_.CommandLine
        if (-not $cl) { return }
        $lower = $cl.ToLower()
        foreach ($t in $targets) { if ($lower.Contains($t)) { $running += $_.ProcessId; break } }
    }
} catch {}
$instance = Join-Path $root 'logs\instance.json'
if (Test-Path -LiteralPath $instance) {
    try {
        $record = Get-Content -LiteralPath $instance -Raw | ConvertFrom-Json
        if ($record.launcher_pid) {
            $live = Get-CimInstance Win32_Process -Filter "ProcessId=$($record.launcher_pid)" -ErrorAction SilentlyContinue
            if ($live -and $live.Name -like 'python*' -and ([string]$live.CommandLine).ToLower().Contains('launch.py')) {
                $running += $record.launcher_pid
            }
        }
    } catch {}
}
if ($running.Count -gt 0) {
    Say ''
    Say 'She is running. Stop her first: double-click Stop_OpenAmika.bat (or press Ctrl+C in her window),'
    Say 'then double-click Update_OpenAmika.bat again. Nothing was changed.'
    exit 1
}

# ---- 2. back up her memory and your settings ------------------------------------------------------------------------
$stamp = Get-Date -Format 'yyyyMMdd-HHmm'
$backupDir = Join-Path $root 'backups'
$zipPath = Join-Path $backupDir "update-$stamp.zip"
$items = @('memory_f', 'brain\memories', 'settings.json', 'brain\.env', 'config\seed.json', 'config\ollama.json',
           'config\voice_map.json', 'config\tools.json', 'config\messengers.json', 'config\build_f.json',
           'config\word_replace.json', 'config\llm_roles.json', 'brain\scenes.json')
$files = New-Object System.Collections.Generic.List[string]
foreach ($rel in $items) {
    $full = Join-Path $root $rel
    if (Test-Path -LiteralPath $full -PathType Container) {
        Get-ChildItem -LiteralPath $full -Recurse -File -Force | ForEach-Object { $files.Add($_.FullName) }
    } elseif (Test-Path -LiteralPath $full -PathType Leaf) {
        $files.Add($full)
    }
}
Get-ChildItem -LiteralPath (Join-Path $root 'brain') -Filter '*.txt' -File -ErrorAction SilentlyContinue |
    ForEach-Object { $files.Add($_.FullName) }
try {
    New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
    Add-Type -AssemblyName System.IO.Compression
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = [System.IO.Compression.ZipFile]::Open($zipPath, 'Create')
    try {
        foreach ($file in $files) {
            $entry = $file.Substring($root.Length).TrimStart('\') -replace '\\', '/'
            [void][System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip, $file, $entry)
        }
    } finally { $zip.Dispose() }
    Say "Backed up her memory and your settings ($($files.Count) files): $zipPath"
} catch {
    Say "Could not write the backup ($($_.Exception.Message)). Nothing was changed."
    Say 'Free some disk space, or copy the memory_f and brain\memories folders somewhere safe by hand, then try again.'
    exit 1
}

# ---- 3. the update itself -----------------------------------------------------------------------------------------
$isClone = $false
if (Get-Command git -ErrorAction SilentlyContinue) {
    $top = & git -C $root rev-parse --show-toplevel 2>$null
    if ($LASTEXITCODE -eq 0 -and $top) {
        try { $isClone = ([System.IO.Path]::GetFullPath([string]$top) -ieq [System.IO.Path]::GetFullPath($root)) } catch {}
    }
}
if (-not $isClone) {
    Say ''
    Say 'This folder is not a git clone (it came from a ZIP, or Git is not installed), so it cannot update itself.'
    Say 'Her memory is safe in the backup above. To update a ZIP folder (README.md, "Updating her", the ZIP path):'
    Say '  1. Download and unzip the new ZIP next to this folder.'
    Say '  2. Copy these from this folder into the new one: memory_f, brain\memories, settings.json, brain\.env,'
    Say '     config\seed.json, config\ollama.json, config\voice_map.json, config\tools.json, config\messengers.json'
    Say '  3. In the new folder, run the two setup lines again, then Start_OpenAmika.bat.'
    exit 2
}

$dirty = & git -C $root status --porcelain --untracked-files=no
$stashed = $false
if ($dirty) {
    & git -C $root stash push -m "OpenAmika update $stamp" | Out-Host
    if ($LASTEXITCODE -ne 0) {
        Say 'git could not put your own changes aside (git stash). Nothing was updated; her memory is in the backup.'
        exit 1
    }
    $stashed = $true
}
& git -C $root pull --ff-only | Out-Host
$pulled = ($LASTEXITCODE -eq 0)
if ($stashed) {
    & git -C $root stash pop | Out-Host
    if ($LASTEXITCODE -ne 0) {
        $conflicts = @(& git -c core.quotepath=false -C $root diff --name-only --diff-filter=U)
        if ($conflicts.Count -gt 0) {
            # keep the person's version of every file both sides changed; theirs = the stash (the person's edits)
            & git -C $root checkout --theirs -- . 2>$null
            & git -C $root reset -q 2>$null
            Say ''
            Say 'These files had your own changes and the update changed them too. Your version is kept:'
            foreach ($f in $conflicts) { Say "  $f" }
            Say 'The update''s version of a persona file is in brain\defaults\ (Setup -> Personality can reset to it).'
            Say "Her memory is safe, and also in $zipPath. Your changes stay in git's stash list as well (git stash list)."
        } else {
            Say 'git could not put your own changes back (git stash pop). They are in git stash list; her memory is in the backup.'
        }
    }
}
if (-not $pulled) {
    Say ''
    Say 'git pull did not work (no internet, or this folder has changes git cannot merge). Nothing was updated.'
    Say "Her memory is safe, and also in $zipPath."
    exit 1
}

# ---- 4. install what changed ----------------------------------------------------------------------------------------
Say ''
Say 'Checking her setup...'
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root 'scripts\setup_windows.ps1') --check | Out-Host
if ($LASTEXITCODE -ne 0) {
    Say 'The update needs new parts: running the setup now (it skips everything that is in place).'
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root 'scripts\setup_windows.ps1') | Out-Host
}
$py = Join-Path $root 'envs\brain\Scripts\python.exe'
try {
    $settings = Get-Content -LiteralPath (Join-Path $root 'settings.json') -Raw | ConvertFrom-Json
    if ($settings.brain_python) {
        $p = [string]$settings.brain_python
        if (-not [System.IO.Path]::IsPathRooted($p)) { $p = Join-Path $root $p }
        $py = $p
    }
} catch {}
if (Test-Path -LiteralPath $py) {
    & $py -X utf8 (Join-Path $root 'scripts\setup_tts.py') --verify | Out-Host
    if ($LASTEXITCODE -ne 0) {
        Say 'Her voice or her model needs new files: running scripts\setup_tts.py (type yes if it asks).'
        & $py -X utf8 (Join-Path $root 'scripts\setup_tts.py') | Out-Host
    }
}
Say ''
Say "Updated. Start her: double-click Start_OpenAmika.bat. Her memory backup: $zipPath"
exit 0
