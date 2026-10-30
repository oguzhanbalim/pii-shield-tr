"""Seeded, fully synthetic test-set generator.

Every identifier is generated here at run time. Checksums are computed, so a generated
T.C. number or VKN is structurally valid and could coincide with a real one by chance;
none is taken from any real record. Email domains are reserved (RFC 2606 / RFC 6761).

Templates use {SLOT} placeholders. Some slots are labelled as personal data even though
the tool is not expected to catch them (mistyped IDs, names outside its dictionaries), so
the score reflects them instead of hiding them. Slots missing from GOLD_KIND are hard
negatives: values that look like personal data but are not.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass

from pii_shield_tr.names import tr_lower
from pii_shield_tr.validators import iban_check_digits, tckn_check_digits, vkn_check_digit

GIVEN = ["Ayşe", "Mehmet", "Zeynep", "Mustafa", "Elif", "Oğuzhan", "Fatma", "İbrahim", "Işıl",
         "Şule", "Gökhan", "Büşra", "Uğur", "Hülya", "Ömer", "Ceren"]
SURNAME = ["Yılmaz", "Kaya", "Demir", "Çelik", "Şahin", "Öztürk", "Aydın", "Arslan", "Doğan",
           "Koç", "Aksoy", "Karaca"]
# Deliberately absent from the package's dictionaries: measures the dictionary's reach.
UNSEEN_GIVEN = ["Ilgaz", "Bengisu", "Tolunay", "Mirza", "Nehir", "Çağan", "Defne", "Atlas",
                "Lavin", "Yağız", "Sarp", "Bade"]
UNSEEN_SURNAME = ["Tanrıverdi", "Gümüşoğlu", "Akyürek", "Dalgıç", "Ertuna", "Sezgintürk",
                  "Karabulut", "Özsoy", "Taşkıran", "Boyacıoğlu"]
AMBIGUOUS = ["Deniz", "Umut", "Güneş", "Barış", "Bahar"]


def gen_tckn(rng: random.Random) -> str:
    first = str(rng.randint(1, 9)) + "".join(str(rng.randint(0, 9)) for _ in range(8))
    return first + tckn_check_digits(first)


def gen_bad_tckn(rng: random.Random) -> str:
    value = gen_tckn(rng)
    return value[:-1] + str((int(value[-1]) + rng.randint(1, 9)) % 10)


def gen_vkn(rng: random.Random) -> str:
    first = "".join(str(rng.randint(0, 9)) for _ in range(9))
    return first + vkn_check_digit(first)


def gen_iban(rng: random.Random, spaced: bool = False) -> str:
    bban = "99999" + "0" + "".join(str(rng.randint(0, 9)) for _ in range(16))
    iban = f"TR{iban_check_digits(bban)}{bban}"
    return " ".join(iban[i : i + 4] for i in range(0, 26, 4)) if spaced else iban


def gen_bad_iban(rng: random.Random) -> str:
    iban = gen_iban(rng)
    last = str((int(iban[-1]) + rng.randint(1, 9)) % 10)
    return iban[:-1] + last


def gen_phone(rng: random.Random) -> str:
    code = rng.choice(["532", "505", "542", "555", "212", "312", "232"])
    a = f"{rng.randint(200, 999)}"
    b, c = f"{rng.randint(0, 99):02d}", f"{rng.randint(0, 99):02d}"
    if code[0] != "5":
        return rng.choice(
            [f"0{code} {a} {b} {c}", f"({code}) {a} {b} {c}", f"+90 {code} {a}{b}{c}"]
        )
    return rng.choice(
        [
            f"0{code} {a} {b} {c}",
            f"+90 {code} {a} {b} {c}",
            f"0{code}{a}{b}{c}",
            f"+90{code}{a}{b}{c}",
            f"{code} {a} {b} {c}",
            f"0 ({code}) {a}-{b}-{c}",
            f"0{code}.{a}.{b}.{c}",
            f"0090 {code} {a} {b}{c}",
        ]
    )


def _ascii(text: str) -> str:
    return tr_lower(text).translate(str.maketrans("çğıöşü", "cgiosu"))


def gen_email(rng: random.Random) -> str:
    user = _ascii(rng.choice(GIVEN)) + rng.choice([".", "_", ""]) + _ascii(rng.choice(SURNAME))
    domain = rng.choice(["example.com", "ornek.example", "posta.test", "mail.example.org"])
    return f"{user}{rng.randint(1, 99)}@{domain}"


def gen_plate(rng: random.Random) -> str:
    letters = "ABCDEFGHJKLMNPRSTUVYZ"
    province = f"{rng.randint(1, 81):02d}"
    n_letters, n_digits = rng.choice([(1, 4), (2, 3), (2, 4), (3, 2), (3, 3)])
    group = "".join(rng.choice(letters) for _ in range(n_letters))
    digits = "".join(str(rng.randint(1, 9)) for _ in range(n_digits))
    return rng.choice([f"{province} {group} {digits}", f"{province}{group}{digits}"])


def gen_name(rng: random.Random) -> str:
    return f"{rng.choice(GIVEN)} {rng.choice(SURNAME)}"


def gen_unseen_name(rng: random.Random) -> str:
    return f"{rng.choice(UNSEEN_GIVEN)} {rng.choice(UNSEEN_SURNAME)}"


def gen_given(rng: random.Random) -> str:
    return rng.choice(GIVEN)


GENERATORS = {
    "TCKN": gen_tckn,
    "VKN": gen_vkn,
    "IBAN": gen_iban,
    "IBAN_SPACED": lambda r: gen_iban(r, spaced=True),
    "TEL": gen_phone,
    "EPOSTA": gen_email,
    "PLAKA": gen_plate,
    "AD": gen_name,
    "AD_GIVEN": gen_given,
    "AD_UNSEEN": gen_unseen_name,
    "AD_UNSEEN_GIVEN": lambda r: r.choice(UNSEEN_GIVEN),
    "AD_AMBIGUOUS_ALONE": lambda r: r.choice(AMBIGUOUS),
    "AD_LOWER": lambda r: tr_lower(gen_name(r)),
    "AD_UPPER": lambda r: gen_name(r).replace("i", "İ").replace("ı", "I").upper(),
    "TCKN_TYPO": gen_bad_tckn,
    # Not personal data by label: values the tool should leave alone.
    "BAD_TCKN": gen_bad_tckn,
    "BAD_IBAN": gen_bad_iban,
    "ORDER": lambda r: str(r.randint(10**9, 10**10 - 1)),
    "NUM11": lambda r: "0" + str(r.randint(10**9, 10**10 - 1)),
}

# Slot name -> gold label. Slots absent from this map are hard negatives.
GOLD_KIND = {
    "TCKN": "TCKN", "TCKN_TYPO": "TCKN", "VKN": "VKN", "IBAN": "IBAN", "IBAN_SPACED": "IBAN",
    "TEL": "TEL", "EPOSTA": "EPOSTA", "PLAKA": "PLAKA", "AD": "AD", "AD_GIVEN": "AD",
    "AD_UNSEEN": "AD", "AD_UNSEEN_GIVEN": "AD", "AD_AMBIGUOUS_ALONE": "AD", "AD_LOWER": "AD",
    "AD_UPPER": "AD",
}

TEMPLATES = [
    # Identity numbers
    "T.C. Kimlik No: {TCKN}",
    "Başvuru sahibinin kimlik numarası {TCKN} olarak kaydedildi.",
    "TC: {TCKN}, doğum yılı 1987.",
    "Hasta dosyasına {TCKN} numaralı kimlik işlendi.",
    "TCKN {TCKN} sistemde bulunamadı, tekrar kontrol edin.",
    "Kimlik no yanlış girilmiş olabilir: {TCKN_TYPO}.",
    # Tax numbers
    "Vergi Kimlik No: {VKN}",
    "Firmanın VKN'si {VKN} olarak görünüyor.",
    "Fatura için vergi numarası {VKN} kullanıldı.",
    "Bu kaydın numarası {VKN} ama alan etiketi eksik.",
    # IBAN
    "Ödemeyi {IBAN} hesabına yapın.",
    "IBAN: {IBAN_SPACED}",
    "İade tutarı {IBAN_SPACED} numaralı hesaba aktarılacak.",
    "Kira için {IBAN}'a havale yaptım.",
    # Phones
    "Bana {TEL} numarasından ulaşabilirsiniz.",
    "Telefon: {TEL}",
    "Kargo görevlisi {TEL}'yi aradı ama açılmadı.",
    "Acil durumda {TEL} aransın.",
    # Email
    "E-posta adresim {EPOSTA}, oradan yazın.",
    "Faturayı {EPOSTA}'ya gönderdik.",
    "İletişim: {EPOSTA} / {TEL}",
    # Plates
    "Aracın plakası {PLAKA} olarak tutanağa geçti.",
    "{PLAKA} plakalı araç otoparkta kaldı.",
    "Plaka: {PLAKA}",
    # Names with explicit signal
    "Adı Soyadı: {AD}",
    "Ad Soyad: {AD_UNSEEN}",
    "Sayın {AD}, başvurunuz alındı.",
    "Sayın {AD_UNSEEN}, randevunuz onaylandı.",
    "Benim adım {AD_UNSEEN}, siparişimle ilgili yazıyorum.",
    "Dr. {AD} hastayı muayene etti.",
    "Av. {AD_UNSEEN} dilekçeyi hazırladı.",
    "{AD_GIVEN} Hanım dosyayı teslim etti.",
    "{AD_UNSEEN_GIVEN} Bey aradı, sizi soruyor.",
    "Müşteri: {AD_UPPER}",
    # Names in prose
    "{AD} dün ofise uğradı.",
    "Toplantıya {AD} ve {AD} katılacak.",
    "{AD}'ın dosyası eksik.",
    "Dün {AD_GIVEN} ile görüştüm, bugün dönecek.",
    "{AD_UPPER} ADLI KİŞİYE AİT BELGE TESLİM ALINDI.",
    # Names the heuristics are expected to struggle with
    "{AD_UNSEEN} dün ofise uğradı.",
    "Toplantı notlarını {AD_UNSEEN_GIVEN} ile paylaştım.",
    "kayıt {AD_LOWER} adına açılmış.",
    "Bu işi {AD_AMBIGUOUS_ALONE} halletti.",
    # Combined
    "{AD} ({TCKN}) için {TEL} numarasına SMS gönderildi.",
    "Alıcı: {AD}, IBAN: {IBAN_SPACED}, e-posta: {EPOSTA}",
    "{AD_UNSEEN} / {EPOSTA} / {TEL}",
    # Hard negatives: nothing here is personal data
    "Sipariş numaranız {ORDER} ile takip edilebilir.",
    "Geçersiz kimlik örneği: {BAD_TCKN}.",
    "Bu IBAN hatalı görünüyor: {BAD_IBAN}.",
    "Referans {NUM11} ile kayıtlı.",
    "Telefon 16 GB 128 GB seçenekleriyle satılıyor.",
    "Çınar Caddesi üzerindeki Mehmet Ali Bulvarı kapalı.",
    "Toplam tutar 1.250,75 TL, vade 30 gün.",
    "Toplantı 12.03.2031 tarihinde 14:30'da başlayacak.",
    "Örnek Üniversitesi ile Kurgu Üniversitesi ortak bildiri yayımladı.",
    "Deniz kenarında yürüdük, umut etmekten vazgeçmedik.",
    "Güneş bugün erken battı.",
    "Bahar geldi, Barış Parkı çok güzel.",
    "Kaya Sokak üzerinde yol çalışması var.",
    "Bugün Pazartesi, yarın Salı.",
    "Sürüm 3.12.4 yayımlandı, yapı numarası 2031100412.",
    "Rapor 2031 yılının ikinci çeyreğini kapsıyor.",
    "Ürün kodu 34 ABC değil, doğrusu 3400 olmalı.",
    "Merhaba, kargom nerede acaba?",
]

_SLOT = re.compile(r"\{([A-Z_0-9]+)\}")


@dataclass(frozen=True)
class Gold:
    start: int
    end: int
    kind: str
    slot: str
    text: str


@dataclass(frozen=True)
class Example:
    text: str
    gold: tuple[Gold, ...]
    template: str


def render(template: str, rng: random.Random) -> Example:
    out = []
    gold = []
    cursor = 0
    length = 0
    for match in _SLOT.finditer(template):
        literal = template[cursor : match.start()]
        out.append(literal)
        length += len(literal)
        slot = match.group(1)
        value = GENERATORS[slot](rng)
        if slot in GOLD_KIND:
            gold.append(Gold(length, length + len(value), GOLD_KIND[slot], slot, value))
        out.append(value)
        length += len(value)
        cursor = match.end()
    out.append(template[cursor:])
    return Example("".join(out), tuple(gold), template)


def generate(n_per_template: int = 20, seed: int = 2030) -> list[Example]:
    rng = random.Random(seed)
    return [render(t, rng) for t in TEMPLATES for _ in range(n_per_template)]
