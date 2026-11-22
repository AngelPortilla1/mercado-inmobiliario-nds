# Script de Ejecución Semanal — Mercado Inmobiliario en Norte de Santander (NSInmobilario)
# Uso manual:
#   powershell -ExecutionPolicy Bypass -File .\scripts\run_weekly_capture.ps1
#
# Para registrar como tarea semanal automática en el Programador de Tareas de Windows (todos los domingos a las 08:00 AM):
#   $Action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$PWD\scripts\run_weekly_capture.ps1`"" -WorkingDirectory "$PWD"
#   $Trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At 8am
#   Register-ScheduledTask -TaskName "NSInmobiliario_CapturaSemanal" -Action $Action -Trigger $Trigger -Description "Captura semanal ética de avisos inmobiliarios en Norte de Santander"

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

Write-Host "=== [NSInmobilario] Iniciando captura semanal ($(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')) ===" -ForegroundColor Cyan
uv run python -m src.pipeline --scrape
Write-Host "=== [NSInmobilario] Captura semanal finalizada con éxito ===" -ForegroundColor Green
