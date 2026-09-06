"""Stable intake orchestration domain for PrimeStride Client OS."""

from .router import install_intake_routes
from .service import inspection_engine, merge_notes_preserving_source

__all__ = ["install_intake_routes", "inspection_engine", "merge_notes_preserving_source"]
