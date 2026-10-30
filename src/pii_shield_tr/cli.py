"""Command line: pii-shield shield|restore|detect. Reads a file or stdin, writes stdout."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .detect import detect
from .vault import Vault


def _read(path: str | None) -> str:
    if path in (None, "-"):
        return sys.stdin.read()
    return Path(path).read_text(encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pii-shield", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    shield = sub.add_parser("shield", help="replace personal data with placeholders")
    shield.add_argument("input", nargs="?", help="input file, or stdin")
    shield.add_argument("--vault", required=True, help="JSON mapping file (created or extended)")

    restore = sub.add_parser("restore", help="put original values back")
    restore.add_argument("input", nargs="?", help="input file, or stdin")
    restore.add_argument("--vault", required=True, help="JSON mapping file")

    find = sub.add_parser("detect", help="print detected spans as JSON lines, change nothing")
    find.add_argument("input", nargs="?", help="input file, or stdin")

    args = parser.parse_args(argv)
    text = _read(args.input)

    if args.command == "detect":
        for span in detect(text):
            print(
                json.dumps(
                    {"start": span.start, "end": span.end, "kind": span.kind.value,
                     "text": span.text},
                    ensure_ascii=False,
                )
            )
        return 0

    vault_path = Path(args.vault)
    if args.command == "shield":
        vault = Vault.load(vault_path) if vault_path.exists() else Vault()
        sys.stdout.write(vault.shield(text))
        vault.save(vault_path)
        return 0

    vault = Vault.load(vault_path)
    sys.stdout.write(vault.restore(text))
    unknown = vault.unknown_placeholders(text)
    if unknown:
        print(f"warning: placeholders not in vault: {', '.join(unknown)}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
