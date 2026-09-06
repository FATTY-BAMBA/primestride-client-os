# PrimeStride Client OS — Product & Platform Overview

**Version:** 1.6.0  
**Status:** Internal operating platform; architecture foundation complete, real-client evidence intake pending for the current 菘佑 implementation  
**Audience:** PrimeStride leadership, product/engineering, implementation team, future delivery partners

---

## 1. Executive summary

PrimeStride Client OS is the internal operating system that turns messy SME client evidence into a governed, repeatable AI implementation workflow.

It is not the final client-facing AI Operations Brain itself. It is the implementation engine behind it: the place where PrimeStride keeps client context, retains original files, creates source lineage, runs deterministic and multimodal analysis, controls what counts as evidence, measures module readiness, records decisions, and converts verified evidence into an implementation blueprint.

The current platform flow is:

`Client account → durable tenant identity → Source-First Intake → private original → SourceReference → IngestionJob → deterministic / AI proposal → human review → ACTIVE / TEST / ARCHIVED lifecycle → evidence-based readiness → client blueprint → implementation`

The core promise is simple:

> Accept messy client data without making the client clean it first, but never allow unverifiable or synthetic evidence to become client truth.

---

## 2. Why this exists

SME AI projects usually slow down at the same point: the client has spreadsheets, PDFs, work orders, quotations, SOPs, reports, photos and informal process knowledge, but no clean implementation-ready data model.

Traditional software projects often respond by giving the client homework: rename fields, export everything, clean files, explain every process, or migrate into a new system before value can begin.

PrimeStride Client OS is designed around the opposite approach:

- the client sends what they already use;
- PrimeStride retains the original before interpretation;
- the system inspects and proposes structure;
- humans approve what becomes evidence;
- readiness is calculated from reviewed evidence;
- the next request is the smallest missing gap, not another broad questionnaire.

This is intended to become reusable implementation IP across many SME clients.

---

## 3. What the tool currently does

### 3.1 Client account and tenant provisioning

Each Company receives a durable tenant identity independent of its display name. The tenant identity defines the storage namespace used by Source Vault and future tenant-level configuration.

Current behavior includes:

- persistent `tenant_configs` records;
- stable tenant keys such as `c0001-songyou`;
- default locale and timezone;
- default source lifecycle policy;
- onboarding status;
- preservation of historical Source Vault namespaces so existing object paths do not change if a company is renamed;
- automatic provisioning as part of new-client creation once the database migration is adopted.

### 3.2 Source-First Intake

The operating rule is **retain first, interpret second**.

When a source enters Client OS, the intended flow is:

1. retain the original file privately;
2. calculate SHA-256;
3. assign immutable `source_id`;
4. create or link the IntakeFile workflow record;
5. create first-class `SourceReference` lineage;
6. route the file to deterministic or AI analysis;
7. keep all extracted results as proposals until human review.

Supported paths include structured spreadsheets/CSV and multimodal PDF/image evidence.

### 3.3 Private Source Vault

Original client files are retained in private S3-compatible object storage. The current production adapter is configured for Cloudflare R2.

Source Vault provides:

- tenant-prefixed object paths;
- immutable source identity;
- SHA-256 provenance;
- storage-provider and MIME metadata;
- first-class SourceReference creation;
- private presigned access to the original;
- no public bucket requirement.

The first client namespace `c0001-songyou` is explicitly preserved.

### 3.4 Deterministic structured-data inspection

The proven browser inspection engine remains the v0.8.4 extraction behavior, now behind stable platform architecture.

It can:

- inspect CSV / TSV / JSON / XLSX;
- scan multi-sheet workbooks;
- identify strong table regions in messy sheets;
- suppress overlapping scan-noise candidates;
- infer likely data category;
- map source fields to canonical targets;
- profile missingness and uniqueness;
- normalize status values;
- flag structural and semantic quality issues;
- propose readiness evidence for human approval;
- preserve file hash and inspection metadata.

This path is deterministic and rule-based. AI does not calculate authoritative totals or pricing values.

### 3.5 Multimodal AI intake

PDFs, photos and scans can be analyzed by the stable `app.ai` domain using background Responses API jobs.

The multimodal layer can:

- extract visible business facts;
- reconstruct work-order sections;
- distinguish planned vs actual timestamps;
- rebuild production operation rows;
- separate instructions, constraints, notes and actual exceptions;
- propose canonical mappings;
- propose Module 04 / 05 / 06 readiness evidence;
- surface uncertainty and unsafe inferences;
- link the AI job back to the retained original SourceReference.

Important governance rules remain enforced:

- a single work order does not become invented history;
- planned timestamps do not become actual timestamps;
- a preventive instruction does not become an exception event;
- unsupported canonical targets are filtered before UI use;
- AI results remain proposals until human review.

### 3.6 First-class lineage and processing history

The platform has first-class `source_references` and `ingestion_jobs` tables.

That means PrimeStride can answer:

