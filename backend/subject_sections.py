"""Detect exam-paper subject sections in PDFs (any layout, not one publisher).

Upload form subjects are canonical keys. PDFs may spell them differently
(Maths vs Mathematics, Chem vs Chemistry, etc.). Section headers vary, e.g.:

  Physics - Section A (MCQ)
  Section B: Chemistry
  Mathematics Part I
"""

from __future__ import annotations

import re
from typing import Any

# Canonical names must match the upload form (security.validate_subject).
SUBJECT_SECTION_ALIASES: dict[str, tuple[str, ...]] = {
    "Physics": ("physics", "phy"),
    "Chemistry": ("chemistry", "chem"),
    "Mathematics": ("mathematics", "maths", "math", "mths"),
}

CANONICAL_SUBJECTS = frozenset(SUBJECT_SECTION_ALIASES.keys())


def _alias_lookup() -> dict[str, str]:
    out: dict[str, str] = {}
    for canonical, aliases in SUBJECT_SECTION_ALIASES.items():
        out[canonical.lower()] = canonical
        for alias in aliases:
            out[alias.lower()] = canonical
    return out


_ALIAS_LOOKUP: dict[str, str] | None = None


def canonical_subject(label: str) -> str | None:
    """Map a PDF header fragment to Physics / Chemistry / Mathematics."""
    global _ALIAS_LOOKUP
    if _ALIAS_LOOKUP is None:
        _ALIAS_LOOKUP = _alias_lookup()
    return _ALIAS_LOOKUP.get(label.strip().lower())


def _subject_regex_fragment() -> str:
    """Alternation of all known subject spellings (longest match first)."""
    names: list[str] = []
    for canonical, aliases in SUBJECT_SECTION_ALIASES.items():
        names.append(canonical)
        names.extend(aliases)
    names = sorted({n for n in names if n}, key=len, reverse=True)
    return "(?:" + "|".join(re.escape(n) for n in names) + ")"


def _section_header_patterns() -> list[re.Pattern[str]]:
    """Patterns for common Indian / international exam PDF section titles."""
    subj = _subject_regex_fragment()
    return [
        # Physics - Section A (MCQ)   /   Maths - Section B
        re.compile(rf"({subj})\s*[-–:]\s*Section\s+", re.IGNORECASE),
        # Physics Section A   /   CHEMISTRY SECTION 1
        re.compile(rf"\b({subj})\s+Section\s+", re.IGNORECASE),
        # Section A: Physics   /   Section 1 - Chemistry
        re.compile(
            rf"Section\s+[A-Z0-9][A-Z0-9.\s]*\s*[-–:]\s*({subj})\b",
            re.IGNORECASE,
        ),
        # Physics Part I   /   Mathematics - Part 2
        re.compile(rf"\b({subj})\s*[-–:]\s*Part\s+", re.IGNORECASE),
        re.compile(
            rf"\bPart\s+[A-Z0-9][A-Z0-9.\s]*\s*[-–:]\s*({subj})\b",
            re.IGNORECASE,
        ),
        # PHYSICS (MCQ)   /   Chemistry (Numeric)  — parenthetical block
        re.compile(
            rf"\b({subj})\s*\(\s*(?:MCQ|Numeric|Theory|Objective)[^)]*\)",
            re.IGNORECASE,
        ),
    ]


_SECTION_PATTERNS: list[re.Pattern[str]] | None = None


def _patterns() -> list[re.Pattern[str]]:
    global _SECTION_PATTERNS
    if _SECTION_PATTERNS is None:
        _SECTION_PATTERNS = _section_header_patterns()
    return _SECTION_PATTERNS


def detect_section_markers(doc: Any) -> list[tuple[int, str]]:
    """``(page_index, canonical_subject)`` for each section header, in order."""
    markers: list[tuple[int, str]] = []
    seen: set[tuple[int, str]] = set()
    for page_i in range(len(doc)):
        text = doc[page_i].get_text()
        for pattern in _patterns():
            for m in pattern.finditer(text):
                canonical = canonical_subject(m.group(1))
                if not canonical:
                    continue
                key = (page_i, canonical)
                if key in seen:
                    continue
                seen.add(key)
                markers.append(key)
    markers.sort(key=lambda x: x[0])
    return markers


def page_indices_for_subject(doc: Any, job_subject: str) -> list[int] | None:
    """0-based pages to extract for the uploaded subject.

    ``None`` — no section headers detected; caller should process the whole PDF.
    ``[]`` — headers exist but none match ``job_subject``.
    """
    job_subject = (job_subject or "").strip()
    if job_subject not in CANONICAL_SUBJECTS:
        return None

    markers = detect_section_markers(doc)
    if not markers:
        return None

    pages: set[int] = set()
    for idx, (page_i, subj) in enumerate(markers):
        if subj != job_subject:
            continue
        start = page_i
        end = len(doc) - 1
        for j in range(idx + 1, len(markers)):
            next_page, next_subj = markers[j]
            if next_subj != job_subject:
                end = next_page - 1
                break
        for p in range(start, end + 1):
            pages.add(p)

    return sorted(pages)
