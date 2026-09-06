"""Stable private object-storage services for retained client originals.

Source Vault keeps immutable originals in private S3-compatible storage. As of
v1.6, new object paths use the durable tenant identity from ``app.accounts``;
legacy environment/name-derived keys remain only as a compatibility fallback for
databases that have not yet adopted the tenant provisioning migration.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from ..models import Company, IntakeFile

DOMAIN_VERSION = "1.6.0"
MANIFEST_PREFIX = "PS_SOURCE_VAULT_V1:"
MAX_SOURCE_BYTES = int(os.getenv("SOURCE_VAULT_MAX_BYTES", str(25 * 1024 * 1024)))

BUCKET = os.getenv("SOURCE_VAULT_BUCKET", "").strip()
ENDPOINT = os.getenv("SOURCE_VAULT_ENDPOINT", "").strip() or None
REGION = os.getenv("SOURCE_VAULT_REGION", "").strip() or None
ACCESS_KEY = os.getenv("SOURCE_VAULT_ACCESS_KEY_ID", "").strip()
SECRET_KEY = os.getenv("SOURCE_VAULT_SECRET_ACCESS_KEY", "").strip()
SSE = os.getenv("SOURCE_VAULT_SSE", "").strip()

ALLOWED_CATEGORIES = {"customers", "products", "quotes", "work_orders", "reports", "other"}
# Historical fallback only. Persisted tenant_configs are authoritative in v1.6+.
DEFAULT_NAME_ALIASES = {"菘佑有限公司": "songyou"}


def configured() -> bool:
    return bool(BUCKET and ACCESS_KEY and SECRET_KEY)


def provider_name() -> str:
    if not ENDPOINT:
        return "AWS S3"
    host = ENDPOINT.lower()
    if "r2.cloudflarestorage.com" in host:
        return "Cloudflare R2"
    if "supabase" in host:
        return "Supabase S3"
    return "S3-compatible private storage"


def s3_client():
    # Keep boto3 lazy so ordinary Client OS requests do not pay its import cost.
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


def safe_name(filename: str | None) -> str:
    name = Path(filename or "client-file").name.strip() or "client-file"
    name = re.sub(r"[^A-Za-z0-9._\-\u4e00-\u9fff]+", "-", name).strip(".-")
    return name[:180] or "client-file"


def ascii_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    return slug[:48]


def slug_overrides() -> dict[str, str]:
    raw = os.getenv("SOURCE_VAULT_TENANT_SLUGS_JSON", "").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return {
            str(key): ascii_slug(str(value))
            for key, value in data.items()
            if ascii_slug(str(value))
        }
    except Exception:
        return {}


def _legacy_tenant_key(company: Company) -> str:
    overrides = slug_overrides()
    slug = overrides.get(str(company.id))
    if not slug:
        slug = DEFAULT_NAME_ALIASES.get(company.name)
    if not slug:
        slug = ascii_slug(company.name)
    if not slug:
        slug = "client"
    return f"c{company.id:04d}-{slug}"


def tenant_key(company: Company, db=None) -> str:
    """Return the immutable tenant namespace for a company.

    When a DB session is supplied, ``tenant_configs`` is authoritative. The
    fallback preserves existing behavior during migration adoption and for old
    compatibility imports that call this helper without a session.
    """
    if db is not None:
        try:
            from ..accounts.service import tenant_key_for_company
            return tenant_key_for_company(db, company)
        except Exception:
            # Storage should remain readable during migration rollout; legacy
            # namespace derivation is safer than failing an existing retained file.
            pass
    return _legacy_tenant_key(company)


def manifest_from_notes(notes: str | None) -> dict[str, Any] | None:
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


def append_manifest(notes: str | None, manifest: dict[str, Any]) -> str:
    base_lines = [
        line for line in (notes or "").splitlines()
        if not line.startswith(MANIFEST_PREFIX)
    ]
    base_lines.append(
        MANIFEST_PREFIX + json.dumps(manifest, ensure_ascii=False, separators=(",", ":"))
    )
    return "\n".join(line for line in base_lines if line).strip()


def public_manifest(row: IntakeFile, manifest: dict[str, Any]) -> dict[str, Any]:
    result = {
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
    if manifest.get("tenant_key"):
        result["tenant_key"] = manifest.get("tenant_key")
    if manifest.get("object_key"):
        result["object_path"] = manifest.get("object_key")
    return result


# Compatibility aliases while release-numbered modules are retired.
_configured = configured
_provider_name = provider_name
_s3_client = s3_client
_safe_name = safe_name
_ascii_slug = ascii_slug
_slug_overrides = slug_overrides
_manifest_from_notes = manifest_from_notes
_append_manifest = append_manifest
_public_manifest = public_manifest
_DEFAULT_NAME_ALIASES = DEFAULT_NAME_ALIASES

__all__ = [
    "DOMAIN_VERSION",
    "MANIFEST_PREFIX",
    "MAX_SOURCE_BYTES",
    "BUCKET",
    "ENDPOINT",
    "REGION",
    "ACCESS_KEY",
    "SECRET_KEY",
    "SSE",
    "ALLOWED_CATEGORIES",
    "DEFAULT_NAME_ALIASES",
    "configured",
    "provider_name",
    "s3_client",
    "safe_name",
    "ascii_slug",
    "slug_overrides",
    "tenant_key",
    "manifest_from_notes",
    "append_manifest",
    "public_manifest",
    "_configured",
    "_provider_name",
    "_s3_client",
    "_safe_name",
    "_ascii_slug",
    "_slug_overrides",
    "_manifest_from_notes",
    "_append_manifest",
    "_public_manifest",
    "_DEFAULT_NAME_ALIASES",
]