- which original file produced this analysis;
- which SHA and object path identify the retained source;
- which engine/model processed it;
- which attempt succeeded or failed;
- whether a retry reused the same original;
- whether a processing result has been human reviewed.

Retries create a new IngestionJob attempt against the same immutable source rather than uploading a duplicate original.

### 3.7 Source lifecycle isolation

Every IntakeFile has an operational lifecycle state:

- **ACTIVE** — real/current client evidence and allowed to affect readiness;
- **TEST** — synthetic engineering evidence; never allowed to affect client readiness;
- **ARCHIVED** — retained for audit/history but excluded from current assessment.

This solved an important product-risk issue: the synthetic files used to build and test the system remain preserved without contaminating real client truth.

### 3.8 Human review gate

The system does not silently promote extracted information into truth.

The workflow is:

`Analyze → propose mappings/evidence → operator reviews → Confirm Review → evidence becomes operational`

Human review also closes any associated `needs_review` ingestion jobs.

### 3.9 Evidence-based readiness

Readiness is deterministic and evidence-based.

Client OS distinguishes:

- Evidence Coverage;
- Readiness Range;
- confirmed weighted points;
- unknown weighted points;
- available / partial / missing / awaiting evidence.

Unknown does not mean missing and it does not mean ready.

The current scoring logic calculates a minimum from confirmed evidence and a maximum that includes still-unknown weighted criteria. This prevents the misleading provisional 100% scores common in early implementations.

### 3.10 Gap Intelligence

Reviewed readiness evidence is converted into a practical next-action brief:

- **ASK NEXT** — the smallest high-value unanswered evidence gaps;
- **WHAT WE KNOW** — current evidence by module;
- **DO NOT ASK AGAIN** — evidence already established and not worth re-requesting.

This is one of the main client-experience advantages of the platform: every data request should become smaller and more specific as evidence accumulates.

### 3.11 Job recovery and retry

Background multimodal jobs can be refreshed and terminal failures can be retried.

The retry contract is:

`original source → attempt 1 → terminal failure → attempt 2 → same SourceReference → new IngestionJob`

No duplicate original is created.

### 3.12 Stable platform architecture

The production backend is now composed from stable domains:

- `accounts`
- `lineage`
- `jobs`
- `readiness`
- `lifecycle`
- `intake`
- `storage`
- `workspace`
- `ai`

The application is built through an explicit FastAPI application factory and centralized bootstrap. The old FastAPI constructor monkeypatch and route-order bootstrap sprawl are gone.

The Data Intake frontend also has one stable browser bootstrap with four domain boundaries:

- deterministic;
- AI;
- source;
- workspace.

The release-numbered frontend files still exist as compatibility leaves behind those stable boundaries and can now be retired incrementally.

---

## 4. What the tool deliberately does not do yet

Client OS should not be confused with a full ERP or a finished external SaaS product.

It currently does **not** provide:

- full accounting / invoicing / general ledger;
- full inventory or MRP;
- complete external customer self-service portal;
- production-grade user authentication / RBAC for many external organizations;
- a finished permission model for every future role;
- autonomous approval of pricing or operational decisions;
- complete modules 01–06 as client-facing applications;
- automatic production database migrations during deployment;
- every legacy browser module fully rewritten into the new frontend domains.

This boundary is intentional. The current platform is the governed implementation and evidence layer that allows those client-facing capabilities to be built safely and repeatedly.

---

## 5. Current engineering maturity

### Complete / operational foundation

- explicit application factory and centralized bootstrap;
- stable backend domains;
- stable frontend bootstrap;
- private Source Vault;
- SourceReference lineage;
- IngestionJob history;
- background AI processing;
- retry and state recovery;
- deterministic structured intake;
- multimodal PDF/image intake;
- human evidence review;
- ACTIVE / TEST / ARCHIVED isolation;
- evidence-based readiness and Gap Intelligence;
- repeatable tenant provisioning code;
- Alembic migration framework;
- regression tests and GitHub Actions CI.

### Transition items still open

- run `alembic upgrade head` once against the production PostgreSQL database so production formally adopts the Alembic revisions and persists `tenant_configs`;
- retire release-numbered frontend implementation leaves domain-by-domain after parity testing;
- gradually retire the old Source Vault manifest copy in `IntakeFile.notes` after relational lineage is fully authoritative everywhere;
- add authentication / RBAC / stronger tenant boundary enforcement before broad external multi-user SaaS exposure.

---

## 6. Current 菘佑 implementation status

**Client:** 菘佑有限公司  
**Primary client contact:** Mei  
**PrimeStride Owner:** Abdoulie Fatty  
**Current priority modules:**

- 04 — AI Quoting;
- 05 — Work Order & Production Management;
- 06 — AI Analytics.

Current operating state:

- the Phase 0 onboarding/data checklist has already been sent;
- the client is not expected to clean or rename files before sending them;
- PrimeStride is waiting for the first real client sample upload;
- real readiness is therefore still intentionally unknown;
- synthetic test fixtures remain preserved as TEST and are excluded from readiness;
- no implementation blueprint should be treated as evidence-backed until real ACTIVE client sources are reviewed.

