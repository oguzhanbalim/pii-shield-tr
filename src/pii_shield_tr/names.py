"""Heuristic person-name detection for Turkish text.

There is no NER model here. A name is found by one of three signals: an explicit
label or title next to capitalised words, a small dictionary of common given names,
or a small dictionary of common surnames preceded by a capitalised word. Anything
outside those signals is missed, and the README's evaluation shows how much.
"""

from __future__ import annotations

import re
from collections.abc import Iterator

_UP = "A-ZÇĞİÖŞÜ"
_LOW = "a-zçğıöşü"
_TOKEN = rf"(?:[{_UP}][{_LOW}]+|[{_UP}]{{2,}})"
_NAME_RUN = rf"{_TOKEN}(?:[ \t]+{_TOKEN}){{0,2}}"


def tr_lower(text: str) -> str:
    return text.replace("İ", "i").replace("I", "ı").lower()


GIVEN_NAMES = frozenset(
    """
    ahmet mehmet mustafa ali hüseyin hasan ibrahim ismail osman yusuf murat ömer ramazan
    halil süleyman abdullah mahmut recep fatih kadir emre hakan adem kemal yaşar serkan
    orhan oğuzhan onur burak volkan gökhan cem tolga sinan selim tuncay erdem bülent
    levent uğur ufuk kerem koray mert berk arda efe ege emir kaan baran alper taner
    cengiz metin nihat ayhan turgut engin erkan vedat zafer ayşe fatma emine hatice
    zeynep elif meryem şerife sultan hanife merve özlem yasemin esra leyla büşra sevgi
    aysel hülya dilek gamze gül gülşen pınar tuğba ebru derya seda sibel burcu aslı
    ceren damla ece irem melike nur rabia selin songül şule tuba yeliz zehra aylin
    banu berna canan didem feride gizem hande işıl kübra nazlı neslihan nilgün sevim
    """.split()
)

# Also ordinary Turkish words: only treated as names next to a surname or title.
AMBIGUOUS_GIVEN = frozenset(
    """
    deniz umut güneş yıldız bahar can barış şeker kaya demir aslan ay sevgi nur gül sultan
    """.split()
)

SURNAMES = frozenset(
    """
    yılmaz kaya demir çelik şahin yıldız yıldırım öztürk aydın özdemir arslan doğan kılıç
    aslan çetin kara koç kurt özkan şimşek polat korkmaz özer erdoğan güneş bulut tekin
    avcı acar kaplan aksoy karaca güler sarı keskin tunç başaran bozkurt
    """.split()
)

_NOT_A_NAME_AFTER = frozenset(
    """
    caddesi cad sokak sokağı sok mahallesi mah bulvarı üniversitesi hastanesi okulu lisesi
    parkı köprüsü meydanı holding bankası limited anonim ilkokulu ortaokulu vakfı derneği
    stadyumu havalimanı camii kampüsü
    """.split()
)

_HONORIFIC_SUFFIXES = frozenset({"bey", "hanım", "beyefendi", "hanımefendi", "efendi"})
_NOT_A_NAME_WORDS = frozenset(
    """
    ve ile için bu şu adlı isimli türkiye ankara istanbul izmir bursa antalya adana konya
    pazartesi salı çarşamba perşembe cuma cumartesi pazar ocak şubat mart nisan mayıs haziran
    temmuz ağustos eylül ekim kasım aralık
    """.split()
)

_LABELS = (
    r"(?:ad[ıi]?[ \t]+soyad[ıi]?|ad[ıi]?[-/ ]soyad[ıi]?|isim[ \t]+soyisim|isim|ad[ıi]|"
    r"hasta(?:n[ıi]n)?[ \t]+ad[ıi]|müşteri(?:[ \t]+ad[ıi])?|gönderen|alıcı|yetkili|"
    r"sorumlu|başvuru[ \t]+sahibi|kart[ \t]+sahibi|veli|iletişim[ \t]+kişisi)"
)
_LABEL_RE = re.compile(rf"(?i:\b{_LABELS})[ \t]*[:=][ \t]*(?P<name>{_NAME_RUN})")
_INTRO_RE = re.compile(
    rf"(?i:\b(?:benim[ \t]+)?(?:ad[ıi]m|ismim)(?:[ \t]+da)?)[ \t]+(?P<name>{_NAME_RUN})"
)
_TITLE_RE = re.compile(
    rf"(?:\b(?:Sayın|Sn\.|Bay|Bayan|Dr\.|Prof\.|Doç\.|Av\.|Uzm\.|Op\.|Müh\.)[ \t]+)+"
    rf"(?P<name>{_NAME_RUN})"
)
_HONORIFIC_RE = re.compile(
    rf"(?P<name>{_NAME_RUN})[ \t]+(?:Bey|Hanım|Beyefendi|Hanımefendi)\b"
)
_TOKEN_RE = re.compile(_TOKEN)
# Lowercase names are only considered for a known given + known surname pair.
_LOWER_PAIR_RE = re.compile(rf"\b([{_LOW}]{{2,}})(?=[ \t]+([{_LOW}]{{2,}})\b)")


