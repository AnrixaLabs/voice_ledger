"""
Two capture modes, two extraction strategies:

Guided mode (recommended default): the app asks for one field at a
time ("say the name", "say how much was paid", ...). Each answer is a
short, single-purpose utterance, so a plain rule-based parser per
field is both accurate and fully offline. `extract_guided_field` below
is that parser.

Free-form mode: the user says everything in one breath. That needs
real language understanding, so this calls Claude to pull the same
fields out of one transcript. It requires an Anthropic API key and an
internet connection; if neither is available, fall back to guided
mode. See config.settings.anthropic_api_key.

Either way, the app must show the extracted fields back to the user
for a quick visual/spoken confirmation *before* the biometric-signed
submit - these parsers are a first draft, not a source of truth.
"""
import json
from dataclasses import dataclass
from datetime import date
from typing import Literal, Optional

from .dates_hy import parse_date
from .money_hy import parse_money

FieldName = Literal[
    "counterparty_name", "place", "amount_paid", "amount_due",
    "transaction_date", "due_date",
]


def extract_guided_field(field: FieldName, transcript: str) -> dict:
    """Parse a single guided-mode answer. Returns a dict with at least
    `raw_transcript`; money/date fields also include the parsed value."""
    out: dict = {"field": field, "raw_transcript": transcript}

    if field in ("amount_paid", "amount_due"):
        parsed = parse_money(transcript)
        if parsed:
            out["amount"] = parsed.amount
            out["currency"] = parsed.currency
        return out

    if field in ("transaction_date", "due_date"):
        parsed = parse_date(transcript)
        if parsed:
            out["date"] = parsed.value.isoformat()
        return out

    # counterparty_name / place: light cleanup only - these are open
    # vocabulary (proper nouns) so we don't try to parse them further.
    out["text"] = transcript.strip().strip(".,։")
    return out


FREEFORM_SYSTEM_PROMPT = """\
You extract structured payment-ledger fields from a transcript of \
spoken Armenian. Respond with ONLY a JSON object, no prose, no \
markdown fences, matching this shape exactly:

{
  "counterparty_name": string or null,
  "place": string or null,
  "amount_paid": {"amount": number, "currency": "AMD"|"USD"|"EUR"|"RUB"} or null,
  "amount_due": {"amount": number, "currency": "AMD"|"USD"|"EUR"|"RUB"} or null,
  "transaction_date": "YYYY-MM-DD" or null,
  "due_date": "YYYY-MM-DD" or null
}

Today's date is {today}. Resolve relative dates (\u0561\u0575\u057d\u0585\u0580, \u057e\u0561\u0572\u0568, ...) against it. \
If a field isn't mentioned, use null. Never invent a value that \
wasn't said.
"""


@dataclass
class FreeformResult:
    fields: dict
    raw_response: str


def extract_freeform(transcript: str, today: Optional[date] = None) -> FreeformResult:
    """Send the whole transcript to Claude and get every field back at
    once. Raises RuntimeError if no API key is configured - callers
    should catch this and fall back to guided mode."""
    from ..config import settings

    if not settings.anthropic_api_key:
        raise RuntimeError(
            "Free-form mode needs settings.anthropic_api_key. "
            "Either set it, or use guided mode (no internet required)."
        )

    import anthropic  # lazy import: optional dependency

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    today = today or date.today()

    response = client.messages.create(
        model=settings.freeform_model,
        max_tokens=500,
        system=FREEFORM_SYSTEM_PROMPT.format(today=today.isoformat()),
        messages=[{"role": "user", "content": transcript}],
    )
    text = "".join(block.text for block in response.content if block.type == "text")
    fields = json.loads(text)
    return FreeformResult(fields=fields, raw_response=text)
