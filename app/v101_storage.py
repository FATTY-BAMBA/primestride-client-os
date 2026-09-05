"""PrimeStride Client OS v1.0.1 tenant-readable Source Vault upload route.

Keeps immutable internal identity authoritative while making object keys easier
for humans to inspect. Example: tenants/c0001-songyou/originals/2026/09/...
Existing v1.0 objects remain valid at their historical keys; only new uploads use
this path convention.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy import select

from .db import SessionLocal
from .models import Company, IntakeFile, TimelineEvent
from .v100_storage import (
    ALLOWED_CATEGORIES,
    BUCKET,
    MAX_SOURCE_BYTES,
    SSE,
    _append_manifest,
    _configured,
    _manifest_from_notes,
    _provider_name,
    _public_manifest,
    _s3_client,
    _safe_name,
)

VERSION = "1.0.1"

# Optional production override. Example:
# SOURCE_VAULT_TENANT_SLUGS_JSON={"1":"songyou","2":"acme"}
# The known first-client alias keeps the current workspace readable immediately;
# future tenant creation should eventually persist this as TenantConfig.
_DEFAULT_NAME_ALIASES = {"菘佑有限公司": "songyou"}


def _ascii_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    return slug[:48]


def _slug_overrides() -> dict[str, str]:
    raw = os.getenv("SOURCE_VAULT_TENANT_SLUGS_JSON", "").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return {str(k): _ascii_slug(str(v)) for k, v in data.items() if _ascii_slug(str(v))}
    except Exception:
        return {}


def tenant_key(company: Company) -> str:
    overrides = _slug_overrides()
    slug = overrides.get(str(company.id))
    if not slug:
        slug = _DEFAULT_NAME_ALIASES.get(company.name)
    if not slug:
        slug = _ascii_slug(company.name)
    if not slug:
        slug = "client"
    return f"c{company.id:04d}-{slug}"


def install_v101_storage(app: FastAPI) -> None:
    if getattr(app.state, "ps_v101_storage_installed", False):
        return
    app.state.ps_v101_storage_installed = True

    @app.get("/companies/{company_id}/source-first/status", include_in_schema=False)
    def source_first_status(company_id: int):
        db = SessionLocal()
        try:
            company = db.get(Company, company_id)
            if not company:
                return JSONResponse({"error": "Company not found."}, status_code=404)
            return {
                "ok": True,
                "version": VERSION,
                "configured": _configured(),
                "tenant_key": tenant_key(company),
                "path_pattern": f"tenants/{tenant_key(company)}/originals/YYYY/MM/",
                "provider": _provider_name() if _configured() else None,
            }
        finally:
            db.close()

    # Registered before the v1.0 route so new uploads use the readable tenant key.
    @app.post("/companies/{company_id}/source-vault/upload", include_in_schema=False)
    async def source_vault_upload_v101(
        company_id: int,
        file: UploadFile = File(...),
        category: str = Form("other"),
    ):
        if not _configured():
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
                "error": f"Source Vault currently accepts files up to {MAX_SOURCE_BYTES // (1024*1024)} MB per request.",
                "code": "source_too_large",
            }, status_code=413)

        sha256 = hashlib.sha256(raw).hexdigest()
        filename = _safe_name(file.filename)
        content_type = (file.content_type or "application/octet-stream").strip()
        now = datetime.now(timezone.utc)
        source_id = f"src_{uuid.uuid4().hex}"

        db = SessionLocal()
        try:
            company = db.get(Company, company_id)
            if not company:
                return JSONResponse({"error": "Company not found."}, status_code=404)

            tkey = tenant_key(company)
            object_key = f"tenants/{tkey}/originals/{now:%Y/%m}/{sha256[:12]}-{uuid.uuid4().hex[:8]}-{filename}"

            existing_rows = list(db.scalars(select(IntakeFile).where(IntakeFile.company_id == company_id)))
            matching: IntakeFile | None = None
            for row in existing_rows:
                if sha256 in (row.notes or ""):
                    matching = row
                    break
                manifest = _manifest_from_notes(row.notes)
                if manifest and manifest.get("sha256") == sha256:
                    matching = row
                    break
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
                _s3_client().put_object(**put_kwargs)
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
                "storage_provider": _provider_name(),
                "stored_at": now.isoformat(),
                "immutable": True,
            }

            if matching:
                matching.notes = _append_manifest(matching.notes, manifest)
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
                    notes=_append_manifest(None, manifest),
                )
                db.add(row)
                db.flush()
                deduplicated = False

            if company.stage == "Data Requested":
                company.stage = "Data Received"
            db.add(TimelineEvent(
                company_id=company_id,
                event_type="Source Vault",
                title="Original source retained privately",
                details=f"{filename} · {source_id} · {tkey} · SHA-256 {sha256[:12]}… · {_provider_name()}",
            ))
            db.commit()
            db.refresh(row)
            public = _public_manifest(row, manifest)
            public["tenant_key"] = tkey
            public["object_path"] = object_key
            return {
                "ok": True,
                "version": VERSION,
                "deduplicated": deduplicated,
                "file": public,
            }
        finally:
            db.close()
