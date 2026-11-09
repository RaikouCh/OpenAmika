@echo off
rem Updates OpenAmika and keeps her memory: a backup zip of memory_f, brain\memories and your settings goes into
rem backups\ first, then git pulls the update and the setup installs what changed (scripts\update_openamika.ps1).
rem Stop her first (Stop_OpenAmika.bat). A ZIP folder (not a git clone) gets the steps to update it by hand.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\update_openamika.ps1" %*
pause
