"""PrimeStride Client OS platform bootstrap.

v1.6.0 adds repeatable account/tenant provisioning on top of the consolidated
v1.5 platform. New clients receive a durable tenant namespace in the same
transaction that creates their Company record; Source Vault now resolves that
persisted identity instead of depending on a mutable company name.
"""
from __future__ import annotations

import time
from importlib import import_module
from typing import Callable

from fastapi import FastAPI, Request

PLATFORM_VERSION = "1.6.0"

INSTALLERS: tuple[tuple[str, str, str], ...] = (
    ("accounts", ".accounts.router", "install_account_routes"),
    ("lineage", ".lineage.router", "install_lineage_routes"),
    ("job_recovery", ".jobs.router", "install_job_routes"),
    ("readiness", ".readiness.router", "install_readiness_routes"),
    ("source_lifecycle", ".lifecycle.router", "install_lifecycle_routes"),
    ("intake", ".intake.router", "install_intake_routes"),
    ("storage", ".storage.router", "install_storage_routes"),
    ("workspace", ".workspace.router", "install_workspace_routes"),
    ("ai", ".ai.router", "install_ai_routes"),
)


def _load_installer(module_name: str, function_name: str) -> Callable[[FastAPI], None]:
    module = import_module(module_name, package=__package__)
    return getattr(module, function_name)


def install_platform_extensions(app: FastAPI) -> None:
    if getattr(app.state, "ps_platform_extensions_installed", False):
        return

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
        _load_installer(module_name, function_name)(app)
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
                "accounts",
                "lineage",
                "jobs",
                "readiness",
                "lifecycle",
                "intake",
                "storage",
                "workspace",
                "ai",
            ],
            "deterministic_runtime": "app.intake.deterministic",
            "multimodal_runtime": "app.ai",
            "frontend_runtime": "/static/frontend/bootstrap.js",
            "frontend_domains": ["deterministic", "ai", "source", "workspace"],
            "schema_migrations": "alembic",
            "regression_ci": "github-actions",
            "tenant_provisioning": "persistent-tenant-config",
            "compatibility_bridge": "none",
        }
