from __future__ import annotations

import re

from app import LyricLine
from device_host import TimedSegment, main, wrapped_rows


MAX_WORDS = 4
MAX_PHRASE_ROWS = 2


def estimated_syllables(word: str) -> int:
    clean = re.sub(r"[^a-z]", "", word.lower())
    if not clean:
        return 1
    groups = len(re.findall(r"[aeiouy]+", clean))
    if clean.endswith("e") and not clean.endswith(("le", "ye")) and groups > 1:
        groups -= 1
    return max(1, groups)


def split_into_phrases(text: str) -> list[str]:
    words = text.split()
    if not words:
        return [""]

    phrases: list[str] = []
    start = 0
    while start < len(words):
        end = start
        while end < len(words) and end - start < MAX_WORDS:
            candidate = " ".join(words[start : end + 1])
            if end > start and wrapped_rows(candidate) > MAX_PHRASE_ROWS:
                break
            end += 1
            if end - start >= 2 and words[end - 1].endswith((",", ";", ":", ".", "!", "?")):
                break

        if end == start:
            end += 1

        remaining = len(words) - end
        if remaining == 1 and end - start < MAX_WORDS:
            candidate = " ".join(words[start:])
            if wrapped_rows(candidate) <= MAX_PHRASE_ROWS:
                end = len(words)

        phrases.append(" ".join(words[start:end]))
        start = end
    return phrases


def phrase_weight(phrase: str) -> float:
    words = phrase.split()
    weight = sum(estimated_syllables(word) for word in words)
    if phrase.endswith((",", ";", ":")):
        weight += 0.75
    elif phrase.endswith((".", "!", "?")):
        weight += 1.5
    return max(1.0, weight)


def build_phrase_segments(
    lines: list[LyricLine], fallback_duration_ms: int = 3500
) -> list[TimedSegment]:
    result: list[TimedSegment] = []
    for index, line in enumerate(lines):
        phrases = split_into_phrases(line.words)
        end_ms = (
            lines[index + 1].start_ms
            if index + 1 < len(lines)
            else line.start_ms + fallback_duration_ms
        )
        duration = max(1, end_ms - line.start_ms)
        weights = [phrase_weight(phrase) for phrase in phrases]
        total_weight = sum(weights)
        elapsed_weight = 0.0
        for phrase, weight in zip(phrases, weights):
            start_ms = line.start_ms + round(duration * elapsed_weight / total_weight)
            result.append(TimedSegment(start_ms, phrase))
            elapsed_weight += weight
    return result


if __name__ == "__main__":
    raise SystemExit(main(build_phrase_segments))
