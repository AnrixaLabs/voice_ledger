"""
Currency-aware amount extraction for Armenian utterances.

Looks for a currency cue (word or symbol) and pulls the nearest number
to it. Defaults to AMD (Armenian dram) when an amount is present with
no currency word at all, since that's the overwhelmingly common case
for this app's expected use.
"""
import re
from dataclasses import dataclass

from .numbers_hy import parse_number

CURRENCY_MAP: dict[str, str] = {
    # dram
    "դրամ": "AMD", "դր": "AMD", "֏": "AMD", "amd": "AMD", "dram": "AMD",
    # US dollar
    "դոլար": "USD", "$": "USD", "usd": "USD", "dollar": "USD",
    # euro
    "եվրո": "EUR", "€": "EUR", "eur": "EUR", "euro": "EUR",
    # Russian ruble
    "ռուբլի": "RUB", "₽": "RUB", "rub": "RUB",
}

_CURRENCY_PATTERN = re.compile(
    "|".join(re.escape(k) for k in sorted(CURRENCY_MAP, key=len, reverse=True)),
    re.IGNORECASE,
)


@dataclass
class ParsedMoney:
    amount: float
    currency: str  # ISO-ish code: AMD / USD / EUR / RUB


def parse_money(text: str, default_currency: str = "AMD") -> ParsedMoney | None:
    number = parse_number(text)
    if number is None:
        return None

    currency = default_currency
    m = _CURRENCY_PATTERN.search(text)
    if m:
        currency = CURRENCY_MAP[m.group(0).lower()]

    return ParsedMoney(amount=number.value, currency=currency)
