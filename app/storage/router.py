"""HTTP routes for private Source Vault retention and retrieval."""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import select

from ..db import SessionLocal
from ..lifecycle.service import ensure_lifecycle_rows, reconcile_stage
from ..lineage.service import record_source_reference
from ..models import Company, IntakeFile, TimelineEvent
from .service import (
    ALLOWED_CATEGORIES,
    BUCKET,
    DOMAIN_VERSION,
    MAX_SOURCE_BYTES,
    SSE,
    append_manifest,
    configured,
    manifest_from_notes,
    provider_name,
    public_manifest,
    s3_client,
    safe_name,
    tenant_key,
)


def install_storage_routes(app: FastAPI) -> None:
    if getattr(app.state, "ps_storage_routes_installed", False):
        return
    app.state.ps_storage_routes_installed = True

    @app.get("/api/source-vault/status", include_in_schema=False)
    def source_vault_status():
        return {
            "version": DOMAIN_VERSION,
            "configured": configured(),
            "provider": provider_name() if configured() else None,
            "bucket_configured": bool(BUCKET),
            "max_file_bytes": MAX_SOURCE_BYTES,
            "policy": "private-originals + sha256 + tenant-prefixed object keys",
            "domain": "storage",
        }

    @app.get("/companies/{company_id}/source-first/status", include_in_schema=False)
    def source_first_status(company_id: int):
        db = SessionLocal()
        try:
            company = db.get(Company, company_id)
            if not company:
                return JSONResponse({"error": "Company not found."}, status_code=404)
            tkey = tenant_key(company)
            return {
                "ok": True,
                "version": DOMAIN_VERSION,
                "configured": configured(),
                "tenant_key": tkey,
                "path_pattern": f"tenants/{tkey}/originals/YYYY/MM/",
                "provider": provider_name() if configured() else None,
                "lineage_registry": "source_references",
                "domain": "storage",
            }
        finally:
            db.close()

    @app.get("/companies/{company_id}/source-vault/files", include_in_schema=False)
    def source_vault_files(company_id: int):
        db = SessionLocal()
        try:
            company = db.get(Company, company_id)
            if not company:
                return JSONResponse({"error": "Company not found."}, status_code=404)
            rows = list(
                db.scalars(
                    select(IntakeFile)
                    .where(IntakeFile.company_id == company_id)
                    .order_by(IntakeFile.received_at.desc())
                )
            )
            vaulted = []
            unretained = []
            for row in rows:
                manifest = manifest_from_notes(row.notes)
                if manifest:
                    item = public_manifest(row, manifest)
                    item["lineage_registry"] = "source_references"
                    vaulted.append(item)
                else:
                    unretained.append({
                        "file_id": row.id,
                        "filename": row.filename,
                        "category": row.category,
                        "status": row.status,
                        "source": row.source,
                    })
            return {
                "ok": True,
                "version": DOMAIN_VERSION,
                "registered_count": len(rows),
                "vaulted_count": len(vaulted),
                "vaulted": vaulted,
                "unretained": unretained,
            }
        finally:
            db.close()

    @app.post("/companies/{company_id}/source-vault/upload", include_in_schema=False)
    async def source_vault_upload(
        company_id: int,
        file: UploadFile = File(...),
        category: str = Form("other"),
    ):
        if not configured():
            return JSONResponse({
                "error": "Source Vault is installed but private object storage is not configured yet.",
                "code": "source_vault_not_configured",
            }, status_code=503)

        category = category if category in ALLOWED_CATEGORIES else "other"
        raw = await file.read(MAX_SOURCE_BYTES + 1)
        if not raw:
            return JSONResponse({"error": "The selected file is empty.", "code": "empty_file"}, status_code=400)
        if len(raw) > MAX_SOURCE_BYTES:
            return JSONResponse({
                "error": f"Source Vault currently accepts files up to {MAX_SOURCE_BYTES // (1024 * 1024)} MB per request.",
                "code": "source_too_large",
            }, status_code=413)

        sha256 = hashlib.sha256(raw).hexdigest()
        filename = safe_name(file.filename)
        content_type = (file.content_type or "application/octet-stream").strip()
        now = datetime.now(timezone.utc)
        source_id = f"src_{uuid.uuid4().hex}"

        db = SessionLocal()
        try:
            company = db.get(Company, company_id)
            if not company:
                return JSONResponse({"error": "Company not found."}, status_code=404)

            tkey = tenant_key(company)
            object_key = (
                f"tenants/{tkey}/originals/{now:%Y/%m}/"
                f"{sha256[:12]}-{uuid.uuid4().hex[:8]}-{filename}"
            )

            existing_rows = list(
                db.scalars(select(IntakeFile).where(IntakeFile.company_id == company_id))
            )
            matching: IntakeFile | None = None
            for row in existing_rows:
                if sha256 in (row.notes or ""):
                    matching = row
                    break
                manifest = manifest_from_notes(row.notes)
                if manifest and manifest.get("sha256") == sha256:
                    matching = row
                    break
                # Preserve v1.0.1 inventory behavior during architecture cleanup.
                if row.filename == filename:
                    matching = row
                    break

            put_kwargs: dict[str, Any] = {
                "Bucket": BUCKET,
                "Key": object_key,
                "Body": raw,
                "ContentType": content_type,
                "ContentDisposition": f'attachment; filename="{filename}"',
                "Metadata": {
                    "company-id": str(company_id),
                    "tenant-key": tkey,
                    "source-id": source_id,
                    "sha256": sha256,
                    "original-name": filename[:100],
                },
            }
            if SSE:
                put_kwargs["ServerSideEncryption"] = SSE

            try:
                s3_client().put_object(**put_kwargs)
            except Exception as exc:
                return JSONResponse({
                    "error": "Private object storage upload failed.",
                    "code": "source_vault_provider_error",
                    "detail": f"{type(exc).__name__}: {str(exc)[:800]}",
                }, status_code=502)

            manifest = {
                "version": 1,
                "source_id": source_id,
                "company_id": company_id,
                "tenant_key": tkey,
                "sha256": sha256,
                "bytes": len(raw),
                "content_type": content_type,
                "original_filename": filename,
                "object_key": object_key,
                "bucket": BUCKET,
                "storage_provider": provider_name(),
                "stored_at": now.isoformat(),
                "immutable": True,
            }

            if matching:
                matching.notes = append_manifest(matching.notes, manifest)
                if "Source Vault" not in (matching.source or ""):
                    matching.source = ((matching.source or "Manual") + " + Source Vault")[:80]
                row = matching
                deduplicated = True
            else:
                row = IntakeFile(
                    company_id=company_id,
                    filename=filename,
                    category=category,
                    status="Received",
                    source="Source Vault",
                    notes=append_manifest(None, manifest),
                )
                db.add(row)
                db.flush()
                deduplicated = False

            record_source_reference(
                db,
                company_id=company_id,
                intake_file_id=row.id,
                manifest=manifest,
            )

            # The stable lifecycle domain is authoritative for operational stage.
            ensure_lifecycle_rows(db, company_id)
            all_files = list(
                db.scalars(select(IntakeFile).where(IntakeFile.company_id == company_id)).all()
            )
            old_stage = company.stage
            reconcile_stage(db, company, all_files)

            db.add(TimelineEvent(
                company_id=company_id,
                event_type="Source Vault",
                title="Original source retained privately",
                details=(
                    f"{filename} · {source_id} · {tkey} · SHA-256 {sha256[:12]}…"
                    f" · {provider_name()} · first-class lineage"
                    + (f" · Stage: {old_stage} → {company.stage}" if old_stage != company.stage else "")
                ),
            ))
            db.commit()
            db.refresh(row)

            public = public_manifest(row, manifest)
            public["tenant_key"] = tkey
            public["object_path"] = object_key
            public["lineage_registry"] = "source_references"
            return {
                "ok": True,
                "version": DOMAIN_VERSION,
                "deduplicated": deduplicated,
                "file": public,
            }
        finally:
            db.close()

    @app.get("/companies/{company_id}/source-vault/files/{file_id}/open", include_in_schema=False)
    def source_vault_open(company_id: int, file_id: int):
        if not configured():
            return JSONResponse({"error": "Source Vault is not configured."}, status_code=503)
        db = SessionLocal()
        try:
            row = db.get(IntakeFile, file_id)
            if not row or row.company_id != company_id:
                return JSONResponse({"error": "Source file not found."}, status_code=404)
            manifest = manifest_from_notes(row.notes)
            if not manifest or not manifest.get("object_key"):
                return JSONResponse({"error": "This inventory item has no retained original source."}, status_code=404)
            bucket = str(manifest.get("bucket") or BUCKET or "").strip()
            if not bucket:
                return JSONResponse({"error": "Retained source has no storage bucket."}, status_code=404)
            try:
                url = s3_client().generate_presigned_url(
                    "get_object",
                    Params={"Bucket": bucket, "Key": manifest["object_key"]},
                    ExpiresIn=300,
                )
                return RedirectResponse(url=url, status_code=302)
            except Exception as exc:
                return JSONResponse({
                    "error": "Could not create a private source link.",
                    "detail": f"{type(exc).__name__}: {str(exc)[:800]}",
                }, status_code=502)
        finally:
            db.close()


__all__ = ["install_storage_routes"]
