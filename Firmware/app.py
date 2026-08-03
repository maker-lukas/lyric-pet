from __future__ import annotations

import bisect
import hashlib
import hmac
import os
import secrets
import struct
import sys
import time
from dataclasses import dataclass

import requests
import spotipy
from dotenv import load_dotenv
from rich.align import Align
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.progress_bar import ProgressBar
from rich.text import Text


POLL_INTERVAL_SECONDS = 1.5
WEB_PLAYER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
_web_token: tuple[str, int] | None = None


@dataclass(frozen=True)
class LyricLine:
    start_ms: int
    words: str


@dataclass(frozen=True)
class Playback:
    track_id: str
    title: str
    artists: str
    progress_ms: int
    duration_ms: int
    is_playing: bool
    sampled_at: float

    def position_ms(self) -> int:
        elapsed = (time.monotonic() - self.sampled_at) * 1000 if self.is_playing else 0
        return min(self.duration_ms, int(self.progress_ms + elapsed))


class LyricsError(RuntimeError):
    pass


def active_line_index(lines: list[LyricLine], position_ms: int) -> int:
    return bisect.bisect_right([line.start_ms for line in lines], position_ms) - 1


def get_web_player_token(sp_dc: str) -> str:
    global _web_token
    now_ms = int(time.time() * 1000)
    if _web_token and _web_token[1] > now_ms + 60_000:
        return _web_token[0]

    server_time = requests.get("https://open.spotify.com/api/server-time", timeout=10)
    server_time.raise_for_status()
    secret_response = requests.get(
        "https://raw.githubusercontent.com/xyloflake/spot-secrets-go/main/secrets/secretDict.json",
        timeout=10,
    )
    secret_response.raise_for_status()
    secret_dict = secret_response.json()
    version = next(reversed(secret_dict))
    secret = "".join(
        str(value ^ ((index % 33) + 9))
        for index, value in enumerate(secret_dict[version])
    )

    counter = struct.pack(">Q", int(server_time.json()["serverTime"]) // 30)
    digest = hmac.new(secret.encode(), counter, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    binary = (
        ((digest[offset] & 0x7F) << 24)
        | (digest[offset + 1] << 16)
        | (digest[offset + 2] << 8)
        | digest[offset + 3]
    )

    token_response = requests.get(
        "https://open.spotify.com/api/token",
        params={
            "reason": "transport",
            "productType": "web-player",
            "totp": f"{binary % 1_000_000:06d}",
            "totpVer": version,
            "ts": str(int(time.time())),
        },
        headers={"User-Agent": WEB_PLAYER_USER_AGENT},
        cookies={"sp_dc": sp_dc},
        timeout=10,
    )
    token_response.raise_for_status()
    payload = token_response.json()
    if payload.get("isAnonymous") or not payload.get("accessToken"):
        raise LyricsError("The SP_DC cookie is invalid or expired.")

    _web_token = (
        payload["accessToken"],
        int(payload.get("accessTokenExpirationTimestampMs", now_ms + 300_000)),
    )
    return _web_token[0]


def fetch_lyrics(api_url: str, track_id: str, sp_dc: str | None = None) -> tuple[str, list[LyricLine]]:
    try:
        if sp_dc:
            access_token = get_web_player_token(sp_dc)
            response = requests.get(
                f"https://spclient.wg.spotify.com/color-lyrics/v2/track/{track_id}",
                params={"format": "json", "market": "from_token"},
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "App-platform": "WebPlayer",
                    "User-Agent": WEB_PLAYER_USER_AGENT,
                },
                timeout=10,
            )
            response.raise_for_status()
            payload = response.json().get("lyrics", {})
        else:
            response = requests.get(
                f"{api_url.rstrip('/')}/",
                params={"trackid": track_id},
                timeout=10,
            )
            payload = response.json()
    except requests.RequestException as exc:
        if getattr(exc.response, "status_code", None) == 404:
            raise LyricsError("Lyrics are unavailable for this track.") from exc
        raise LyricsError(f"Could not reach Spotify's lyrics service: {exc}") from exc
    except ValueError as exc:
        raise LyricsError("Spotify's lyrics service returned invalid JSON.") from exc

    if payload.get("error"):
        raise LyricsError(payload.get("message", "Lyrics are unavailable for this track."))
    if not response.ok:
        raise LyricsError(f"Lyrics API returned HTTP {response.status_code}.")

    try:
        lines = [
            LyricLine(int(line.get("startTimeMs", 0)), str(line.get("words", "")))
            for line in payload["lines"]
        ]
    except (KeyError, TypeError, ValueError) as exc:
        raise LyricsError("The lyrics API response has an unexpected format.") from exc

    return str(payload.get("syncType", "UNSYNCED")), lines


def get_playback(spotify: spotipy.Spotify) -> Playback | None:
    data = spotify.current_playback(additional_types="track")
    if not data or not data.get("item") or data["item"].get("type") != "track":
        return None

    item = data["item"]
    progress_ms = int(data.get("progress_ms") or 0)

    return Playback(
        track_id=item["id"],
        title=item["name"],
        artists=", ".join(artist["name"] for artist in item["artists"]),
        progress_ms=progress_ms,
        duration_ms=int(item.get("duration_ms") or 1),
        is_playing=bool(data.get("is_playing")),
        sampled_at=time.monotonic(),
    )


def format_time(milliseconds: int) -> str:
    seconds = max(0, milliseconds // 1000)
    return f"{seconds // 60}:{seconds % 60:02d}"


def render(
    playback: Playback | None,
    sync_type: str,
    lines: list[LyricLine],
    message: str | None,
    height: int,
    lyrics_delay_ms: int = 0,
) -> Panel:
    if playback is None:
        return Panel(
            Align.center("Open Spotify and play a song…", vertical="middle"),
            title="[bold green]Spotify Lyrics[/]",
            subtitle="Ctrl+C to quit",
            height=max(5, height - 1),
            border_style="green",
        )

    position = playback.position_ms()
    lyrics_position = max(0, position - lyrics_delay_ms)
    heading = Text.assemble(
        (playback.title, "bold white"),
        ("\n" + playback.artists, "dim"),
        ("  ·  " + ("Playing" if playback.is_playing else "Paused"), "green"),
    )

    if message:
        lyrics_view = Align.center(Text(message, style="yellow"), vertical="middle")
    elif sync_type != "LINE_SYNCED":
        text = Text("\n".join(line.words for line in lines), justify="center")
        lyrics_view = Align.center(text, vertical="middle")
    else:
        current = active_line_index(lines, lyrics_position)
        visible_count = max(3, height - 10)
        first = max(0, current - visible_count // 2)
        first = min(first, max(0, len(lines) - visible_count))
        lyric_text = Text(justify="center")
        for index, line in enumerate(lines[first : first + visible_count], start=first):
            style = "bold bright_green" if index == current else "dim" if index < current else "white"
            lyric_text.append((line.words or "♪") + "\n", style=style)
        lyrics_view = Align.center(lyric_text, vertical="middle")

    progress = Group(
        ProgressBar(total=playback.duration_ms, completed=position, style="grey35", complete_style="green"),
        Align.center(f"{format_time(position)} / {format_time(playback.duration_ms)}"),
    )
    return Panel(
        Group(Align.center(heading), Text(""), lyrics_view, Text(""), progress),
        title="[bold green]Spotify Lyrics[/]",
        subtitle="Ctrl+C to quit",
        height=max(8, height - 1),
        border_style="green",
        padding=(1, 2),
    )


def build_spotify_client(scope: str = "user-read-currently-playing user-read-playback-state") -> spotipy.Spotify:
    client_id = os.getenv("SPOTIPY_CLIENT_ID")
    if not client_id:
        raise RuntimeError("SPOTIPY_CLIENT_ID is missing. Copy .env.example to .env and fill it in.")

    auth = spotipy.SpotifyPKCE(
        client_id=client_id,
        redirect_uri=os.getenv("SPOTIPY_REDIRECT_URI", "http://127.0.0.1:8888/callback"),
        state=secrets.token_urlsafe(24),
        scope=scope,
        cache_path=os.getenv("SPOTIPY_CACHE_PATH", ".spotify-cache"),
        open_browser=True,
    )
    return spotipy.Spotify(auth_manager=auth, requests_timeout=10, retries=2)


def main() -> int:
    load_dotenv()
    console = Console()
    try:
        spotify = build_spotify_client()
        spotify.auth_manager.get_access_token()
    except spotipy.SpotifyOauthError as exc:
        console.print(f"[bold red]Spotify authorization failed:[/] {exc}")
        console.print("Close old Spotify authorization tabs, then run the app again.")
        return 2
    except RuntimeError as exc:
        console.print(f"[bold red]Configuration error:[/] {exc}")
        return 2

    api_url = os.getenv("LYRICS_API_URL", "http://localhost:8080")
    lyrics_delay_ms = int(os.getenv("LYRICS_DELAY_MS", "500"))
    sp_dc = os.getenv("SP_DC")
    if sp_dc == "PASTE_SP_DC_COOKIE_HERE":
        sp_dc = None
    playback: Playback | None = None
    track_id: str | None = None
    sync_type = "UNSYNCED"
    lines: list[LyricLine] = []
    message: str | None = None
    lyrics_message: str | None = None
    next_poll = 0.0

    try:
        with Live(console=console, refresh_per_second=10, screen=True) as live:
            while True:
                if time.monotonic() >= next_poll:
                    try:
                        playback = get_playback(spotify)
                        message = None
                        if playback and playback.track_id != track_id:
                            track_id = playback.track_id
                            lyrics_message = None
                            try:
                                sync_type, lines = fetch_lyrics(api_url, track_id, sp_dc)
                                if not lines:
                                    lyrics_message = "No lyrics were returned for this track."
                            except LyricsError as exc:
                                lines = []
                                lyrics_message = str(exc)
                        elif playback is None:
                            track_id = None
                            lines = []
                            lyrics_message = None
                    except spotipy.SpotifyException as exc:
                        message = f"Spotify error: {exc.msg or exc}"
                    except requests.RequestException as exc:
                        message = f"Spotify connection error: {exc}"
                    next_poll = time.monotonic() + POLL_INTERVAL_SECONDS

                live.update(
                    render(
                        playback,
                        sync_type,
                        lines,
                        message or lyrics_message,
                        console.height,
                        lyrics_delay_ms,
                    )
                )
                time.sleep(0.1)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
