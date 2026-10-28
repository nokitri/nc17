# Installs NC17 Assistant for Ableton Live 12 on Windows and registers it with
# Claude Code and/or Codex if their CLIs are installed.
# Run:  powershell -ExecutionPolicy Bypass -File install\install-windows.ps1
$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent $PSScriptRoot
$Scripts = if ($env:NC17_REMOTE_SCRIPTS) { $env:NC17_REMOTE_SCRIPTS } else {
    Join-Path ([Environment]::GetFolderPath("MyDocuments")) "Ableton\User Library\Remote Scripts" }
$Venv = Join-Path $env:USERPROFILE ".nc17-ableton"

Write-Host "-> Remote Script -> $Scripts\NC17Assistant"
New-Item -ItemType Directory -Force -Path $Scripts | Out-Null
$Target = Join-Path $Scripts "NC17Assistant"
if (Test-Path $Target) { Remove-Item -Recurse -Force $Target }
Copy-Item -Recurse (Join-Path $Here "remote_script\NC17Assistant") $Scripts

Write-Host "-> MCP server -> $Venv"
$Py = Get-Command py -ErrorAction SilentlyContinue
if ($Py) { & py -3 -m venv $Venv } else {
    $Py = Get-Command python -ErrorAction SilentlyContinue
    if (-not $Py) { throw "Python 3.10+ is required: https://www.python.org/downloads/" }
    & python -m venv $Venv }
& "$Venv\Scripts\python.exe" -m pip install -q --upgrade pip
& "$Venv\Scripts\python.exe" -m pip install -q (Join-Path $Here "mcp_server")
$Bin = Join-Path $Venv "Scripts\nc17-ableton.exe"

if (Get-Command claude -ErrorAction SilentlyContinue) {
    claude mcp remove nc17-ableton -s user 2>$null | Out-Null
    claude mcp add nc17-ableton -s user -- $Bin; Write-Host "-> Registered with Claude Code" }
if (Get-Command codex -ErrorAction SilentlyContinue) {
    codex mcp remove nc17-ableton 2>$null | Out-Null
    codex mcp add nc17-ableton -- $Bin; Write-Host "-> Registered with Codex" }

Write-Host ""
Write-Host "Done. In Live 12: Options > Settings > Link, Tempo & MIDI > Control Surface -> NC17Assistant"
Write-Host "(restart Live if it is not listed). MCP server command: $Bin"
