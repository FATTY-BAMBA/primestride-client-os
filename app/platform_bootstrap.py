"""PrimeStride Client OS platform bootstrap.

Architecture consolidation entrypoint for the previously version-stacked runtime.

All production extensions are installed from one explicit registry in a fixed
order.  The current app still reaches this function through a small compatibility
bridge in db.py because app/main.py creates the FastAPI object directly during
module import.  That bridge is intentionally temporary; the next cleanup step is
moving app creation into an application factory and deleting the bridge entirely.

Keeping the registry here makes route precedence visible, testable and auditable
without scattering imports across database infrastructure.
"""
from __future__ import annotations

from importlib import import_module
from typing import Callable

from fastapi import FastAPI

PLATFORM_VERSION = "1.2.0"

# Order is behavioral: several newer routes intentionally shadow prototype
# routes, and Starlette resolves the first matching route.
INSTALLERS: tuple[tuple[str, str, str], ...] = (
    ("lineage", ".v110_lineage", "install_v110_lineage"),
    ("job_recovery", ".v112_jobs", "install_v112_jobs"),
    ("readiness_lifecycle", ".v1111_readiness_fix", "install_v1111_readiness_fix"),
    ("source_lifecycle", ".v111_lifecycle", "install_v111_lifecycle"),
    ("review_workflow", ".v110_review", "install_v110_review"),
    ("source_first_registration", ".v101_runtime", "install_v101_runtime"),
    ("source_first_storage", ".v101_storage", "install_v101_storage"),
    ("deterministic_intake", ".v082_runtime", "install_v082"),
    ("readiness_ranges", ".v082_perf", "install_v082_perf"),
    ("source_vault_compat", ".v100_storage", "install_v100_storage"),
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
            "bootstrap": "centralized-registry",
            "components": list(installed),
            "compatibility_bridge": "db.py -> platform_bootstrap (temporary)",
        }
