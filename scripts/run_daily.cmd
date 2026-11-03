@echo off
rem Called every hour by Windows Task Scheduler (see: autopost-kit schedule).
rem autopost.yaml decides what runs and when; this script only starts it.
cd /d "%~dp0.."
if not exist output\logs mkdir output\logs
echo ==== %date% %time% ==== >> output\logs\run.log
".venv\Scripts\autopost-kit.exe" -v run >> output\logs\run.log 2>&1
