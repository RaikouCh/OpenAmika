@echo off
rem OPTIONAL, only for her smart home (Zigbee plugs): talking to her, her voice and her setup never need this.
rem Smart-home setup that needs administrator rights (Windows asks for permission):
rem   Install_CP210x_driver.ps1  - driver for the SONOFF Zigbee Dongle Plus MG24 (gives it a COM port):
rem                                tries Windows Update, then a CP210x*Driver*.zip from your Downloads or this folder
rem                                (silabs.com only serves browsers: get CP210x_Universal_Windows_Driver.zip there).
rem   Setup_IoT_admin.ps1        - Eclipse Mosquitto (MQTT broker) via winget (only when it is missing).
rem Afterwards run Start_OpenAmika.bat again and turn IoT on from the Tools page: it shows the IoT safety
rem statement (docs\IOT_DISCLAIMER.md) first, and once you accept it the launcher finds the COM port,
rem starts the broker and zigbee2mqtt, and your Zigbee devices appear on the Tools page / in Amika's hands.
if not exist "C:\Program Files\mosquitto\mosquitto.exe" (
    powershell -NoProfile -Command "Start-Process powershell -Verb RunAs -Wait -ArgumentList '-NoProfile -ExecutionPolicy Bypass -File \"%~dp0Setup_IoT_admin.ps1\"'"
)
powershell -NoProfile -Command "Start-Process powershell -Verb RunAs -Wait -ArgumentList '-NoProfile -ExecutionPolicy Bypass -File \"%~dp0Install_CP210x_driver.ps1\"'"
