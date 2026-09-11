import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.nlu.numbers_hy import parse_number, parse_word_number, parse_digit_number
from app.nlu.money_hy import parse_money
from app.nlu.dates_hy import parse_date


# ---- numbers: digit form ----

def test_digit_simple():
    assert parse_digit_number("50000") == 50000.0

def test_digit_thousand_separator_space():
    assert parse_digit_number("50 000 դրամ") == 50000.0

def test_digit_thousand_separator_comma():
    assert parse_digit_number("12,500") == 12500.0

def test_digit_decimal():
    assert parse_digit_number("199.99") == 199.99


# ---- numbers: word form ----

def test_word_simple_ones():
    assert parse_word_number("հինգ") == 5

def test_word_teen():
    assert parse_word_number("տասնութ") == 18

def test_word_concatenated_tens_ones():
    assert parse_word_number("երեսունհինգ") == 35  # thirty-five, one token

def test_word_spaced_tens_ones():
    assert parse_word_number("քսան մեկ") == 21

def test_word_hundred():
    assert parse_word_number("երկու հարյուր") == 200

def test_word_hundred_plus_tens():
    assert parse_word_number("երեք հարյուր հիսուն") == 350

def test_word_thousand():
    assert parse_word_number("հիսուն հազար") == 50000

def test_word_thousand_plus_hundred():
    assert parse_word_number("երկու հազար հինգ հարյուր") == 2500

def test_word_bare_hundred_thousand():
    assert parse_word_number("հազար դրամ") == 1000


# ---- money ----

def test_money_digit_with_dram():
    m = parse_money("հիսուն հազար դրամ վճարեցի")
    assert m and m.currency == "AMD"

def test_money_digit_dram():
    m = parse_money("50000 դրամ")
    assert m and m.amount == 50000.0 and m.currency == "AMD"

def test_money_dollar_symbol():
    m = parse_money("$200 մնացել է")
    assert m and m.amount == 200.0 and m.currency == "USD"

def test_money_default_currency_when_absent():
    m = parse_money("20000")
    assert m and m.currency == "AMD"

def test_money_euro_word():
    m = parse_money("հարյուր եվրո")
    assert m and m.amount == 100.0 and m.currency == "EUR"


# ---- dates ----

def test_date_today():
    d = parse_date("այսօր", today=date(2026, 9, 11))
    assert d.value == date(2026, 9, 11)

def test_date_tomorrow():
    d = parse_date("վաղը", today=date(2026, 9, 11))
    assert d.value == date(2026, 9, 12)

def test_date_next_week():
    d = parse_date("հաջորդ շաբաթ", today=date(2026, 9, 11))
    assert d.value == date(2026, 9, 18)

def test_date_digit_form():
    d = parse_date("10.09.2026", today=date(2026, 9, 1))
    assert d.value == date(2026, 9, 10)

def test_date_absolute_month_genitive():
    d = parse_date("վճարումը մինչև 15 հոկտեմբերի 2026", today=date(2026, 9, 11))
    assert d.value == date(2026, 10, 15)

def test_date_weekday_next_occurrence():
    # 2026-09-11 is a Friday; asking for Friday should land on the *next* one, not today.
    d = parse_date("ուրբաթ", today=date(2026, 9, 11))
    assert d.value == date(2026, 9, 18)
    assert d.value.weekday() == 4  # Friday

def test_date_saturday_not_confused_with_next_week_phrase():
    # "շաբաթ" alone (Saturday) must not match after the "հաջորդ շաբաթ" phrase
    # check already consumed the "next week" case above; verify it still
    # resolves correctly on its own.
    d = parse_date("շաբաթ", today=date(2026, 9, 11))  # Friday
    assert d.value == date(2026, 9, 12)  # next day is Saturday
    assert d.value.weekday() == 5
