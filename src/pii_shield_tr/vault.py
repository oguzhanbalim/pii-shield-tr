"""Reversible local mapping between personal values and stable placeholders."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from .detect import Kind, Span, detect

_KINDS = "|".join(k.value for k in Kind)
_PLACEHOLDER_RE = re.compile(rf"\[\s*({_KINDS})_(\d+)\s*\]", re.IGNORECASE)


class Vault:
    """Holds the placeholder mapping for one conversation or document set.

    The same value gets the same placeholder across calls, including when it is written
    differently ('0532 ...' and '+90532...' are one phone). `restore` writes back the
    first spelling seen. The vault contains the real data: keep it local.
    """

    def __init__(self) -> None:
        self._by_key: dict[tuple[str, str], str] = {}
        self._originals: dict[str, str] = {}
        self._counters: dict[str, int] = {}

    def __len__(self) -> int:
        return len(self._originals)

    def _placeholder_for(self, span: Span, reserved: set[str]) -> str:
        key = (span.kind.value, span.canonical)
        existing = self._by_key.get(key)
        if existing is not None:
            return existing
        count = self._counters.get(span.kind.value, 0)
        while True:
            count += 1
            placeholder = f"[{span.kind.value}_{count}]"
            # Text that already looks like a placeholder must not collide with a real one.
            if placeholder not in reserved:
                break
        self._counters[span.kind.value] = count
        self._by_key[key] = placeholder
        self._originals[placeholder] = span.text
        return placeholder

    def shield(self, text: str) -> str:
        """Replace detected personal data in `text` with placeholders."""
        reserved = {m.group().upper() for m in _PLACEHOLDER_RE.finditer(text)}
        out: list[str] = []
        cursor = 0
        for span in detect(text):
            out.append(text[cursor : span.start])
            out.append(self._placeholder_for(span, reserved))
            cursor = span.end
        out.append(text[cursor:])
        return "".join(out)

    def restore(self, text: str) -> str:
        """Put original values back. Tolerates case and padding changes a model may introduce."""

        def replace(match: re.Match[str]) -> str:
            key = f"[{match.group(1).upper()}_{match.group(2)}]"
            return self._originals.get(key, match.group())

        return _PLACEHOLDER_RE.sub(replace, text)

    def unknown_placeholders(self, text: str) -> list[str]:
        """Placeholder-shaped strings in `text` this vault never issued (e.g. model inventions)."""
        found = []
        for match in _PLACEHOLDER_RE.finditer(text):
            key = f"[{match.group(1).upper()}_{match.group(2)}]"
            if key not in self._originals:
                found.append(match.group())
        return found

    def to_dict(self) -> dict[str, object]:
        return {
            "version": 1,
            "entries": [
                {"kind": kind, "canonical": canonical, "placeholder": ph,
                 "original": self._originals[ph]}
                for (kind, canonical), ph in self._by_key.items()
            ],
            "counters": self._counters,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Vault:
        vault = cls()
        for entry in data["entries"]:
            vault._by_key[(entry["kind"], entry["canonical"])] = entry["placeholder"]
            vault._originals[entry["placeholder"]] = entry["original"]
        vault._counters = dict(data["counters"])
        return vault

    def save(self, path: str | Path) -> None:
        """Write the mapping as JSON. Created with mode 0600 because it holds the real values."""
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(self.to_dict(), handle, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path: str | Path) -> Vault:
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
