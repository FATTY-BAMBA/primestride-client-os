"""Stable readiness domain."""

from .router import install_readiness_routes
from .service import build_readiness_projection

__all__ = ["install_readiness_routes", "build_readiness_projection"]
