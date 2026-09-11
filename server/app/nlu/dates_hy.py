"""
Armenian date-expression parsing.

Covers three shapes, checked in this order (most specific first so a
phrase like "հաջորդ շաբաթ" - next week - isn't mis-read as the
weekday "շաբաթ" - Saturday):

  1. Digit dates: "10.09.2026", "10/09/2026", "10-09-26"
  2. Relative phrases: այսօր (today), վաղը (tomorrow), երեկ (yesterday),
     հաջորդ շաբաթ (next week), հաջորդ ամիս (next month), and similar.
  3. Weekday names: returns the next occurrence strictly after `today`.
  4. Absolute day + Armenian month name (+ optional year): "10 սեպտեմբերի"
     or "10 սեպտեմբերի 2026".

This is a first pass tuned for how people actually phrase a payment
due date, not a general-purpose Armenian date grammar. Anything it
can't resolve returns None, and the guided-mode UI should let the
user just say the date again or pick it from a calendar.
"""
import re
from dataclasses import dataclass
from datetime import date, timedelta

from .numbers_hy import parse_word_number

MONTHS = {
    "հունվար": 1, "փետրվար": 2, "մարտ": 3, "ապրիլ": 4,
    "մայիս": 5, "հունիս": 6, "հուլիս": 7, "օգոստոս": 8,
    "սեպտեմբեր": 9, "հոկտեմբեր": 10, "նոյեմբեր": 11, "դեկտեմբեր": 12,
}
_MONTHS_BY_LEN = sorted(MONTHS.items(), key=lambda kv: -len(kv[0]))

# Monday=0 ... Sunday=6, matching date.weekday()
WEEKDAYS = {
    "երկուշաբթի": 0, "երեքշաբթի": 1, "չորեքշաբթի": 2, "հինգշաբթի": 3,
    "ուրբաթ": 4, "շաբաթ": 5, "կիրակի": 6,
}

# Checked before weekday matching, longest phrase first.
_RELATIVE_PHRASES: list[tuple[str, int]] = [
    ("վաղը չէ մյուս օրը", 2),
    ("հաջորդ շաբաթ", 7),
    ("հաջորդ ամիս", 30),
    ("մեկ շաբաթից", 7),
    ("մեկ ամսից", 30),
    ("այսօր", 0),
    ("վաղը", 1),
    ("երեկ", -1),
]

_DIGIT_DATE_RE = re.compile(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})\b")
_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")


@dataclass
class ParsedDate:
    value: date
    source: str  # "digit" | "relative" | "weekday" | "absolute"


def parse_date(text: str, today: date | None = None) -> ParsedDate | None:
    today = today or date.today()
    text_norm = text.strip()

    m = _DIGIT_DATE_RE.search(text_norm)
    if m:
        day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if year < 100:
            year += 2000
        try:
            return ParsedDate(value=date(year, month, day), source="digit")
        except ValueError:
            pass  # fall through to other strategies

    for phrase, offset in _RELATIVE_PHRASES:
        if phrase in text_norm:
            return ParsedDate(value=today + timedelta(days=offset), source="relative")

    for word, weekday_idx in WEEKDAYS.items():
        if word in text_norm:
            days_ahead = (weekday_idx - today.weekday()) % 7
            days_ahead = days_ahead or 7  # strictly the *next* occurrence
            return ParsedDate(value=today + timedelta(days=days_ahead), source="weekday")

    tokens = text_norm.split()
    for i, tok in enumerate(tokens):
        stem = tok.strip(",.։՝")
        month_num = None
        for month_word, num in _MONTHS_BY_LEN:
            if stem.startswith(month_word):
                month_num = num
                break
        if month_num is None:
            continue

        day_num = None
        if i > 0:
            prev = tokens[i - 1].strip(",.։՝")
            if prev.isdigit():
                day_num = int(prev)
            else:
                day_num = parse_word_number(prev)
        if day_num is None or not (1 <= day_num <= 31):
            continue

        year_match = _YEAR_RE.search(text_norm)
        year = int(year_match.group(0)) if year_match else today.year
        try:
            candidate = date(year, month_num, day_num)
        except ValueError:
            continue
        if not year_match and candidate < today:
            # Bare "10 September" spoken after the fact almost always
            # means next year's occurrence for a *due* date context.
            candidate = date(year + 1, month_num, day_num)
        return ParsedDate(value=candidate, source="absolute")

    return None
