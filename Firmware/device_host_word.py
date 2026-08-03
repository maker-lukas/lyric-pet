from __future__ import annotations

from app import LyricLine
from device_host import TimedSegment, main


def word_weight(word: str) -> float:
    letters = sum(character.isalnum() for character in word)
    weight = max(1.0, letters / 3)
    if word.endswith((",", ";", ":")):
        weight += 0.5
    elif word.endswith((".", "!", "?")):
        weight += 1.0
    return weight


def build_word_segments(
    lines: list[LyricLine], fallback_duration_ms: int = 3500
) -> list[TimedSegment]:
    result: list[TimedSegment] = []
    for index, line in enumerate(lines):
        words = line.words.split()
        if not words:
            result.append(TimedSegment(line.start_ms, ""))
            continue

        end_ms = (
            lines[index + 1].start_ms
            if index + 1 < len(lines)
            else line.start_ms + fallback_duration_ms
        )
        duration = max(1, end_ms - line.start_ms)
        weights = [word_weight(word) for word in words]
        total_weight = sum(weights)
        elapsed_weight = 0.0
        for word, weight in zip(words, weights):
            start_ms = line.start_ms + round(duration * elapsed_weight / total_weight)
            result.append(TimedSegment(start_ms, word))
            elapsed_weight += weight
    return result


if __name__ == "__main__":
    raise SystemExit(main(build_word_segments))
