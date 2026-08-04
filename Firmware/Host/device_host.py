from __future__ import annotations

import bisect
import math
import os
import time
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

import serial
from dotenv import load_dotenv
from serial.tools import list_ports
from spotipy.exceptions import SpotifyException

from app import LyricsError, Playback, build_spotify_client, fetch_lyrics, get_playback


DISPLAY_COLUMNS = 10
DISPLAY_ROWS = 4
POLL_INTERVAL_SECONDS = 1.5
SPOTIFY_SCOPE = (
    "user-read-currently-playing user-read-playback-state "
    "user-modify-playback-state"
)


@dataclass(frozen=True)
class TimedSegment:
    start_ms: int
    text: str


def wrapped_rows(text: str, columns: int = DISPLAY_COLUMNS) -> int:
    rows = 1
    width = 0
    for word in text.split():
        word_width = len(word)
        if width and width + 1 + word_width <= columns:
            width += 1 + word_width
        elif width:
            rows += max(1, math.ceil(word_width / columns))
            width = word_width % columns or columns
        else:
            rows += max(0, math.ceil(word_width / columns) - 1)
            width = word_width % columns or columns
    return rows


def split_for_display(text: str) -> list[str]:
    words = text.split()
    if not words:
        return [""]

    @lru_cache(maxsize=None)
    def fits(start: int, end: int) -> bool:
        return wrapped_rows(" ".join(words[start:end])) <= DISPLAY_ROWS

    minimum = [len(words) + 1] * (len(words) + 1)
    minimum[-1] = 0
    for start in range(len(words) - 1, -1, -1):
        for end in range(start + 1, len(words) + 1):
            if fits(start, end):
                minimum[start] = min(minimum[start], 1 + minimum[end])

    segment_count = minimum[0]
    target = len(" ".join(words)) / segment_count

    @lru_cache(maxsize=None)
    def choose(start: int, remaining: int) -> tuple[float, tuple[int, ...]]:
        if remaining == 0:
            return (0.0, ()) if start == len(words) else (math.inf, ())

        best: tuple[float, tuple[int, ...]] = (math.inf, ())
        for end in range(start + 1, len(words) + 1):
            if not fits(start, end):
                continue
            tail_cost, tail_breaks = choose(end, remaining - 1)
            length = len(" ".join(words[start:end]))
            punctuation_bonus = 20 if words[end - 1].endswith((",", ";", ":", ".", "!", "?")) else 0
            cost = (length - target) ** 2 - punctuation_bonus + tail_cost
            if cost < best[0]:
                best = cost, (end,) + tail_breaks
        return best

    _, breaks = choose(0, segment_count)
    result: list[str] = []
    start = 0
    for end in breaks:
        result.append(" ".join(words[start:end]))
        start = end
    return result


def build_timed_segments(lines: list, fallback_duration_ms: int = 3500) -> list[TimedSegment]:
    result: list[TimedSegment] = []
    for index, line in enumerate(lines):
        chunks = split_for_display(line.words)
        end_ms = lines[index + 1].start_ms if index + 1 < len(lines) else line.start_ms + fallback_duration_ms
        duration = max(len(chunks) * 500, end_ms - line.start_ms)
        weights = [max(1, sum(character.isalnum() for character in chunk)) for chunk in chunks]
        total_weight = sum(weights)
        elapsed_weight = 0
        for chunk, weight in zip(chunks, weights):
            start_ms = line.start_ms + round(duration * elapsed_weight / total_weight)
            result.append(TimedSegment(start_ms, chunk))
            elapsed_weight += weight
    return result


def ascii_text(text: str) -> str:
    for symbol in "♪♫♬♩":
        text = text.replace(symbol, "")
    normalized = unicodedata.normalize("NFKD", text)
    return normalized.encode("ascii", "replace").decode("ascii").replace("\t", " ").replace("\n", " ")


