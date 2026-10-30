import json
import os
import random
import stat

from synth import gen_iban, gen_tckn, generate

from pii_shield_tr import Vault
from pii_shield_tr.cli import main
from pii_shield_tr.validators import canonical_phone


def test_round_trip_and_nothing_left_in_clear():
    rng = random.Random(20)
    tckn, iban = gen_tckn(rng), gen_iban(rng, spaced=True)
    text = f"Adı Soyadı: Elif Kaya, kimlik {tckn}, IBAN: {iban}, e-posta elif@ornek.example"
    vault = Vault()
    masked = vault.shield(text)
    assert tckn not in masked and iban not in masked and "Elif" not in masked
    assert "elif@" not in masked
    assert masked == (
        "Adı Soyadı: [AD_1], kimlik [TCKN_1], IBAN: [IBAN_1], e-posta [EPOSTA_1]"
    )
    assert vault.restore(masked) == text


def test_placeholders_stable_across_calls_and_spellings():
    vault = Vault()
    first = vault.shield("Ara: 0532 123 45 67")
    second = vault.shield("Numara +90 532 123 45 67 ve 0212 123 45 67")
    assert first == "Ara: [TEL_1]"
    assert second == "Numara [TEL_1] ve [TEL_2]"
    assert canonical_phone("+90 532 123 45 67") == canonical_phone("0532 123 45 67")
    # First spelling seen is the one restored.
    assert vault.restore("[TEL_1]") == "0532 123 45 67"


def test_name_identity_is_case_insensitive_turkish():
    vault = Vault()
    assert vault.shield("Sayın Işıl Yılmaz") == "Sayın [AD_1]"
    assert vault.shield("SAYIN yok, IŞIL YILMAZ aradı") == "SAYIN yok, [AD_1] aradı"


def test_restore_handles_suffixes_and_model_reformatting():
    vault = Vault()
    vault.shield("Sayın Elif Kaya")
    assert vault.restore("[AD_1]'nın başvurusu") == "Elif Kaya'nın başvurusu"
    assert vault.restore("[ ad_1 ] onaylandı") == "Elif Kaya onaylandı"


def test_unknown_placeholders_reported_and_left_alone():
    vault = Vault()
    vault.shield("Sayın Elif Kaya")
    reply = "[AD_1] ve [AD_7] geldi"
    assert vault.unknown_placeholders(reply) == ["[AD_7]"]
    assert vault.restore(reply) == "Elif Kaya ve [AD_7] geldi"


def test_literal_placeholder_in_input_does_not_collide():
    vault = Vault()
    text = "Şablonda [TEL_1] yazıyor, gerçek numara 0532 123 45 67"
    masked = vault.shield(text)
    assert masked == "Şablonda [TEL_1] yazıyor, gerçek numara [TEL_2]"
    assert vault.restore(masked) == text


def test_vault_persistence_is_private_and_lossless(tmp_path):
    path = tmp_path / "vault.json"
    vault = Vault()
    masked = vault.shield("Sayın Elif Kaya, 0532 123 45 67")
    vault.save(path)
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
    loaded = Vault.load(path)
    assert loaded.restore(masked) == "Sayın Elif Kaya, 0532 123 45 67"
    assert loaded.shield("0532 123 45 67 ve 0212 123 45 67") == "[TEL_1] ve [TEL_2]"


def test_round_trip_on_the_whole_synthetic_set():
    # One vault per sentence: within a sentence the same value could appear in two spellings.
    for example in generate(n_per_template=3, seed=99):
        vault = Vault()
        assert vault.restore(vault.shield(example.text)) == example.text


def test_cli_shield_restore_detect(tmp_path, capsys):
    source = tmp_path / "in.txt"
    source.write_text("Sayın Elif Kaya, 0532 123 45 67", encoding="utf-8")
    vault_path = tmp_path / "v.json"

    assert main(["shield", str(source), "--vault", str(vault_path)]) == 0
    masked = capsys.readouterr().out
    assert masked == "Sayın [AD_1], [TEL_1]"

    reply = tmp_path / "reply.txt"
    reply.write_text("[AD_1] bilgilendirildi", encoding="utf-8")
    assert main(["restore", str(reply), "--vault", str(vault_path)]) == 0
    assert capsys.readouterr().out == "Elif Kaya bilgilendirildi"

    assert main(["detect", str(source)]) == 0
    rows = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [r["kind"] for r in rows] == ["AD", "TEL"]

    reply.write_text("[AD_9] kim?", encoding="utf-8")
    assert main(["restore", str(reply), "--vault", str(vault_path)]) == 2
