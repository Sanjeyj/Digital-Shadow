"""
analyzer/__init__.py
Package initializer. Exposes the top-level analysis API.
"""

from analyzer.exposure_engine import run_exposure_analysis
from analyzer.url_analyzer import analyze_urls
from analyzer.metadata_analyzer import analyze_document_metadata
from analyzer.risk_scoring import compute_score, build_finding

__all__ = [
    "run_exposure_analysis",
    "analyze_urls",
    "analyze_document_metadata",
    "compute_score",
    "build_finding",
]