This is the correct place to wait. The platform is ready for the next real evidence event rather than needing another architecture cycle.

---

## 7. What happens when real client data arrives

The intended operating sequence is:

### Step 1 — retain

The source is stored privately first and receives immutable lineage.

### Step 2 — inspect

Structured files use deterministic inspection. PDFs/photos/scans use the multimodal AI path.

### Step 3 — review

PrimeStride reviews proposed classification, field mappings, quality flags and readiness evidence.

### Step 4 — confirm

Only approved evidence is confirmed. TEST and ARCHIVED material remains excluded.

### Step 5 — calculate readiness

Modules 04 / 05 / 06 receive evidence coverage and readiness ranges based only on reviewed ACTIVE evidence.

### Step 6 — identify smallest gaps

Gap Intelligence should produce a short next-request list and a clear do-not-ask-again list.

### Step 7 — generate implementation blueprint

Once enough evidence exists, the system can produce the evidence-backed client blueprint for the first operational slice.

---

## 8. Near-future roadmap and major wins

### A. Production migration adoption — immediate

Run the production PostgreSQL database to Alembic head.

**Win:** production gets formal schema version ownership, durable tenant configs and safer future migrations.

### B. Real-evidence readiness for 菘佑 — next external trigger

As soon as the first real files arrive, process them through Source-First Intake and build the first real readiness picture for Modules 04 / 05 / 06.

**Win:** the sales/implementation conversation changes from assumptions to evidence.

### C. Evidence-backed implementation blueprint

Generate a blueprint that clearly separates:

- confirmed operating facts;
- open assumptions;
- blocking gaps;
- V1 data model;
- required integrations;
- human approval points;
- module sequence.

**Win:** implementation scope becomes defensible, smaller and easier to price.

### D. First operational vertical slice

Recommended first closed-loop slice:

`Quote evidence → canonical quote/order data → accepted quote → work order → production status/events → management metric`

This deliberately crosses Modules 04 → 05 → 06.

**Win:** proves the central AI Operations Brain proposition: multiple applications sharing one operating-data spine.

### E. Repeatable multi-client onboarding

Extend account provisioning into a true onboarding template:

- tenant config;
- selected modules;
- client contact and PrimeStride Owner;
- intake checklist state;
- source namespace;
- default readiness rubric;
- implementation workspace.

**Win:** client #2 should start faster than client #1, and every implementation should make the next one easier.

### F. Authentication, RBAC and tenant hardening

Before making Client OS broadly client-accessible, implement explicit user identity, roles, permissions and tenant-scoped authorization below the AI layer.

**Win:** moves Client OS from internal implementation platform toward safe external collaboration / SaaS use.

### G. Client-facing AI Operations Brain modules

After the operating-data spine is proven, expand the vertical slice into the six client-facing modules:

1. Knowledge Management;
2. AI Knowledge Assistant;
3. AI Customer Service;
4. AI Quoting;
5. Work Order & Production Management;
6. AI Analytics.

All modules should consume the same governed operating-data layer rather than creating six independent systems.

---

## 9. Product principles that should not change

1. **Do not make messy-data clients perform unnecessary cleanup homework.**
2. **Retain originals before interpretation.**
3. **Messy is acceptable; unverifiable is not.**
4. **One canonical model; client variation should be configuration-first.**
5. **AI interprets, explains and proposes. Deterministic systems calculate authoritative values.**
6. **Important outputs need provenance.**
7. **Unknown evidence remains unknown.**
8. **TEST and ARCHIVED evidence never affect client truth.**
9. **Human review remains the approval boundary for material evidence.**
10. **Do not accidentally become a full ERP.**
11. **Every implementation should make the next implementation easier.**

---

## 10. How to judge whether Client OS is succeeding

Useful platform KPIs should eventually include:

- time from first client upload to first useful readiness assessment;
- percentage of client files that can be classified without re-requesting data;
- percentage of evidence linked to an immutable SourceReference;
- number of repeated questions prevented by `DO NOT ASK AGAIN` evidence;
- average number of follow-up data requests per implementation;
- percentage of ingestion jobs completing without manual recovery;
- time from sufficient evidence to implementation blueprint;
- time to first working operational vertical slice;
- implementation reuse rate across clients;
- client #N onboarding time compared with client #1.

---

## 11. Current position

PrimeStride Client OS has crossed the line from rapid prototype into a coherent internal implementation platform.

The core intake/governance architecture has been built, refactored, tested and deployed. The highest-value next work is no longer another foundation rewrite. It is to let real client evidence exercise the platform and then convert that evidence into the first production operational slice of the AI Operations Brain.

The next important milestone is therefore not another version number.

It is:

> **First real client evidence → reviewed readiness → evidence-backed blueprint → working 04/05/06 vertical slice.**