def find_serial_port() -> str | None:
    configured = os.getenv("SERIAL_PORT", "").strip()
    if configured:
        return configured
    for port in list_ports.comports():
        description = f"{port.description} {port.manufacturer or ''}".lower()
        if port.vid in {0x2E8A, 0x239A} or "xiao" in description or "rp2040" in description:
            return port.device
    return None


def send_text(connection: serial.Serial, text: str) -> None:
    if (
        os.getenv("DISPLAY_SUPPORTS_ICONS") == "1"
        and any(symbol in text for symbol in "♪♫♬♩")
        and not ascii_text(text).strip()
    ):
        connection.write(b"ICON\tMUSIC\n")
        return
    connection.write(f"TEXT\t{ascii_text(text)}\n".encode())


def toggle_playback(spotify, playback: Playback | None) -> None:
    if playback and playback.is_playing:
        spotify.pause_playback()
    else:
        spotify.start_playback()


def main(segment_builder=build_timed_segments, playback_provider=None, playback_toggle=None) -> int:
    load_dotenv()
    spotify = None
    if playback_provider is None:
        spotify = build_spotify_client(SPOTIFY_SCOPE)
        spotify.auth_manager.get_access_token()
        playback_provider = lambda: get_playback(spotify)
        playback_toggle = lambda: toggle_playback(spotify, playback)
    lyrics_delay_ms = int(os.getenv("LYRICS_DELAY_MS", "500"))
    api_url = os.getenv("LYRICS_API_URL", "http://localhost:8080")
    sp_dc = os.getenv("SP_DC")

    connection: serial.Serial | None = None
    playback: Playback | None = None
    track_id: str | None = None
    segments: list[TimedSegment] = []
    segment_starts: list[int] = []
    displayed: str | None = None
    next_poll = 0.0

    print("XIAO Lyrics host started. Press Ctrl+C to stop.")
    try:
        while True:
            if connection is None:
                port = find_serial_port()
                if port:
                    try:
                        connection = serial.Serial(port, 115200, timeout=0)
                        time.sleep(1.5)
                        print(f"Connected to {port}")
                        displayed = None
                    except serial.SerialException:
                        connection = None
                if connection is None:
                    print("Waiting for XIAO RP2040…", end="\r")
                    time.sleep(1)
                    continue

            try:
                while connection.in_waiting:
                    command = connection.readline().decode(errors="ignore").strip()
                    if command == "TOGGLE":
                        try:
                            playback_toggle()
                        except (SpotifyException, RuntimeError) as exc:
                            message = exc.msg if isinstance(exc, SpotifyException) else str(exc)
                            print(f"Playback rejected play/pause: {message or exc}")

                if time.monotonic() >= next_poll:
                    playback = playback_provider()
                    next_poll = time.monotonic() + POLL_INTERVAL_SECONDS
                    if playback and playback.track_id != track_id:
                        track_id = playback.track_id
                        try:
                            sync_type, lines = fetch_lyrics(api_url, track_id, sp_dc)
                            segments = segment_builder(lines) if sync_type == "LINE_SYNCED" else []
                            segment_starts = [segment.start_ms for segment in segments]
                            displayed = None
                        except LyricsError as exc:
                            segments = []
                            segment_starts = []
                            send_text(connection, str(exc))
                    elif playback is None:
                        track_id = None
                        segments = []
                        segment_starts = []

                text = "Play a song"
                if playback and segments:
                    position = max(0, playback.position_ms() - lyrics_delay_ms)
                    index = bisect.bisect_right(segment_starts, position) - 1
                    text = segments[index].text if index >= 0 else ""
                if text != displayed:
                    send_text(connection, text)
                    displayed = text

                time.sleep(0.05)
            except (serial.SerialException, OSError):
                print("XIAO disconnected; waiting for it to return.")
                connection.close()
                connection = None
    except KeyboardInterrupt:
        return 0
    finally:
        if connection:
            connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
