# Spotify Lyrics Terminal

A small terminal app that detects the song currently playing on Spotify and
highlights line-synced lyrics at the correct playback position.

## Setup

You need a Spotify account and a Spotify developer app. Lyrics are fetched from
the same Spotify backend used by
[akashrchandran/spotify-lyrics-api](https://github.com/akashrchandran/spotify-lyrics-api),
without requiring Docker or a separate server.

### 1. Get the lyrics cookie

Find your Spotify `sp_dc` cookie using the
[upstream guide](https://github.com/akashrchandran/syrics/wiki/Finding-sp_dc),
then put it in `.env` as `SP_DC`.

Keep this cookie private. The upstream project warns that it may be against
Spotify's terms of service, so use it at your own risk.

### 2. Configure Spotify playback access

1. Create an app at the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard).
2. Add `http://127.0.0.1:8888/callback` as a redirect URI in the app settings.
3. Copy `.env.example` to `.env` and replace `your_spotify_app_client_id`.

The app uses PKCE authentication, so it does not need your client secret.

### 3. Install and run

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
./run.ps1
```

Your browser opens for Spotify authorization on the first run. Start playing a
song in Spotify; the terminal updates automatically. Press `Ctrl+C` to exit.

If `SP_DC` is omitted, the app can instead use a self-hosted API configured by
`LYRICS_API_URL`.

If lyric highlighting is early or late, adjust `LYRICS_DELAY_MS` in `.env`.
Higher values make lyrics appear later; `1000` equals one second.

## XIAO RP2040 device version

The original TUI remains available through `run.ps1`. The hardware host is a
separate program and can be started after flashing the firmware:

```powershell
powershell -ExecutionPolicy Bypass -File .\run-device.ps1
```

On Linux, install `python-gobject` and run the MPRIS host instead. It reads and
controls the local Spotify client through D-Bus, so Spotify Premium and a
developer client ID are not required:

```bash
./run-device-linux.sh
```

The `SP_DC` cookie in `.env` is still required for the lyrics source.

The device host shows only the active lyric segment. Long lines are divided
into balanced, screen-sized segments and timed proportionally by text length.
Touching the TTP223 toggles Spotify playback. See
[`firmware/README.md`](firmware/README.md) for the exact wiring and flashing
steps.

An experimental one-word-at-a-time mode is also available:

```powershell
powershell -ExecutionPolicy Bypass -File .\run-device-word.ps1
```

Spotify normally supplies line-level rather than word-level timestamps, so
this mode estimates word timing from word length and punctuation.

For a less cramped and more timing-tolerant display, short-phrase mode shows
2–4 words in at most two OLED rows and estimates timing from syllables:

```powershell
powershell -ExecutionPolicy Bypass -File .\run-device-phrase.ps1
```

## Tests

```powershell
python -m unittest -v
```
