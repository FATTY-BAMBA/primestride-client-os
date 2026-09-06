"""PrimeStride Client OS platform bootstrap.

Central runtime registry for the previously version-stacked implementation.

v1.3.3 completes the deterministic-intake migration: production routing and
readiness scoring no longer depend on v082 modules. Those files remain thin
compatibility adapters while stable intake/readiness/workspace domains own the
validated behavior.
"""
from __future__ import annotations

import time
from importlib import import_module
from typing import Callable

from fastapi import FastAPI, Request

PLATFORM_VERSION = "1.3.3"

# Order is behavioral: several newer routes intentionally shadow prototype
# routes, and Starlette resolves the first matching route.
INSTALLERS: tuple[tuple[str, str, str], ...] = (
    ("lineage", ".lineage.router", "install_lineage_routes"),
    ("job_recovery", ".jobs.router", "install_job_routes"),
    ("readiness", ".readiness.router", "install_readiness_routes"),
    ("source_lifecycle", ".lifecycle.router", "install_lifecycle_routes"),
    ("intake", ".intake.router", "install_intake_routes"),
    ("storage", ".storage.router", "install_storage_routes"),
    ("workspace", ".workspace.router", "install_workspace_routes"),
    ("multimodal_background", ".v093_ai", "install_v093_ai"),
    ("multimodal_section_mapping", ".v092_ai", "install_v092_ai"),
    ("multimodal_mapping", ".v091_ai", "install_v091_ai"),
    ("multimodal_base", ".v09_ai", "install_v09_ai"),
)


def _load_installer(module_name: str, function_name: str) -> Callable[[FastAPI], None]:
    module = import_module(module_name, package=__package__)
    installer = getattr(module, function_name)
    return installer


def install_platform_extensions(app: FastAPI) -> None:
    """Install every Client OS runtime extension exactly once, in route order."""
    if getattr(app.state, "ps_platform_extensions_installed", False):
        return

    # Preserve the useful v0.8 Server-Timing signal, but report the actual
    # platform version instead of a historical intake-runtime version.
    @app.middleware("http")
    async def primestride_timing(request: Request, call_next):
        started = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - started) * 1000
        response.headers["Server-Timing"] = f"primestride;dur={elapsed_ms:.1f}"
        response.headers["X-PrimeStride-Version"] = PLATFORM_VERSION
        return response

    installed: list[str] = []
    for component, module_name, function_name in INSTALLERS:
        installer = _load_installer(module_name, function_name)
        installer(app)
        installed.append(component)

    app.state.ps_platform_extensions_installed = True
    app.state.ps_platform_version = PLATFORM_VERSION
    app.state.ps_platform_components = tuple(installed)

    @app.get("/api/platform/status", include_in_schema=False)
    def platform_status():
        return {
            "ok": True,
            "version": PLATFORM_VERSION,
            "bootstrap": "explicit-application-factory",
            "components": list(installed),
            "stable_domains": [
                "lineage",
                "jobs",
                "readiness",
                "lifecycle",
                "intake",
                "storage",
                "workspace",
            ],
            "deterministic_runtime": "app.intake.deterministic",
            "compatibility_bridge": "none",
        }
