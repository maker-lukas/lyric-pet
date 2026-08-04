from __future__ import annotations

import re
import time

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib

from app import Playback
from device_host import main


MPRIS_NAME = "org.mpris.MediaPlayer2.spotify"
MPRIS_PATH = "/org/mpris/MediaPlayer2"
MPRIS_PLAYER = "org.mpris.MediaPlayer2.Player"
DBUS_PROPERTIES = "org.freedesktop.DBus.Properties"


def track_id_from_metadata(metadata: dict) -> str | None:
    for value in (metadata.get("xesam:url", ""), metadata.get("mpris:trackid", "")):
        match = re.search(r"(?:track/|track:)([A-Za-z0-9]+)", str(value))
        if match:
            return match.group(1)
    return None


class SpotifyMpris:
    def __init__(self) -> None:
        self.bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)

    def properties(self) -> dict:
        try:
            result = self.bus.call_sync(
                MPRIS_NAME,
                MPRIS_PATH,
                DBUS_PROPERTIES,
                "GetAll",
                GLib.Variant("(s)", (MPRIS_PLAYER,)),
                GLib.VariantType("(a{sv})"),
                Gio.DBusCallFlags.NONE,
                2_000,
                None,
            )
        except GLib.Error:
            return {}
        return result.unpack()[0]

    def get_playback(self) -> Playback | None:
        properties = self.properties()
        metadata = properties.get("Metadata", {})
        track_id = track_id_from_metadata(metadata)
        if not track_id:
            return None

        artists = metadata.get("xesam:artist", [])
        return Playback(
            track_id=track_id,
            title=str(metadata.get("xesam:title", "Unknown track")),
            artists=", ".join(str(artist) for artist in artists),
            progress_ms=max(0, int(properties.get("Position", 0)) // 1_000),
            duration_ms=max(1, int(metadata.get("mpris:length", 1_000)) // 1_000),
            is_playing=properties.get("PlaybackStatus") == "Playing",
            sampled_at=time.monotonic(),
        )

    def toggle(self) -> None:
        try:
            self.bus.call_sync(
                MPRIS_NAME,
                MPRIS_PATH,
                MPRIS_PLAYER,
                "PlayPause",
                None,
                None,
                Gio.DBusCallFlags.NONE,
                2_000,
                None,
            )
        except GLib.Error as exc:
            raise RuntimeError(f"Spotify MPRIS is unavailable: {exc.message}") from exc


if __name__ == "__main__":
    spotify = SpotifyMpris()
    raise SystemExit(main(playback_provider=spotify.get_playback, playback_toggle=spotify.toggle))
