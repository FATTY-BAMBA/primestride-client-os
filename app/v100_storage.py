"""PrimeStride Client OS v1.0 Source Vault.

Production-intake foundation for retaining original client files in a private,
tenant-prefixed S3-compatible object store. Existing IntakeFile rows remain the
workflow record; a compact source manifest is appended to notes so this release
does not require a database migration. The manifest preserves SHA-256, immutable
source id, object key, content type, size and storage timestamp.

The adapter is intentionally provider-neutral (AWS S3, Cloudflare R2, Supabase
S3-compatible storage, etc.). Nothing is persisted unless private object storage
is explicitly configured in the server environment.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import select

from .db import SessionLocal
from .models import Company, IntakeFile, TimelineEvent

VERSION = "1.0.0"
MANIFEST_PREFIX = "PS_SOURCE_VAULT_V1:"
MAX_SOURCE_BYTES = int(os.getenv("SOURCE_VAULT_MAX_BYTES", str(25 * 1024 * 1024)))

BUCKET = os.getenv("SOURCE_VAULT_BUCKET", "").strip()
ENDPOINT = os.getenv("SOURCE_VAULT_ENDPOINT", "").strip() or None
REGION = os.getenv("SOURCE_VAULT_REGION", "").strip() or None
ACCESS_KEY = os.getenv("SOURCE_VAULT_ACCESS_KEY_ID", "").strip()
SECRET_KEY = os.getenv("SOURCE_VAULT_SECRET_ACCESS_KEY", "").strip()
SSE = os.getenv("SOURCE_VAULT_SSE", "").strip()

ALLOWED_CATEGORIES = {"customers", "products", "quotes", "work_orders", "reports", "other"}


def _configured() -> bool:
    # Explicit credentials keep hosted behavior predictable. If we later adopt
    # workload identity/OIDC, this check can be expanded without changing routes.
    return bool(BUCKET and ACCESS_KEY and SECRET_KEY)


def _provider_name() -> str:
    if not ENDPOINT:
        return "AWS S3"
    host = ENDPOINT.lower()
    if "r2.cloudflarestorage.com" in host:
        return "Cloudflare R2"
    if "supabase" in host:
        return "Supabase S3"
    return "S3-compatible private storage"


def _s3_client():
    # Lazy import avoids making ordinary Client OS page loads pay boto3 import
    # cost when Source Vault is not used.
    import boto3

    kwargs: dict[str, Any] = {
        "aws_access_key_id": ACCESS_KEY,
        "aws_secret_access_key": SECRET_KEY,
    }
    if ENDPOINT:
        kwargs["endpoint_url"] = ENDPOINT
    if REGION:
        kwargs["region_name"] = REGION
    return boto3.client("s3", **kwargs)


def _safe_name(filename: str | None) -> str:
    name = Path(filename or "client-file").name.strip() or "client-file"
    name = re.sub(r"[^A-Za-z0-9._\-\u4e00-\u9fff]+", "-", name).strip(".-")
    return name[:180] or "client-file"


def _manifest_from_notes(notes: str | None) -> dict[str, Any] | None:
    if not notes or MANIFEST_PREFIX not in notes:
        return None
    for line in notes.splitlines():
        if line.startswith(MANIFEST_PREFIX):
            try:
                data = json.loads(line[len(MANIFEST_PREFIX):])
                return data if isinstance(data, dict) else None
            except Exception:
                return None
    return None


def _append_manifest(notes: str | None, manifest: dict[str, Any]) -> str:
    base_lines = [line for line in (notes or "").splitlines() if not line.startswith(MANIFEST_PREFIX)]
    base_lines.append(MANIFEST_PREFIX + json.dumps(manifest, ensure_ascii=False, separators=(",", ":")))
    return "\n".join(line for line in base_lines if line).strip()


def _public_manifest(row: IntakeFile, manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "file_id": row.id,
        "filename": row.filename,
        "category": row.category,
        "status": row.status,
        "source": row.source,
        "source_id": manifest.get("source_id"),
        "sha256": manifest.get("sha256"),
        "bytes": manifest.get("bytes"),
        "content_type": manifest.get("content_type"),
        "stored_at": manifest.get("stored_at"),
        "storage_provider": manifest.get("storage_provider"),
        "immutable": bool(manifest.get("immutable", True)),
    }


def install_v100_storage(app: FastAPI) -> None:
    if getattr(app.state, "ps_v100_storage_installed", False):
        return
    app.state.ps_v100_storage_installed = True

    @app.get("/api/source-vault/status", include_in_schema=False)
    def source_vault_status():
        return {
            "version": VERSION,
            "configured": _configured(),
            "provider": _provider_name() if _configured() else None,
            "bucket_configured": bool(BUCKET),
            "max_file_bytes": MAX_SOURCE_BYTES,
            "policy": "private-originals + sha256 + tenant-prefixed object keys",
        }

    @app.get("/companies/{company_id}/source-vault/files", include_in_schema=False)
    def source_vault_files(company_id: int):
        db = SessionLocal()
        try:
            company = db.get(Company, company_id)
            if not company:
                return JSONResponse({"error": "Company not found."}, status_code=404)
            rows = list(db.scalars(select(IntakeFile).where(IntakeFile.company_id == company_id).order_by(IntakeFile.received_at.desc())))
            vaulted = []
            unretained = []
            for row in rows:
                manifest = _manifest_from_notes(row.notes)
                if manifest:
                    vaulted.append(_public_manifest(row, manifest))
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
                "version": VERSION,
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
        object_key = f"tenants/company-{company_id}/originals/{now:%Y/%m}/{sha256[:12]}-{uuid.uuid4().hex[:8]}-{filename}"

        db = SessionLocal()
        try:
            company = db.get(Company, company_id)
            if not company:
                return JSONResponse({"error": "Company not found."}, status_code=404)

            # If the deterministic/AI inspector already registered this exact
            # source hash, attach the vault manifest to that record instead of
            # creating a duplicate inventory item.
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

            put_kwargs: dict[str, Any] = {
                "Bucket": BUCKET,
                "Key": object_key,
                "Body": raw,
                "ContentType": content_type,
                "ContentDisposition": f'attachment; filename="{filename}"',
                "Metadata": {
                    "company-id": str(company_id),
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
                details=f"{filename} · {source_id} · SHA-256 {sha256[:12]}… · {_provider_name()}",
            ))
            db.commit()
            db.refresh(row)
            return {
                "ok": True,
                "version": VERSION,
                "deduplicated": deduplicated,
                "file": _public_manifest(row, manifest),
            }
        finally:
            db.close()

    @app.get("/companies/{company_id}/source-vault/files/{file_id}/open", include_in_schema=False)
    def source_vault_open(company_id: int, file_id: int):
        if not _configured():
            return JSONResponse({"error": "Source Vault is not configured."}, status_code=503)
        db = SessionLocal()
        try:
            row = db.get(IntakeFile, file_id)
            if not row or row.company_id != company_id:
                return JSONResponse({"error": "Source file not found."}, status_code=404)
            manifest = _manifest_from_notes(row.notes)
            if not manifest or not manifest.get("object_key"):
                return JSONResponse({"error": "This inventory item has no retained original source."}, status_code=404)
            try:
                url = _s3_client().generate_presigned_url(
                    "get_object",
                    Params={"Bucket": BUCKET, "Key": manifest["object_key"]},
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
