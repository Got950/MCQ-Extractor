"""Section detection works for any subject, not one hard-coded PDF."""

from __future__ import annotations

from pathlib import Path

import pymupdf as fitz
import pytest

from subject_sections import (
    detect_section_markers,
    page_indices_for_subject,
)

_EXAMBRO_SAMPLE = Path(
    r"d:\Cloudus Infotech\ExamBro_Allqsformat_20th_May_2026_English_Solution 2.pdf"
)


def _doc_with_text(pages: list[str]):
    doc = fitz.open()
    for text in pages:
        page = doc.new_page()
        page.insert_text((72, 72), text, fontsize=11)
    return doc


@pytest.mark.skipif(not _EXAMBRO_SAMPLE.is_file(), reason="local sample PDF not present")
def test_exambro_style_headers():
  doc = fitz.open(_EXAMBRO_SAMPLE)
  try:
    physics = page_indices_for_subject(doc, "Physics")
    chem = page_indices_for_subject(doc, "Chemistry")
    maths = page_indices_for_subject(doc, "Mathematics")
    assert physics is not None and len(physics) > 0
    assert chem is not None and len(chem) > 0
    assert maths is not None and len(maths) > 0
    assert 0 not in physics  # page 1 is Maths-only in this paper
  finally:
    doc.close()


def test_alternate_header_formats():
    doc = _doc_with_text(
        [
            "Biology intro\n",
            "Chemistry Section A (MCQ)\nQ1...",
            "Section B: Physics\nQ2...",
            "Mathematics - Part II\nQ3...",
        ]
    )
    try:
        markers = detect_section_markers(doc)
        subjects = {s for _, s in markers}
        assert "Chemistry" in subjects
        assert "Physics" in subjects
        assert "Mathematics" in subjects

        chem_pages = page_indices_for_subject(doc, "Chemistry")
        phys_pages = page_indices_for_subject(doc, "Physics")
        assert chem_pages == [1]
        assert phys_pages == [2]
    finally:
        doc.close()


def test_no_headers_means_full_pdf():
    doc = _doc_with_text(["Chapter 1\nSingle subject MCQ paper\n"])
    try:
        assert page_indices_for_subject(doc, "Physics") is None
    finally:
        doc.close()
