import unittest
from unittest.mock import Mock, patch

from app import LyricLine
from device_host import ascii_text, build_timed_segments, send_text, split_for_display, wrapped_rows
from device_host_linux import track_id_from_metadata
from device_host_phrase import build_phrase_segments, estimated_syllables, split_into_phrases
from device_host_word import build_word_segments


class DeviceHostTests(unittest.TestCase):
    def test_linux_mpris_metadata_provides_spotify_track_id(self):
        metadata = {"xesam:url": "https://open.spotify.com/track/6vZCWKiXwxCG0buNfWeQD8"}

        self.assertEqual(track_id_from_metadata(metadata), "6vZCWKiXwxCG0buNfWeQD8")

    def test_music_note_placeholders_become_blank(self):
        self.assertEqual(ascii_text("♪ ♫"), " ")

    def test_u8g2_display_receives_music_icon_command(self):
        connection = Mock()

        with patch.dict("os.environ", {"DISPLAY_SUPPORTS_ICONS": "1"}):
            send_text(connection, "♪")

        connection.write.assert_called_once_with(b"ICON\tMUSIC\n")

    def test_u8g2_display_keeps_ordinary_empty_sections_blank(self):
        connection = Mock()

        with patch.dict("os.environ", {"DISPLAY_SUPPORTS_ICONS": "1"}):
            send_text(connection, "")

        connection.write.assert_called_once_with(b"TEXT\t\n")

    def test_long_line_is_split_into_balanced_display_segments(self):
        chunks = split_for_display("this is a song and these are the lyrics for it")

        self.assertEqual(chunks, ["this is a song and these", "are the lyrics for it"])
        self.assertTrue(all(wrapped_rows(chunk) <= 4 for chunk in chunks))

    def test_segment_timing_is_distributed_within_line(self):
        lines = [
            LyricLine(1000, "this is a song and these are the lyrics for it"),
            LyricLine(5000, "next"),
        ]

        segments = build_timed_segments(lines)

        self.assertEqual(segments[0].start_ms, 1000)
        self.assertGreater(segments[1].start_ms, 1000)
        self.assertLess(segments[1].start_ms, 5000)
        self.assertEqual(segments[-1].text, "next")

    def test_word_mode_displays_one_timed_word_at_a_time(self):
        lines = [
            LyricLine(1000, "Sing these words, slowly."),
            LyricLine(5000, "next"),
        ]

        segments = build_word_segments(lines)

        self.assertEqual([segment.text for segment in segments[:4]], ["Sing", "these", "words,", "slowly."])
        self.assertEqual(segments[0].start_ms, 1000)
        self.assertTrue(all(1000 <= segment.start_ms < 5000 for segment in segments[:4]))

    def test_phrase_mode_uses_short_uncramped_groups(self):
        phrases = split_into_phrases("this is a song and these are the lyrics for it")

        self.assertEqual(" ".join(phrases), "this is a song and these are the lyrics for it")
        self.assertTrue(all(len(phrase.split()) <= 4 for phrase in phrases))
        self.assertTrue(all(wrapped_rows(phrase) <= 2 for phrase in phrases))

    def test_phrase_timing_uses_syllable_weight_and_line_boundaries(self):
        lines = [LyricLine(1000, "beautiful rhythm moving quickly"), LyricLine(4000, "next")]

        segments = build_phrase_segments(lines)

        self.assertEqual(segments[0].start_ms, 1000)
        self.assertGreater(estimated_syllables("beautiful"), estimated_syllables("rhythm"))
        self.assertGreater(len(segments), 2)
        self.assertLess(segments[1].start_ms, 4000)


if __name__ == "__main__":
    unittest.main()
