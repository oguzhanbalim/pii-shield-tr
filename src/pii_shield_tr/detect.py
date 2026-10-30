"""Find personal-data spans in Turkish text. Regex proposes, validators dispose."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from .names import find_name_spans, tr_lower
from .validators import (
    canonical_phone,
    canonical_plate,
    digits_only,
    is_area_code,
    is_mobile_prefix,
    is_valid_plate,
    is_valid_tckn,
    is_valid_tr_iban,
    is_valid_vkn,
    normalize_iban,
)


class Kind(StrEnum):
    IBAN = "IBAN"
    TCKN = "TCKN"
    VKN = "VKN"
    EMAIL = "EPOSTA"
    PHONE = "TEL"
    PLATE = "PLAKA"
    NAME = "AD"


# When spans overlap the longer one wins; on equal length, the earlier kind here wins.
_PRIORITY = {kind: i for i, kind in enumerate(Kind)}


@dataclass(frozen=True, order=True)
class Span:
    start: int
    end: int
    kind: Kind
    text: str
    canonical: str


_IBAN_RE = re.compile(r"(?<![A-Za-z0-9])[Tt][Rr][ -]?\d{2}(?:[ -]?\d){22}(?!\d)")
_TCKN_RE = re.compile(r"(?<![\d.,])(?:\d{11}|\d{3}[ .-]\d{3}[ .-]\d{3}[ .-]\d{2})(?![\d])")
_VKN_RE = re.compile(r"(?<![\d.,])(?:\d{10}|\d{3}[ .-]\d{3}[ .-]\d{4})(?!\d)")
_VKN_CONTEXT_RE = re.compile(r"(?i)(?:\bvkn\b|\bvergi[ \t]+(?:kimlik|no\b|numara|sicil))")
_VKN_CONTEXT_WINDOW = 40
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", re.UNICODE)
_PHONE_RE = re.compile(
    r"(?<![\d.,])"
    r"(?P<prefix>(?:\+|00)[ ]?90[ .-]?\(?|0[ .-]?\(?|\()?"
    r"(?P<code>\d{3})\)?[ .-]?"
    r"\d{3}[ .-]?\d{2}[ .-]?\d{2}"
    r"(?!\d)"
)
_PLATE_RE = re.compile(r"(?<![\w.,])\d{2}[ \t]*[A-Z]{1,3}[ \t]*\d{2,4}(?![\w])")
_UNIT_TOKENS = frozenset(
    {"GB", "MB", "KB", "TB", "TL", "KG", "CM", "MM", "KM", "MG", "ML", "GR", "HZ", "USD", "EUR"}
)


def _find_iban(text: str) -> list[Span]:
    spans = []
    for m in _IBAN_RE.finditer(text):
        if is_valid_tr_iban(m.group()):
            spans.append(Span(m.start(), m.end(), Kind.IBAN, m.group(), normalize_iban(m.group())))
    return spans


def _find_tckn(text: str) -> list[Span]:
    spans = []
    for m in _TCKN_RE.finditer(text):
        if is_valid_tckn(m.group()):
            spans.append(Span(m.start(), m.end(), Kind.TCKN, m.group(), digits_only(m.group())))
    return spans


def _find_vkn(text: str) -> list[Span]:
    """A 10-digit checksum passes one random number in ten, so a nearby keyword is required."""
    spans = []
    for m in _VKN_RE.finditer(text):
        if not is_valid_vkn(m.group()):
            continue
        window = text[max(0, m.start() - _VKN_CONTEXT_WINDOW) : m.start()]
        if _VKN_CONTEXT_RE.search(window):
            spans.append(Span(m.start(), m.end(), Kind.VKN, m.group(), digits_only(m.group())))
    return spans


def _find_email(text: str) -> list[Span]:
    return [
        Span(m.start(), m.end(), Kind.EMAIL, m.group(), m.group().lower())
        for m in _EMAIL_RE.finditer(text)
    ]


def _find_phone(text: str) -> list[Span]:
    spans = []
    for m in _PHONE_RE.finditer(text):
        code = m.group("code")
        prefixed = bool(m.group("prefix"))
        # A bare 10-digit number is accepted for mobile prefixes only; a bare geographic
        # code is too easily an order number or a reference.
        if is_mobile_prefix(code) or (prefixed and is_area_code(code)):
            canonical = canonical_phone(m.group())
            spans.append(Span(m.start(), m.end(), Kind.PHONE, m.group(), canonical))
    return spans


def _find_plate(text: str) -> list[Span]:
    spans = []
    for m in _PLATE_RE.finditer(text):
        letters = "".join(c for c in m.group() if c.isalpha())
        # "16 GB 128" is a spec sheet; "16GB128" written solid is not how units are written.
        if (" " in m.group() and letters in _UNIT_TOKENS) or not is_valid_plate(m.group()):
            continue
        spans.append(Span(m.start(), m.end(), Kind.PLATE, m.group(), canonical_plate(m.group())))
    return spans


def _find_names(text: str) -> list[Span]:
    spans = []
    for start, end in find_name_spans(text):
        surface = text[start:end]
        spans.append(Span(start, end, Kind.NAME, surface, " ".join(tr_lower(surface).split())))
    return spans


def _resolve_overlaps(spans: list[Span]) -> list[Span]:
    ranked = sorted(spans, key=lambda s: (-(s.end - s.start), _PRIORITY[s.kind], s.start))
    kept: list[Span] = []
    for span in ranked:
        if all(span.end <= k.start or span.start >= k.end for k in kept):
            kept.append(span)
    return sorted(kept)


def detect(text: str) -> list[Span]:
    """Return non-overlapping personal-data spans in document order."""
    # Identifiers with a checksum take precedence over shape-only matches on the same digits.
    identifiers = _resolve_overlaps(_find_iban(text) + _find_tckn(text) + _find_vkn(text))
    others = _find_email(text) + _find_phone(text) + _find_plate(text) + _find_names(text)
    free = [s for s in others if all(s.end <= k.start or s.start >= k.end for k in identifiers)]
    return sorted(identifiers + _resolve_overlaps(free))
