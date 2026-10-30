import random

import pytest
from synth import gen_bad_iban, gen_bad_tckn, gen_iban, gen_tckn, gen_vkn

from pii_shield_tr.validators import (
    canonical_phone,
    iban_check_digits,
    iban_mod97,
    is_valid_plate,
    is_valid_tckn,
    is_valid_tr_iban,
    is_valid_vkn,
    tckn_check_digits,
)


def test_tckn_check_digit_formula_by_hand():
    # Worked example, digits 1-9 = 123456789:
    # d10 = ((1+3+5+7+9)*7 - (2+4+6+8)) % 10 = (175-20) % 10 = 5
    # d11 = (45+5) % 10 = 0
    assert tckn_check_digits("123456789") == "50"
    assert is_valid_tckn("12345678950")


@pytest.mark.parametrize(
    "value",
    ["01234567890", "1234567895", "123456789500", "12345678951", "abcdefghijk", ""],
)
def test_tckn_rejects(value):
    assert not is_valid_tckn(value)


def test_generated_identifiers_round_trip_through_validators():
    rng = random.Random(1)
    for _ in range(200):
        assert is_valid_tckn(gen_tckn(rng))
        assert is_valid_vkn(gen_vkn(rng))
        assert is_valid_tr_iban(gen_iban(rng))
        assert is_valid_tr_iban(gen_iban(rng, spaced=True))


def test_single_digit_corruption_is_caught():
    rng = random.Random(2)
    for _ in range(200):
        assert not is_valid_tckn(gen_bad_tckn(rng))
        assert not is_valid_tr_iban(gen_bad_iban(rng))


def test_iban_rejects_wrong_country_and_length():
    bban = "9999900000000000000001"
    good = f"TR{iban_check_digits(bban)}{bban}"
    assert is_valid_tr_iban(good)
    assert is_valid_tr_iban(good.lower())
    assert not is_valid_tr_iban(good[:-1])
    assert not is_valid_tr_iban("DE" + good[2:])


def test_iban_mod97_against_an_external_specimen():
    # The textbook specimen with a made-up bank code; not a Turkish identifier, and the only
    # value in this repo not produced by the generator. It anchors the arithmetic to the spec.
    assert iban_mod97("GB82WEST12345698765432") == 1


def test_vkn_rejects_changed_check_digit():
    rng = random.Random(3)
    value = gen_vkn(rng)
    corrupted = value[:-1] + str((int(value[-1]) + 1) % 10)
    assert is_valid_vkn(value)
    assert not is_valid_vkn(corrupted)
    assert not is_valid_vkn(value[:-1])


@pytest.mark.parametrize(
    "spelling",
    ["05550000001", "0555 000 00 01", "+90 555 000 00 01", "+905550000001", "0 (555) 000-00-01",
     "0090 555 000 00 01", "555 000 00 01"],
)
def test_phone_spellings_share_a_canonical_form(spelling):
    assert canonical_phone(spelling) == "5550000001"


@pytest.mark.parametrize("plate", ["34 ABC 123", "06 A 1234", "35AB123", "81 XY 1234", "01 ABC 12"])
def test_plate_valid(plate):
    assert is_valid_plate(plate)


@pytest.mark.parametrize(
    "plate", ["00 ABC 123", "82 AB 123", "34 A 123", "34 ABC 1234", "34 AB 12"]
)
def test_plate_invalid(plate):
    assert not is_valid_plate(plate)
