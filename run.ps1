# Easy launcher for Woolworths Meal Agent (double-click or run from PowerShell)
$Python = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
$Scripts = "$env:LOCALAPPDATA\Programs\Python\Python312\Scripts"
$Project = Split-Path -Parent $MyInvocation.MyCommand.Path

$env:Path += ";$Scripts"
Set-Location $Project

& $Python -m meal_agent_cli.main @args
