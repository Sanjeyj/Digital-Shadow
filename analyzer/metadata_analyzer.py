"""
analyzer/metadata_analyzer.py
Extracts and evaluates document metadata from PDF and DOCX files.

SECURITY REQUIREMENTS:
- Uploaded content is NEVER executed.
- Files are processed in memory or from a secure temp path.
- The module only reads metadata fields; it never reads or returns file body text.
- Temporary files must be deleted by the caller after this module returns.
"""

from __future__ import annotations

import os
import re
from typing import Optional

from analyzer.patterns import SENSITIVE_FILENAME_KEYWORDS
from analyzer.recommendations import get_recommendation
from analyzer.risk_scoring import build_finding


def analyze_document_metadata(filepath: str, original_filename: str) -> list[dict]:
    """
    Extract and analyze metadata from a PDF or DOCX file.

    Args:
        filepath: Absolute path to the securely stored temp file.
        original_filename: The original filename supplied by the user.

    Returns:
        A list of finding dicts (may be empty).
    """
    findings: list[dict] = []

    # 1. Filename sensitivity check
    findings.extend(_check_filename(original_filename))

    # 2. Extension-based dispatch
    ext = os.path.splitext(original_filename)[1].lower()
    if ext == ".pdf":
        meta = _extract_pdf_metadata(filepath)
    elif ext == ".docx":
        meta = _extract_docx_metadata(filepath)
    else:
        meta = {}

    # 3. Analyze extracted metadata fields
    if meta:
        findings.extend(_check_author(meta))
        findings.extend(_check_software(meta))

    return findings


# ── Filename check ────────────────────────────────────────────────────────────

def _check_filename(filename: str) -> list[dict]:
    findings = []
    if SENSITIVE_FILENAME_KEYWORDS.search(filename):
        rec = get_recommendation("DOC_SENSITIVE_FILENAME")
        findings.append(
            build_finding(
                rule_id="DOC_SENSITIVE_FILENAME",
                title="Sensitive keyword in document filename",
                category="Sensitive Document Indicators",
                severity="medium",
                evidence=f"Filename: {filename}",
                explanation=(
                    "The document filename contains a term that suggests sensitive content "
                    "(e.g., password, medical, salary). Filenames are visible in directory "
                    "listings, email threads, and cloud storage UIs before a recipient "
                    "opens the file."
                ),
                consequence=(
                    "The nature of the document is disclosed to anyone who can view "
                    "the filename, which may draw unwanted attention."
                ),
                recommendation_action=rec["action"],
                recommendation_detail=rec["detail"],
            )
        )
    return findings


# ── Author metadata ───────────────────────────────────────────────────────────

def _check_author(meta: dict) -> list[dict]:
    findings = []
    author_fields = ["author", "creator", "last_modified_by", "dc:creator"]
    authors_found = []
    for field in author_fields:
        val = meta.get(field, "")
        if val and isinstance(val, str) and val.strip():
            authors_found.append(f"{field}: {val.strip()}")

    if authors_found:
        rec = get_recommendation("DOC_AUTHOR_METADATA")
        findings.append(
            build_finding(
                rule_id="DOC_AUTHOR_METADATA",
                title="Author / creator identity in document metadata",
                category="Sensitive Document Indicators",
                severity="medium",
                evidence="; ".join(authors_found),
                explanation=(
                    "The document's embedded metadata contains author or creator "
                    "name information. This data is not visible in the rendered "
                    "document but can be read by anyone with access to the file."
                ),
                consequence=(
                    "The real name or username of the document author may be revealed "
                    "to recipients, even if the document content is intended to be anonymous."
                ),
                recommendation_action=rec["action"],
                recommendation_detail=rec["detail"],
            )
        )
    return findings


# ── Software metadata ─────────────────────────────────────────────────────────

def _check_software(meta: dict) -> list[dict]:
    findings = []
    software_fields = ["producer", "creator_tool", "application", "dc:format"]
    software_found = []
    for field in software_fields:
        val = meta.get(field, "")
        if val and isinstance(val, str) and val.strip():
            software_found.append(f"{field}: {val.strip()}")

    if software_found:
        rec = get_recommendation("DOC_SOFTWARE_METADATA")
        findings.append(
            build_finding(
                rule_id="DOC_SOFTWARE_METADATA",
                title="Software / application version in document metadata",
                category="Sensitive Document Indicators",
                severity="low",
                evidence="; ".join(software_found),
                explanation=(
                    "The document's metadata includes the name and possibly version "
                    "of the software used to create it. Software version information "
                    "can be used in targeted attack research."
                ),
                consequence=(
                    "An attacker may use this information to identify known "
                    "vulnerabilities in the software version you use."
                ),
                recommendation_action=rec["action"],
                recommendation_detail=rec["detail"],
            )
        )
    return findings


# ── PDF extraction ────────────────────────────────────────────────────────────

def _extract_pdf_metadata(filepath: str) -> dict:
    """
    Extract PDF metadata using pypdf (preferred) or pdfminer as fallback.
    Returns a flat dict of field_name → value strings.
    Never returns body text.
    """
    meta: dict = {}
    try:
        import pypdf  # type: ignore
        with open(filepath, "rb") as f:
            reader = pypdf.PdfReader(f, strict=False)
        info = reader.metadata or {}
        for k, v in info.items():
            key = k.lstrip("/").lower()
            if isinstance(v, str):
                meta[key] = v
            elif hasattr(v, "__str__"):
                meta[key] = str(v)
        return meta
    except ImportError:
        pass
    except Exception:
        return {}

    # Fallback: pdfminer
    try:
        from pdfminer.high_level import extract_pages  # type: ignore
        from pdfminer.pdfparser import PDFParser
        from pdfminer.pdfdocument import PDFDocument

        with open(filepath, "rb") as f:
            parser = PDFParser(f)
            doc = PDFDocument(parser)
            for info_dict in doc.info:
                for k, v in info_dict.items():
                    key = k.lower()
                    if isinstance(v, bytes):
                        v = v.decode("utf-8", errors="replace")
                    meta[key] = str(v)
        return meta
    except Exception:
        return {}


# ── DOCX extraction ───────────────────────────────────────────────────────────

def _extract_docx_metadata(filepath: str) -> dict:
    """
    Extract DOCX core properties. Returns a flat dict. Never returns body text.
    """
    meta: dict = {}
    try:
        from docx import Document  # type: ignore
        doc = Document(filepath)
        props = doc.core_properties
        field_map = {
            "author": props.author,
            "last_modified_by": props.last_modified_by,
            "creator": props.author,          # same source, different label
            "application": getattr(props, "application", None),
            "created": str(props.created) if props.created else None,
            "modified": str(props.modified) if props.modified else None,
        }
        for k, v in field_map.items():
            if v and str(v).strip():
                meta[k] = str(v).strip()
        return meta
    except ImportError:
        return {}
    except Exception:
        return {}
