# pii-shield-tr

Swap Turkish personal data for placeholders before the text leaves your machine, and swap it back when the answer returns.

Generic PII tools don't know that a T.C. number has two check digits or that `IŞIL` lowercases to `ışıl`. This one validates Turkish identifiers by their checksums, so a random 11-digit number stays in the text and a real-shaped one does not, and it keeps a local reversible mapping so the LLM never needs the raw values.

**This is not a compliance guarantee or legal advice.** It is a best-effort filter with measured misses (below). Masked text can still identify someone through context. Using it does not by itself satisfy KVKK, GDPR or any other regulation.

No dependencies. No model calls. No network.

## Quickstart

```
pip install -e .
pii-shield shield examples/sample.txt --vault /tmp/vault.json
```

Every identifier in `examples/` is generated (see [Evaluation](#evaluation)). Output:

```
Adı Soyadı: [AD_1]
T.C. Kimlik No: [TCKN_1]
Merhaba, iadem için IBAN: [IBAN_1]. Bana [TEL_1]'den veya [EPOSTA_1] adresinden ulaşın.
Aracım [PLAKA_1] plakalı. Firma vergi numarası [VKN_1]. [AD_2] Hanım olarak ben takip edeceğim.
```

Send that to the model. Restore what comes back:

```
$ cat examples/reply.txt
Sayın [AD_1], iadeniz [IBAN_1] hesabına yapılacak. Sorun olursa [TEL_1] numarasını arayacağız.

$ pii-shield restore examples/reply.txt --vault /tmp/vault.json
Sayın Elif Kaya, iadeniz TR64 9999 9029 4196 0837 8653 88 hesabına yapılacak. Sorun olursa 0532 123 45 67 numarasını arayacağız.
```

As a library:

```python
from pii_shield_tr import Vault

vault = Vault()                          # one vault per conversation
masked = vault.shield(user_text)         # same value, same placeholder, across calls
reply = call_your_llm(masked)
vault.unknown_placeholders(reply)        # placeholders the model made up
final = vault.restore(reply)             # tolerates "[ ad_1 ]"; keeps Turkish suffixes: [AD_1]'nın
vault.save("vault.json")                 # file mode 0600: it holds the real data
```

## What it detects

| Placeholder | What | How |
|---|---|---|
| `TCKN` | T.C. identity number | 11 digits, both check digits verified; compact or grouped |
| `IBAN` | TR IBAN | 26 characters, ISO 13616 mod-97 |
| `VKN` | Tax number | 10 digits, check digit, **and** a keyword (`VKN`, `vergi no`...) in the previous 40 characters |
| `TEL` | Turkish phone | Numbering plan check; `+90`, `0090`, `0`, parens, dots, dashes |
| `EPOSTA` | Email | Regex; stops before suffixes like `'a` |
| `PLAKA` | Vehicle plate | Province 01-81 and issued letter/digit shapes; rejects `16 GB 128` |
| `AD` | Person name | Heuristics only: labels (`Adı Soyadı:`), titles (`Sayın`, `Dr.`), `Hanım`/`Bey`, `adım ...`, plus small given-name and surname dictionaries |

The VKN check digit passes one random 10-digit number in ten, so the keyword is required. Without it, 10% of order numbers would be masked.

The same value gets one placeholder however it is spelled: `0532 123 45 67` and `+90 532 123 45 67` are both `[TEL_1]`, and `IŞIL YILMAZ` and `Işıl Yılmaz` are one name.

## Evaluation

```
python evaluation/run_eval.py
```

```
Synthetic set: 64 templates x 20 = 1280 sentences, seed 2030. Self-written; exact span and kind required.

kind      gold    tp    fp    fn  precision  recall
AD         460   379     0    81      1.000   0.824
EPOSTA     100   100     0     0      1.000   1.000
IBAN       100   100     0     0      1.000   1.000
PLAKA       60    58     0     2      1.000   0.967
TCKN       140   120     0    20      1.000   0.857
TEL        140   140     5     0      0.966   1.000
VKN         80    60     0    20      1.000   0.750
ALL       1080   957     5   123      0.995   0.886

Recall by slot:
  AD                    180/180    1.000  (AD)
  AD_AMBIGUOUS_ALONE      0/20     0.000  (AD)
  AD_GIVEN               40/40     1.000  (AD)
  AD_LOWER               19/20     0.950  (AD)
  AD_UNSEEN              80/120    0.667  (AD)
  AD_UNSEEN_GIVEN        20/40     0.500  (AD)
  AD_UPPER               40/40     1.000  (AD)
  EPOSTA                100/100    1.000  (EPOSTA)
  IBAN                   40/40     1.000  (IBAN)
  IBAN_SPACED            60/60     1.000  (IBAN)
  PLAKA                  58/60     0.967  (PLAKA)
  TCKN                  120/120    1.000  (TCKN)
  TCKN_TYPO               0/20     0.000  (TCKN)
  TEL                   140/140    1.000  (TEL)
  VKN                    60/80     0.750  (VKN)
```

Read these numbers for what they are:

- **I wrote the templates, the generator and the detector.** The set is fully synthetic, and I fixed three bugs it exposed before taking this run. It says the code does what I designed it to do. It does not estimate performance on real text, where precision and recall will both be lower. The precision of 1.000 on names mainly reflects which hard negatives I thought of; see the false positives under Limits.
- Some gold labels are there to be missed: mistyped IDs (`TCKN_TYPO`), unlabelled tax numbers, names outside the dictionaries, and names that are also ordinary words.
- The set is 64 templates, so 1280 sentences are far from 1280 independent tests.

All identifiers are generated at run time from seeded randomness; no real record was used. A generated number with a correct checksum could coincide with a real one by chance. Email domains are reserved example domains and the IBAN bank code is a made-up `99999`. The one exception is a textbook non-Turkish specimen IBAN in `tests/test_validators.py` that checks the mod-97 arithmetic. The VKN algorithm follows the commonly published description; I did not validate it against an official source.

## Limits

- **Mistyped identifiers leak.** A T.C. number with a wrong check digit is not masked (`TCKN_TYPO` above), and neither is an invalid IBAN. That is the cost of checksum precision.
- **Names are the weak spot.** With no label or title, an unknown name passes through: `Nehir Ertuna dün ofise uğradı.` is unchanged. Names that are also words (`Deniz`, `Umut`) are skipped when alone.
- **Names produce false positives.** Actual output: `Yusuf Suresi okundu.` masks `Yusuf Suresi`; `Mert Kozmetik indirim yaptı.` masks `Mert Kozmetik`. Public figures get masked as well.
- **Name variants are not linked.** `Elif Kaya` and `Elif Hanım` become `[AD_1]` and `[AD_2]`, visible in the quickstart.
- **`restore` returns the first spelling seen.** If one number appears in two spellings, restoring yields the first for both, so the round trip is exact only when each value has one spelling.
- A tax number without its keyword is not found; a bare number starting with a mobile prefix reads as a phone number, which accounts for the `TEL` false positives on order numbers.
- Not detected: addresses, dates of birth, health data, passport numbers, card numbers, foreign IDs, or anything identifying through context ("the mayor's daughter").
- Obfuscated text (`0 5 3 2 ...`, zero-width characters, spelled-out digits) is not handled.
- The vault file holds the real values in plain JSON. It is created with mode 0600 and is not encrypted.
- Tested locally on Python 3.12 only; CI is configured for 3.11 and 3.12 but this repository has not been pushed.

## License

MIT
