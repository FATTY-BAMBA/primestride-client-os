"""HTTP routes for repeatable account and tenant provisioning."""
from __future__ import annotations

from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from ..db import SessionLocal
from ..models import Company, TimelineEvent
from .service import DOMAIN_VERSION, ensure_tenant_config, provisioning_snapshot


def install_account_routes(app: FastAPI) -> None:
    if getattr(app.state, "ps_account_routes_installed", False):
        return
    app.state.ps_account_routes_installed = True

    # Stable replacement for the prototype /companies route. Every new account
    # now receives a durable tenant/storage identity in the same transaction.
    @app.post("/companies", include_in_schema=False)
    def create_company_provisioned(
        name: str = Form(...),
        industry: str = Form(""),
        owner: str = Form(""),
        tenant_slug: str = Form(""),
        locale: str = Form("zh-Hant"),
        timezone_name: str = Form("Asia/Taipei"),
    ):
        db = SessionLocal()
        try:
            clean_name = name.strip()
            if not clean_name:
                return HTMLResponse("Company name is required", 400)

            company = Company(
                name=clean_name,
                industry=industry.strip() or None,
                owner=owner.strip() or None,
                stage="New Lead",
                next_action="Schedule first discovery meeting",
            )
            db.add(company)
            db.flush()

            config = ensure_tenant_config(
                db,
                company,
                slug=tenant_slug.strip() or None,
                locale=locale.strip() or None,
                timezone_name=timezone_name.strip() or None,
            )
            db.add(TimelineEvent(
                company_id=company.id,
                event_type="Created",
                title="Company added to pipeline",
                details=f"PrimeStride Owner: {company.owner or 'unassigned'}",
            ))
            db.add(TimelineEvent(
                company_id=company.id,
                event_type="Provisioning",
                title="Client tenant provisioned",
                details=(
                    f"{config['tenant_key']} · locale {config['locale']} · timezone {config['timezone']}"
                    + (" · persisted" if config.get("persisted") else " · awaiting migration persistence")
                ),
            ))
            db.commit()
            return RedirectResponse(f"/companies/{company.id}", 303)
        finally:
            db.close()

    @app.get("/companies/{company_id}/provisioning/status", include_in_schema=False)
    def provisioning_status(company_id: int):
        db = SessionLocal()
        try:
            company = db.get(Company, company_id)
            if not company:
                return JSONResponse({"error": "Company not found."}, status_code=404)
            result = provisioning_snapshot(db, company)
            db.commit()
            return {"ok": True, "domain": "accounts", **result}
        finally:
            db.close()

    @app.post("/companies/{company_id}/provisioning/preferences", include_in_schema=False)
    def update_provisioning_preferences(
        company_id: int,
        locale: str = Form(""),
        timezone_name: str = Form(""),
    ):
        db = SessionLocal()
        try:
            company = db.get(Company, company_id)
            if not company:
                return JSONResponse({"error": "Company not found."}, status_code=404)
            before = provisioning_snapshot(db, company)
            config = ensure_tenant_config(
                db,
                company,
                locale=locale.strip() or None,
                timezone_name=timezone_name.strip() or None,
            )
            db.add(TimelineEvent(
                company_id=company_id,
                event_type="Provisioning",
                title="Tenant preferences updated",
                details=(
                    f"locale {before['locale']} → {config['locale']} · "
                    f"timezone {before['timezone']} → {config['timezone']} · tenant key unchanged"
                ),
            ))
            db.commit()
            return {
                "ok": True,
                "version": DOMAIN_VERSION,
                "tenant_key": config["tenant_key"],
                "locale": config["locale"],
                "timezone": config["timezone"],
            }
        finally:
            db.close()


__all__ = ["install_account_routes"]
