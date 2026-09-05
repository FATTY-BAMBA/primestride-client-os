"""Stable intake orchestration helpers.

Keeps source manifests intact when inspections are refreshed and identifies which
processing engine produced a saved review payload. Deterministic table parsing
still lives in the v0.8 compatibility layer until that domain is migrated.
"""
from __future__ import annotations

import re

MANIFEST_PREFIX = "PS_SOURCE_VAULT_V1:"
DOMAIN_VERSION = "1.3.1"


def merge_notes_preserving_source(old_notes: str | None, new_notes: str | None) -> str | None:
    new_lines = [
        line for line in (new_notes or "").splitlines()
        if line and not line.startswith(MANIFEST_PREFIX)
    ]
    manifests = [
        line for line in (old_notes or "").splitlines()
        if line.startswith(MANIFEST_PREFIX)
    ]
    text = "\n".join(new_lines + manifests).strip()
    return text or None


def inspection_engine(notes: str | None, source: str | None) -> tuple[str, str] | None:
    text = f"{source or ''} {notes or ''}"
    if re.search(r"messy-data inspection|Local browser inspection|sheet=|mapped=", text, re.I):
        match = re.search(r"v(0\.8(?:\.\d+)?)", text, re.I)
        return "deterministic_inspection", (match.group(1) if match else "0.8.4")
    if re.search(r"AI multimodal|multimodal analysis|model=", text, re.I):
        match = re.search(r"v(0\.9(?:\.\d+)*)", text, re.I)
        return "multimodal_ai_review", (match.group(1) if match else "0.9.4.1")
    return None


# Historical aliases while release-numbered modules remain import-compatible.
_merge_notes_preserving_source = merge_notes_preserving_source
_inspection_engine = inspection_engine

__all__ = [
    "DOMAIN_VERSION",
    "MANIFEST_PREFIX",
    "merge_notes_preserving_source",
    "inspection_engine",
    "_merge_notes_preserving_source",
    "_inspection_engine",
]
