"""
Armenian (Eastern Armenian) cardinal number parsing.

Handles two input shapes, since speech-to-text output is a mix of both
in practice (Whisper tends to render larger numbers as digits even
when the speaker says them as words):

  1. Digit form: "50000", "50,000", "50 000", "1.500,75"
  2. Word form:  "հիսուն հազար" (fifty thousand), "երկու հարյուր տասնհինգ" (215)

Word-form numbers in Armenian are often concatenated without spaces
for the tens+units pair (e.g. "քսանմեկ" = twenty-one), so a single
whitespace-split token can itself encode a two-part number. We handle
that with a prefix match against the tens table before giving up on a
token.

This module intentionally only knows cardinal numbers up to the
low millions — enough for any plausible cash transaction. It is not a
full Armenian morphological analyzer.
"""
import re
from dataclasses import dataclass

ONES = {
    "զրո": 0, "մեկ": 1, "երկու": 2, "երեք": 3, "չորս": 4, "հինգ": 5,
    "վեց": 6, "յոթ": 7, "ութ": 8, "ինը": 9,
    "տասը": 10, "տասն": 10,
    "տասնմեկ": 11, "տասներկու": 12, "տասներեք": 13, "տասնչորս": 14,
    "տասնհինգ": 15, "տասնվեց": 16, "տասնյոթ": 17, "տասնութ": 18, "տասնինը": 19,
}

TENS = {
    "քսան": 20, "երեսուն": 30, "քառասուն": 40, "հիսուն": 50,
    "վաթսուն": 60, "յոթանասուն": 70, "ութսուն": 80, "իննսուն": 90,
}

SCALES = {
    "հարյուր": 100,
    "հազար": 1_000,
    "միլիոն": 1_000_000,
}

# Longest-first so "տասնութ" (18) is tried before "տասը" (10) as a prefix.
_TENS_BY_LEN = sorted(TENS.items(), key=lambda kv: -len(kv[0]))


def _parse_word_token(word: str) -> int | None:
    """Resolve a single whitespace-delimited word to a number, handling
    the concatenated tens+ones case (e.g. "երեսունհինգ" = 35)."""
    word = word.strip(",.።՝")
    if word in ONES:
        return ONES[word]
    if word in TENS:
        return TENS[word]
    if word in SCALES:
        return SCALES[word]
    for tens_word, tens_val in _TENS_BY_LEN:
        if word.startswith(tens_word) and word != tens_word:
            remainder = word[len(tens_word):]
            if remainder in ONES and ONES[remainder] < 10:
                return tens_val + ONES[remainder]
    return None


def parse_word_number(text: str) -> int | None:
    """Parse a maximal run of Armenian number words anywhere in `text`.
    Returns None if no number words are found."""
    tokens = text.split()
    best_run: list[int | str] = []
    current_run: list[tuple[str, int]] = []

    def flush(run: list[tuple[str, int]]) -> int | None:
        if not run:
            return None
        total = 0
        current = 0
        for _, val in run:
            if val in SCALES.values() and val >= 100:
                current = (current or 1) * val
                if val >= 1000:
                    total += current
                    current = 0
            else:
                current += val
        return total + current

    best_value = None
    for tok in tokens:
        val = _parse_word_token(tok)
        if val is not None:
            current_run.append((tok, val))
        else:
            if current_run:
                v = flush(current_run)
                if v is not None:
                    best_value = v  # keep the last (usually only) run
                current_run = []
    if current_run:
        v = flush(current_run)
        if v is not None:
            best_value = v
    return best_value


_DIGIT_RE = re.compile(r"\d[\d\s,.\u00A0]*\d|\d")


def parse_digit_number(text: str) -> float | None:
    """Parse the first digit-run in `text`, tolerating thousand separators
    (space, comma, dot) and an optional decimal part after the last dot
    or comma when followed by exactly two digits."""
    m = _DIGIT_RE.search(text)
    if not m:
        return None
    raw = m.group(0)
    # Decide whether the last '.' or ',' is a decimal point (exactly 2
    # digits follow) or a thousands separator.
    last_sep_match = re.search(r"[.,](\d+)$", raw)
    if last_sep_match and len(last_sep_match.group(1)) == 2:
        integer_part = raw[: last_sep_match.start()]
        frac_part = last_sep_match.group(1)
        cleaned_int = re.sub(r"[^\d]", "", integer_part)
        return float(f"{cleaned_int}.{frac_part}")
    cleaned = re.sub(r"[^\d]", "", raw)
    return float(cleaned) if cleaned else None


@dataclass
class ParsedNumber:
    value: float
    source: str  # "digit" or "word"


def parse_number(text: str) -> ParsedNumber | None:
    """Digit form takes priority (it's unambiguous); word form is the
    fallback for fully spelled-out amounts."""
    digit_val = parse_digit_number(text)
    if digit_val is not None:
        return ParsedNumber(value=digit_val, source="digit")
    word_val = parse_word_number(text)
    if word_val is not None:
        return ParsedNumber(value=float(word_val), source="word")
    return None
