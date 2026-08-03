import unittest
from unittest.mock import Mock, patch

from app import LyricLine, active_line_index, fetch_lyrics


class LyricsTests(unittest.TestCase):
    def test_active_line_tracks_song_position(self):
        lines = [LyricLine(1000, "one"), LyricLine(2500, "two"), LyricLine(4000, "three")]

        self.assertEqual(active_line_index(lines, 999), -1)
        self.assertEqual(active_line_index(lines, 1000), 0)
        self.assertEqual(active_line_index(lines, 3999), 1)
        self.assertEqual(active_line_index(lines, 9000), 2)

    @patch("app.requests.get")
    def test_fetch_lyrics_parses_native_api_response(self, get: Mock):
        get.return_value.ok = True
        get.return_value.json.return_value = {
            "error": False,
            "syncType": "LINE_SYNCED",
            "lines": [{"startTimeMs": "960", "words": "Hello"}],
        }

        sync_type, lines = fetch_lyrics("http://localhost:8080", "track-id")

        self.assertEqual(sync_type, "LINE_SYNCED")
        self.assertEqual(lines, [LyricLine(960, "Hello")])
        get.assert_called_once_with(
            "http://localhost:8080/", params={"trackid": "track-id"}, timeout=10
        )

    @patch("app.get_web_player_token", return_value="token")
    @patch("app.requests.get")
    def test_fetch_lyrics_can_call_spotify_directly(self, get: Mock, get_token: Mock):
        lyrics_response = Mock()
        lyrics_response.ok = True
        lyrics_response.json.return_value = {
            "lyrics": {
                "syncType": "LINE_SYNCED",
                "lines": [{"startTimeMs": "1200", "words": "Direct"}],
            }
        }
        get.return_value = lyrics_response

        sync_type, lines = fetch_lyrics("unused", "track-id", "cookie")

        self.assertEqual(sync_type, "LINE_SYNCED")
        self.assertEqual(lines, [LyricLine(1200, "Direct")])
        get_token.assert_called_once_with("cookie")


if __name__ == "__main__":
    unittest.main()
