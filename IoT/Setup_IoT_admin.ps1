# OpenAmika smart home — the install that needs administrator rights, done once: Eclipse Mosquitto, the MQTT
# broker zigbee2mqtt and OpenAmika's smart-home server talk through (winget). The Silicon Labs CP210x USB-UART
# driver (the SONOFF Zigbee Dongle Plus MG24 is a CP2102N; without it Windows shows the dongle with "code 28" and no
# COM port) is installed by Install_CP210x_driver.ps1; Setup_IoT_admin.bat runs both. Everything else (zigbee2mqtt,
# the OpenAmika IoT server, configuration) needs no elevation and is set up by the OpenAmika launcher / this folder.
# Run from an elevated PowerShell:
#   powershell -ExecutionPolicy Bypass -File Setup_IoT_admin.ps1
$ErrorActionPreference = 'Continue'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$log = Join-Path $here 'setup_admin.log'
Start-Transcript -Path $log -Force | Out-Null
Write-Host "OpenAmika smart home — administrator setup" -ForegroundColor Cyan

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) { Write-Host "This script must run as administrator." -ForegroundColor Red; Stop-Transcript | Out-Null; Read-Host "Press Enter to close"; exit 1 }

# ── 1. CP210x driver: a status line only ─────────────────────────────────────────────────
# The driver itself is installed by Install_CP210x_driver.ps1 (Windows Update first, then a zip you downloaded in a
# browser), which Setup_IoT_admin.bat runs after this script. This script downloads nothing: silabs.com serves
# browsers only (a script gets HTTP 403), and a "download a zip, then install a driver" step is what antivirus
# heuristics flag (Windows Defender called the repository ZIP Trojan:Script/Sabsik on 2026-11-05).
$havePort = Get-CimInstance Win32_SerialPort -EA SilentlyContinue | Where-Object { $_.PNPDeviceID -like 'USB\VID_10C4&PID_EA60*' }
$dongle = Get-PnpDevice -PresentOnly -EA SilentlyContinue | Where-Object { $_.InstanceId -like 'USB\VID_10C4&PID_EA60*' }
if ($havePort) { Write-Host ("[ok] CP210x driver already working: {0}" -f $havePort.DeviceID) -ForegroundColor Green }
elseif ($dongle) { Write-Host "[..] Zigbee dongle found, no COM port yet: Install_CP210x_driver.ps1 runs next and installs the driver." -ForegroundColor Yellow }
else { Write-Host "[--] No Zigbee dongle plugged in (fine: plug it in later and run Setup_IoT_admin.bat again for the driver)." }

# ── 2. Mosquitto ───────────────────────────────────────────────────────────────────────────
$mosq = 'C:\Program Files\mosquitto\mosquitto.exe'
if (Test-Path $mosq) {
    Write-Host "[ok] Mosquitto already installed" -ForegroundColor Green
} else {
    Write-Host "[..] Installing Eclipse Mosquitto with winget…"
    & winget install --id EclipseFoundation.Mosquitto -e --silent --accept-package-agreements --accept-source-agreements --disable-interactivity
    if (Test-Path $mosq) { Write-Host "[ok] Mosquitto installed" -ForegroundColor Green }
    else { Write-Host "[!!] Mosquitto not found after install — get it from https://mosquitto.org/download/" -ForegroundColor Red }
}
# The installer registers a Windows service that may take port 1883 with its own config; OpenAmika's launcher runs
# mosquitto itself (IoT\mosquitto.conf, local only). Leave the service off so the two don't fight over the port.
$svc = Get-Service -Name mosquitto -EA SilentlyContinue
if ($svc) {
    if ($svc.Status -ne 'Stopped') { Stop-Service mosquitto -Force -EA SilentlyContinue }
    Set-Service mosquitto -StartupType Manual -EA SilentlyContinue
    Write-Host "[ok] mosquitto Windows service set to manual (the OpenAmika launcher starts the broker)" -ForegroundColor Green
}

Write-Host ""
Write-Host "Done. Back in OpenAmika: run Start_OpenAmika.bat, then turn IoT on from the Tools page. It shows the IoT safety statement (docs\IOT_DISCLAIMER.md) first; once you accept it, the launcher finds the COM port, starts the broker and zigbee2mqtt, and your Zigbee devices should appear." -ForegroundColor Cyan
Stop-Transcript | Out-Null
Read-Host "Press Enter to close"