def _trim_run(text: str, start: int, end: int) -> tuple[int, int] | None:
    """Trim stopwords off the right of a name run; None when nothing is left."""
    tokens = list(_TOKEN_RE.finditer(text, start, end))
    keep_end = None
    for token in tokens:
        lowered = tr_lower(token.group())
        if lowered in _NOT_A_NAME_AFTER:
            return None
        if lowered in _HONORIFIC_SUFFIXES or lowered in _NOT_A_NAME_WORDS:
            break
        keep_end = token.end()
    return (start, keep_end) if keep_end is not None else None


def _dictionary_spans(text: str) -> Iterator[tuple[int, int]]:
    tokens = list(_TOKEN_RE.finditer(text))
    i = 0
    while i < len(tokens):
        token = tokens[i]
        lowered = tr_lower(token.group())
        follower = _adjacent(text, tokens, i)
        follower_lc = tr_lower(follower.group()) if follower else None
        is_name_word = lowered not in _NOT_A_NAME_WORDS

        if not is_name_word:
            i += 1
            continue
        if follower_lc in _NOT_A_NAME_AFTER:
            i += 2
            continue

        usable_follower = (
            follower is not None
            and follower_lc not in _HONORIFIC_SUFFIXES
            and follower_lc not in _NOT_A_NAME_WORDS
        )
        if lowered in GIVEN_NAMES or lowered in AMBIGUOUS_GIVEN:
            if usable_follower:
                last = i + 1
                # A double given name: "Ayşe Nur Yılmaz".
                second = _adjacent(text, tokens, last)
                if second is not None and tr_lower(second.group()) in _NOT_A_NAME_AFTER:
                    # "Mehmet Ali Bulvarı": the whole run names a place.
                    i = last + 2
                    continue
                if second is not None and (
                    tr_lower(follower.group()) in GIVEN_NAMES | AMBIGUOUS_GIVEN
                    and tr_lower(second.group()) not in _NOT_A_NAME_WORDS
                    and tr_lower(second.group()) not in _HONORIFIC_SUFFIXES
                ):
                    last += 1
                yield token.start(), tokens[last].end()
                i = last + 1
                continue
            if lowered not in AMBIGUOUS_GIVEN:
                yield token.span()
            i += 1
            continue
        if usable_follower and follower_lc in SURNAMES and follower_lc not in AMBIGUOUS_GIVEN:
            yield token.start(), follower.end()
            i += 2
            continue
        i += 1


def _adjacent(text: str, tokens: list[re.Match[str]], i: int) -> re.Match[str] | None:
    """The next token, only if separated from token i by plain spaces."""
    if i + 1 >= len(tokens):
        return None
    between = text[tokens[i].end() : tokens[i + 1].start()]
    return tokens[i + 1] if between and not between.strip(" \t") else None


def find_name_spans(text: str) -> list[tuple[int, int]]:
    """Return (start, end) character spans of likely person names. Spans may overlap."""
    spans: list[tuple[int, int]] = []
    for pattern in (_LABEL_RE, _INTRO_RE, _TITLE_RE, _HONORIFIC_RE):
        for match in pattern.finditer(text):
            trimmed = _trim_run(text, *match.span("name"))
            if trimmed is not None:
                spans.append(trimmed)
    spans.extend(_dictionary_spans(text))
    for match in _LOWER_PAIR_RE.finditer(text):
        if match.group(1) in GIVEN_NAMES and match.group(2) in SURNAMES:
            surname_end = text.index(match.group(2), match.end()) + len(match.group(2))
            spans.append((match.start(), surname_end))
    return spans
