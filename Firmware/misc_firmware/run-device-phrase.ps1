$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$env:LYRICS_DELAY_MS = "0"
& ".\.venv\Scripts\python.exe" device_host_phrase.py
