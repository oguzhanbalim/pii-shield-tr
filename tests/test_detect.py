import random

import pytest
from synth import gen_bad_tckn, gen_iban, gen_tckn, gen_vkn

from pii_shield_tr import Kind, detect
from pii_shield_tr.validators import vkn_check_digit


def kinds(text):
    return [(s.kind, s.text) for s in detect(text)]


def test_tckn_found_only_with_valid_checksum():
    rng = random.Random(10)
    good, bad = gen_tckn(rng), gen_bad_tckn(rng)
    assert kinds(f"Kimlik: {good}") == [(Kind.TCKN, good)]
    assert kinds(f"Kimlik: {bad}") == []


def test_grouped_tckn():
    rng = random.Random(11)
    v = gen_tckn(rng)
    spaced = f"{v[:3]} {v[3:6]} {v[6:9]} {v[9:]}"
    assert kinds(f"No {spaced} kayıtlı") == [(Kind.TCKN, spaced)]


def test_vkn_requires_context():
    rng = random.Random(12)
    v = gen_vkn(rng)
    while v[0] == "5":  # would also read as a mobile number without context
        v = gen_vkn(rng)
    assert kinds(f"Vergi Kimlik No: {v}") == [(Kind.VKN, v)]
    assert kinds(f"Numara {v} kayıtlı") == []


def test_vkn_beats_phone_when_labelled():
    v = "532123456" + vkn_check_digit("532123456")
    assert kinds(f"VKN: {v}") == [(Kind.VKN, v)]


def test_iban_spaced_and_compact():
    rng = random.Random(13)
    compact = gen_iban(rng)
    spaced = gen_iban(rng, spaced=True)
    assert kinds(f"Hesap {compact}.") == [(Kind.IBAN, compact)]
    assert kinds(f"Hesap {spaced}.") == [(Kind.IBAN, spaced)]


def test_iban_digits_are_not_also_reported_as_phone_or_tckn():
    rng = random.Random(14)
    assert [s.kind for s in detect(f"IBAN {gen_iban(rng, spaced=True)}")] == [Kind.IBAN]


@pytest.mark.parametrize(
    "text",
    ["Bana 0532 123 45 67 numarasından", "+90 216 123 45 67 ofis", "(312) 444 55 66 santral"],
)
def test_phones(text):
    assert [s.kind for s in detect(text)] == [Kind.PHONE]


@pytest.mark.parametrize(
    "text",
    ["Sipariş 2121234567 kapandı.", "Toplam 1.250,75 TL", "Tarih 12.03.2031", "Sürüm 3.12.4"],
)
def test_numbers_that_are_not_phones(text):
    assert detect(text) == []


def test_email_stops_before_turkish_suffix():
    assert kinds("Faturayı ayse@ornek.example'a yolladık") == [(Kind.EMAIL, "ayse@ornek.example")]


def test_plate_vs_spec_sheet():
    assert kinds("34 ABC 123 plakalı") == [(Kind.PLATE, "34 ABC 123")]
    assert kinds("16 GB 128 GB seçenekleri") == []


@pytest.mark.parametrize(
    ("text", "name"),
    [
        ("Adı Soyadı: Bengisu Ertuna", "Bengisu Ertuna"),
        ("Sayın Ilgaz Tanrıverdi, merhaba", "Ilgaz Tanrıverdi"),
        ("Benim adım Sarp Dalgıç, yazıyorum", "Sarp Dalgıç"),
        ("Dr. Nehir Özsoy geldi", "Nehir Özsoy"),
        ("Ayşe Hanım geldi", "Ayşe"),
        ("Tolunay Bey aradı", "Tolunay"),
        ("Mehmet Yılmaz'ın dosyası", "Mehmet Yılmaz"),
        ("İBRAHİM ÇELİK ADLI KİŞİ", "İBRAHİM ÇELİK"),
        ("Dün Zeynep ile görüştüm", "Zeynep"),
        ("Ayşe Nur Yılmaz aradı", "Ayşe Nur Yılmaz"),
        ("kayıt gökhan demir adına açılmış", "gökhan demir"),
    ],
)
def test_names(text, name):
    assert kinds(text) == [(Kind.NAME, name)]


@pytest.mark.parametrize(
    "text",
    [
        "Mustafa Kemal Bulvarı kapalı.",
        "Atatürk Caddesi kapalı.",
        "Hacettepe Üniversitesi bildiri yayımladı.",
        "Deniz kenarında yürüdük.",
        "Güneş erken battı.",
        "Kaya Sokak üzerinde çalışma var.",
        "Bugün Pazartesi, yarın Salı.",
    ],
)
def test_not_names(text):
    assert detect(text) == []


def test_spans_are_ordered_and_disjoint():
    rng = random.Random(15)
    text = f"Alıcı: Elif Kaya, {gen_tckn(rng)}, {gen_iban(rng, spaced=True)}, 0532 123 45 67"
    spans = detect(text)
    assert [s.kind for s in spans] == [Kind.NAME, Kind.TCKN, Kind.IBAN, Kind.PHONE]
    assert all(a.end <= b.start for a, b in zip(spans, spans[1:], strict=False))
