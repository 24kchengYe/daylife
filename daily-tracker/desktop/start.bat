@echo off
cd /d "%~dp0"
start "" "node_modules\electron\dist\DayLife.exe" "%~dp0" --app-user-model-id=com.DayLife.dev
