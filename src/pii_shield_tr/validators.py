"""Checksum validators for Turkish identifiers. Pure functions, digits-only canonical forms."""

from __future__ import annotations

import re

_NON_DIGIT = re.compile(r"\D")
_IBAN_SEP = re.compile(r"[\s-]")


def digits_only(value: str) -> str:
    return _NON_DIGIT.sub("", value)


def tckn_check_digits(first_nine: str) -> str:
    """Return the two check digits for the first nine digits of a T.C. identity number."""
    d = [int(c) for c in first_nine]
    tenth = ((d[0] + d[2] + d[4] + d[6] + d[8]) * 7 - (d[1] + d[3] + d[5] + d[7])) % 10
    eleventh = (sum(d) + tenth) % 10
    return f"{tenth}{eleventh}"


def is_valid_tckn(value: str) -> bool:
    """T.C. identity number: 11 digits, no leading zero, two check digits."""
    digits = digits_only(value)
    if len(digits) != 11 or digits[0] == "0":
        return False
    return digits[9:] == tckn_check_digits(digits[:9])


def vkn_check_digit(first_nine: str) -> str:
    """Return the check digit for the first nine digits of a 10-digit tax number (VKN)."""
    total = 0
    for i, c in enumerate(first_nine):
        shifted = (int(c) + 9 - i) % 10
        weighted = (shifted * 2 ** (9 - i)) % 9
        if shifted != 0 and weighted == 0:
            weighted = 9
        total += weighted
    return str((10 - total % 10) % 10)


def is_valid_vkn(value: str) -> bool:
    digits = digits_only(value)
    return len(digits) == 10 and digits[9] == vkn_check_digit(digits[:9])


def normalize_iban(value: str) -> str:
    return _IBAN_SEP.sub("", value).upper()


def iban_mod97(iban: str) -> int:
    """ISO 13616 remainder: move the first four characters to the end, map letters, mod 97."""
    rearranged = iban[4:] + iban[:4]
    numeric = "".join(str(int(c, 36)) for c in rearranged)
    return int(numeric) % 97


def is_valid_tr_iban(value: str) -> bool:
    """TR IBAN: 'TR', two check digits, 22 digits, 26 characters in total, mod-97 == 1."""
    iban = normalize_iban(value)
    if len(iban) != 26 or not iban.startswith("TR") or not iban[2:].isdigit():
        return False
    return iban_mod97(iban) == 1


def iban_check_digits(bban: str) -> str:
    """Return check digits for a TR IBAN whose BBAN (the 22 digits after them) is given."""
    return f"{98 - iban_mod97('TR00' + bban):02d}"


# Numbering plan: mobile prefixes and geographic area codes. Used to reject random digit runs.
_MOBILE_RE = re.compile(r"5(?:0[1-9]|[345]\d|6[01])")
_AREA_CODES = frozenset(
    """
    212 216 222 224 226 228 232 236 242 246 248 252 256 258 262 264 266 272 274 276 282 284
    286 288 312 318 322 324 326 328 332 338 342 344 346 348 352 354 356 358 362 364 366 368
    370 372 374 376 378 380 382 384 386 388 412 414 416 422 424 426 428 432 434 436 438 442
    446 452 454 456 458 462 464 466 472 474 476 478 482 484 486 488 850
    """.split()
)


def is_mobile_prefix(prefix: str) -> bool:
    return _MOBILE_RE.fullmatch(prefix) is not None


def is_area_code(prefix: str) -> bool:
    return prefix in _AREA_CODES


def canonical_phone(value: str) -> str:
    """Reduce any accepted phone spelling to its 10-digit national number."""
    digits = digits_only(value)
    if digits.startswith("0090"):
        digits = digits[4:]
    elif digits.startswith("90") and len(digits) == 12:
        digits = digits[2:]
    elif digits.startswith("0"):
        digits = digits[1:]
    return digits


_PLATE_RE = re.compile(r"(\d{2})\s*([A-Z]{1,3})\s*(\d{2,4})")


def canonical_plate(value: str) -> str:
    return re.sub(r"\s+", "", value).upper()


def is_valid_plate(value: str) -> bool:
    """Province 01-81, then the letter/digit shapes actually issued: 1+4, 2+3/4, 3+2/3."""
    match = _PLATE_RE.fullmatch(value.strip())
    if match is None:
        return False
    province, letters, numbers = match.groups()
    if not 1 <= int(province) <= 81:
        return False
    return (len(letters), len(numbers)) in {(1, 4), (2, 3), (2, 4), (3, 2), (3, 3)}
