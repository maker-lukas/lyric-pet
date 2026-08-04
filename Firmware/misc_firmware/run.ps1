$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

if (-not (Test-Path ".env")) {
    throw "Missing .env. Copy .env.example to .env and fill in your Spotify values."
}

Get-Content ".env" | ForEach-Object {
    if ($_ -match '^\s*([^#][^=]*)=(.*)$') {
        Set-Item -Path "Env:$($matches[1].Trim())" -Value $matches[2].Trim()
    }
}

if (-not $env:SPOTIPY_CLIENT_ID -or $env:SPOTIPY_CLIENT_ID -eq "PASTE_CLIENT_ID_HERE") {
    throw "Open .env and replace PASTE_CLIENT_ID_HERE with your Spotify app client ID."
}
if (-not $env:SP_DC -or $env:SP_DC -eq "PASTE_SP_DC_COOKIE_HERE") {
    throw "Open .env and replace PASTE_SP_DC_COOKIE_HERE with your Spotify sp_dc cookie."
}

& ".\.venv\Scripts\python.exe" app.py
