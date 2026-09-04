from contextlib import asynccontextmanager
from datetime import datetime, date
from pathlib import Path

from fastapi import FastAPI, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select, delete

from .db import get_db, SessionLocal, ensure_schema, DATABASE_URL
from .models import (
    Company, PreMeetingIntake, Discovery, Meeting, PainPoint, ModuleFit,
    Task, Readiness, TimelineEvent, ClientMemory, IntakeFile,
    ReadinessEvidence, DecisionLog, PIPELINE_STAGES,
)

BASE_DIR = Path(__file__).resolve().parent

MODULES = {
    1: "知識管理", 2: "AI 知識助理", 3: "AI 客服",
    4: "AI 報價", 5: "工單／生產管理", 6: "AI 數據分析",
}
MODULE_DETAILS = {
    4: {
        "name": "AI Quoting",
        "name_zh": "AI 報價",
        "purpose": "Turn historical pricing logic into explainable, reviewable quote recommendations.",
        "needs": "Historical quotes, pricing/cost inputs, rules, accepted prices and exception cases.",
    },
    5: {
        "name": "Work Order & Production",
        "name_zh": "工單／生產管理",
        "purpose": "Create a traceable operational flow from accepted order to production status and completion.",
        "needs": "Work orders, production stages, statuses, promised dates, timestamps and exception handling.",
    },
    6: {
        "name": "AI Analytics",
        "name_zh": "AI 數據分析",
        "purpose": "Make management questions answerable from trusted quote, order and production evidence.",
        "needs": "Historical transactions, costs, time fields, production events, trusted reports and KPI definitions.",
    },
}
DISCOVERY_REQUIRED = [
    "current_flow", "biggest_bottleneck", "key_person_dependency", "quote_process",
    "production_tracking", "management_metrics", "priority_improvement", "success_definition"
]
EXPECTED_DATA_CATEGORIES = [
    ("customers", "Customers & Contacts", "客戶與聯絡人"),
    ("products", "Products / Specs / Materials", "產品／規格／材料"),
    ("quotes", "Quotations / Pricing / Costs", "報價／價格／成本"),
    ("work_orders", "Orders / Work Orders", "訂單／工單"),
    ("reports", "Management Reports", "管理報表"),
    ("other", "Other Process Material", "其他流程資料"),
]
READINESS_CRITERIA = {
    4: [
        {"key": "historical_quotes", "label": "Historical quotations", "zh": "歷史報價單", "weight": 15},
        {"key": "customer_identity", "label": "Customer identity", "zh": "客戶識別", "weight": 5},
        {"key": "product_spec", "label": "Product / specification", "zh": "產品／規格", "weight": 15},
        {"key": "quantity", "label": "Quantity", "zh": "數量", "weight": 10},
        {"key": "quoted_price", "label": "Quoted price", "zh": "報價價格", "weight": 10},
        {"key": "accepted_price", "label": "Accepted /成交 price", "zh": "成交價格", "weight": 10},
        {"key": "material_cost", "label": "Material cost", "zh": "材料成本", "weight": 15},
        {"key": "processing_cost", "label": "Processing cost", "zh": "加工成本", "weight": 10},
        {"key": "pricing_rules", "label": "Pricing rules", "zh": "報價規則", "weight": 5},
        {"key": "exception_examples", "label": "Exception examples", "zh": "特殊／例外報價案例", "weight": 5},
    ],
    5: [
        {"key": "work_order_id", "label": "Work order ID", "zh": "工單編號", "weight": 10},
        {"key": "order_reference", "label": "Order / customer reference", "zh": "訂單／客戶關聯", "weight": 5},
        {"key": "product_spec", "label": "Product / specification", "zh": "產品／規格", "weight": 10},
        {"key": "quantity", "label": "Quantity", "zh": "數量", "weight": 5},
        {"key": "promised_date", "label": "Promised date", "zh": "承諾交期", "weight": 10},
        {"key": "production_stages", "label": "Production stages", "zh": "生產站別／製程", "weight": 15},
        {"key": "station_machine", "label": "Station / machine", "zh": "站別／機台", "weight": 10},
        {"key": "assignee", "label": "Responsible person", "zh": "負責人", "weight": 5},
        {"key": "current_status", "label": "Current status", "zh": "目前狀態", "weight": 10},
        {"key": "actual_timestamps", "label": "Actual start / completion time", "zh": "實際開始／完成時間", "weight": 10},
        {"key": "exceptions", "label": "Delay / rework / exception data", "zh": "延誤／重工／例外", "weight": 10},
    ],
    6: [
        {"key": "quote_history", "label": "Quote history", "zh": "報價歷史", "weight": 10},
        {"key": "order_history", "label": "Order history", "zh": "訂單歷史", "weight": 10},
        {"key": "work_order_history", "label": "Work-order history", "zh": "工單歷史", "weight": 10},
        {"key": "revenue", "label": "Revenue", "zh": "營收", "weight": 10},
        {"key": "cost", "label": "Cost", "zh": "成本", "weight": 10},
        {"key": "margin", "label": "Margin / gross profit", "zh": "毛利", "weight": 10},
        {"key": "customer_product", "label": "Customer & product dimensions", "zh": "客戶與產品維度", "weight": 10},
        {"key": "time_fields", "label": "Reliable time fields", "zh": "可信時間欄位", "weight": 10},
        {"key": "production_events", "label": "Production events", "zh": "生產事件", "weight": 10},
        {"key": "kpi_definitions", "label": "Trusted reports / KPI definitions", "zh": "可信報表／KPI 定義", "weight": 10},
    ],
}
READINESS_STATUS_OPTIONS = [
    ("awaiting", "Awaiting evidence · 待證據"),
    ("available", "Available · 已有"),
    ("partial", "Partial · 部分"),
    ("missing", "Missing · 缺少"),
    ("not_required", "Not required · 不需要"),
]
READINESS_STATUS_LABELS = dict(READINESS_STATUS_OPTIONS)
READINESS_FACTORS = {"available": 1.0, "partial": 0.5, "missing": 0.0}
STAGE_ZH = {
    "New Lead": "新名單", "Meeting Booked": "已約會", "Discovery": "探索中",
    "Diagnosis Confirmed": "診斷完成", "Solution Fit": "方案匹配", "Data Requested": "已請資料",
    "Data Received": "已收資料", "Data Readiness": "資料健檢", "Client Blueprint": "客戶藍圖",
    "Proposal": "已提案", "Won": "已成交", "Nurture": "持續培養", "Lost": "未成交",
    "Implementation": "導入中", "Go Live": "已上線", "Optimization": "優化中",
}


def seed_initial_account() -> None:
    """Seed a truthful first account only when the database is empty."""
    ensure_schema()
    db = SessionLocal()
    try:
        if db.scalar(select(Company.id).limit(1)):
            return
        c = Company(
            name="菘佑有限公司",
            industry="Printing",
            stage="Data Requested",
            owner="Abdoulie Fatty",
            next_action="Await initial sample-data upload",
            due_date=None,
            fit_status="Potential Fit",
        )
        db.add(c)
        db.flush()
        db.add_all([
            TimelineEvent(company_id=c.id, event_type="Meeting", title="Initial client meeting completed", details="Primary contact: Mei"),
            TimelineEvent(company_id=c.id, event_type="Scope", title="Priority modules confirmed", details="04 AI Quoting · 05 Work Order & Production · 06 AI Analytics"),
            TimelineEvent(company_id=c.id, event_type="Data Request", title="Phase 0 data checklist sent", details="Existing formats accepted; no cleanup required."),
            TimelineEvent(company_id=c.id, event_type="Data Request", title="Shared upload folder provided", details="Client may place uncertain files in 00_直接丟這裡也可以."),
        ])
        for no in (4, 5, 6):
            db.add(ModuleFit(company_id=c.id, module_no=no, module_name=MODULES[no], fit="High", reason="Confirmed interest in initial meeting"))
        db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        ensure_schema()
        seed_initial_account()
    except Exception as exc:
        print(f"[startup] database initialization warning: {exc!r}")
    yield


app = FastAPI(title="PrimeStride Client OS", version="0.5.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def company_stmt(company_id: int):
    return select(Company).where(Company.id == company_id).options(
        selectinload(Company.intake), selectinload(Company.pains), selectinload(Company.discovery),
        selectinload(Company.meetings), selectinload(Company.module_fits), selectinload(Company.tasks),
        selectinload(Company.readiness), selectinload(Company.timeline),
        selectinload(Company.memory_items), selectinload(Company.intake_files),
        selectinload(Company.readiness_evidence), selectinload(Company.decisions),
    )


def discovery_completion(d: Discovery | None) -> int:
    if not d:
        return 0
    done = sum(1 for f in DISCOVERY_REQUIRED if (getattr(d, f, None) or "").strip())
    return round(done / len(DISCOVERY_REQUIRED) * 100)


def build_followup(c: Company, d: Discovery, pains: list[PainPoint], fits: list[ModuleFit]) -> str:
    top = pains[:3]
    pain_lines = "\n".join([f"{i + 1}. {p.description}" for i, p in enumerate(top)]) or "1. 待確認主要痛點"
    fit_lines = "、".join([f"{m.module_no} {m.module_name}" for m in fits if m.fit == "High"]) or "待確認"
    return (
        f"{c.name} 您好，\n\n感謝今天的時間。依今天討論，我們先確認目前最值得優先改善的是：\n"
        f"{pain_lines}\n\n因此第一階段較相關的方向是：{fit_lines}。\n\n"
        f"下一步：{c.next_action or '確認下一步資料與會議'}。\n"
        "我們會以今天確認的流程與優先順序為基礎，不會要求您重複說明同一件事。"
    )


def render(request: Request, name: str, context: dict):
    return templates.TemplateResponse(request=request, name=name, context=context)


def primary_contact(c: Company) -> str | None:
    for event in sorted(c.timeline, key=lambda x: x.created_at, reverse=True):
        if event.details and "Primary contact:" in event.details:
            return event.details.split("Primary contact:", 1)[1].strip()
    return None


def selected_module_nos(c: Company) -> list[int]:
    selected = sorted(m.module_no for m in c.module_fits if m.fit == "High" and m.module_no in READINESS_CRITERIA)
    return selected or [4, 5, 6]


def ensure_v04_memory(db: Session, c: Company) -> None:
    """Bootstrap persistent 'never ask twice' memory from facts already captured."""
    if db.scalar(select(ClientMemory.id).where(ClientMemory.company_id == c.id).limit(1)):
        return

    contact = primary_contact(c)
    high_modules = sorted(m.module_no for m in c.module_fits if m.fit == "High")
    module_text = ", ".join(f"0{n} {MODULES[n]}" for n in high_modules)

    items: list[ClientMemory] = []
    if c.industry:
        items.append(ClientMemory(company_id=c.id, kind="known", title=f"Industry: {c.industry}", source="Account record"))
    if contact:
        items.append(ClientMemory(company_id=c.id, kind="known", title=f"Primary client contact: {contact}", source="Client onboarding"))
    if module_text:
        items.append(ClientMemory(company_id=c.id, kind="known", title=f"Priority modules: {module_text}", source="Initial meeting"))
    if any(e.title == "Phase 0 data checklist sent" for e in c.timeline):
        items.append(ClientMemory(company_id=c.id, kind="known", title="Phase 0 data checklist already sent", source="Timeline"))
    if any(e.title == "Shared upload folder provided" for e in c.timeline):
        items.append(ClientMemory(company_id=c.id, kind="known", title="Shared upload folder already provided", source="Timeline"))

    if 4 in high_modules:
        items.append(ClientMemory(company_id=c.id, kind="unknown", title="Exact quotation logic and exception rules", source="Pending client data"))
    if 5 in high_modules:
        items.append(ClientMemory(company_id=c.id, kind="unknown", title="Actual production stages and work-order statuses", source="Pending client data"))
    if 6 in high_modules:
        items.append(ClientMemory(company_id=c.id, kind="unknown", title="Management KPI definitions and trusted reports", source="Pending client data"))
    items.append(ClientMemory(company_id=c.id, kind="unknown", title="Client decision maker / approval authority", source="Discovery"))

    if module_text:
        items.append(ClientMemory(company_id=c.id, kind="do_not_ask", title="Which modules are you interested in?", details="Already confirmed in the initial meeting."))
    if contact:
        items.append(ClientMemory(company_id=c.id, kind="do_not_ask", title="Who is our main client contact?", details="Primary contact is already recorded."))
    if c.stage == "Data Requested":
        items.append(ClientMemory(company_id=c.id, kind="do_not_ask", title="Please prepare all your data", details="A focused Phase 0 request was already sent. Review the first batch before asking for more."))
        items.append(ClientMemory(company_id=c.id, kind="next_question", title="After the first files are reviewed: what happens between quote acceptance and work-order creation?", details="Ask only if the files do not already answer this."))
    else:
        items.append(ClientMemory(company_id=c.id, kind="next_question", title="What is the smallest unanswered question that blocks the next stage?", details="Use evidence already captured before asking the client."))

    db.add_all(items)


def ensure_v05_decisions(db: Session, c: Company) -> None:
    if db.scalar(select(DecisionLog.id).where(DecisionLog.company_id == c.id).limit(1)):
        return
    selected = selected_module_nos(c)
    if selected:
        names = " · ".join(f"0{n} {MODULE_DETAILS[n]['name']}" for n in selected)
        db.add(DecisionLog(
            company_id=c.id,
            title="Priority modules confirmed",
            decision=f"Working scope is {names}.",
            rationale="Confirmed interest from the initial client meeting. Exact implementation depth remains evidence-dependent.",
            source="Initial meeting",
            status="Confirmed",
        ))
    if any(e.title == "Phase 0 data checklist sent" for e in c.timeline):
        db.add(DecisionLog(
            company_id=c.id,
            title="Data handoff approach",
            decision="Client may provide existing files without cleanup or reformatting; PrimeStride reviews the first batch before asking for more.",
            rationale="Reduce client effort and avoid requesting data that is not actually needed.",
            source="Phase 0 onboarding",
            status="Confirmed",
        ))


def memory_groups(c: Company) -> dict[str, list[ClientMemory]]:
    groups = {"known": [], "unknown": [], "do_not_ask": [], "next_question": []}
    for item in c.memory_items:
        if item.active:
            groups.setdefault(item.kind, []).append(item)
    return groups


def module_readiness_summary(c: Company, module_no: int) -> dict:
    criteria = READINESS_CRITERIA[module_no]
    evidence_map = {
        e.criterion_key: e for e in c.readiness_evidence if e.module_no == module_no
    }
    enriched = []
    required_total = 0.0
    reviewed_weight = 0.0
    score_weight = 0.0
    score_possible = 0.0

    for item in criteria:
        evidence = evidence_map.get(item["key"])
        status = evidence.status if evidence else "awaiting"
        if status not in {"awaiting", "available", "partial", "missing", "not_required"}:
            status = "awaiting"
        weight = float(item["weight"])
        if status != "not_required":
            required_total += weight
        if status in READINESS_FACTORS:
            reviewed_weight += weight
            score_possible += weight
            score_weight += weight * READINESS_FACTORS[status]
        enriched.append({
            **item,
            "status": status,
            "status_label": READINESS_STATUS_LABELS.get(status, status),
            "notes": evidence.notes if evidence else None,
            "source": evidence.source if evidence else None,
        })

    review_progress = (reviewed_weight / required_total * 100) if required_total else 100.0
    score = (score_weight / score_possible * 100) if score_possible else None
    final = bool(score is not None and review_progress >= 99.9)
    score_label = "Final" if final else ("Provisional" if score is not None else "Awaiting evidence")
    details = MODULE_DETAILS[module_no]
    return {
        "module_no": module_no,
        "name": details["name"],
        "name_zh": details["name_zh"],
        "score": score,
        "score_label": score_label,
        "review_progress": review_progress,
        "final": final,
        "criteria": enriched,
    }


def readiness_summaries(c: Company) -> list[dict]:
    return [module_readiness_summary(c, no) for no in selected_module_nos(c)]


def stage_intelligence(c: Company) -> dict:
    selected = selected_module_nos(c)
    contact_known = bool(primary_contact(c))
    priority_known = bool(selected)
    checklist_sent = any(e.title == "Phase 0 data checklist sent" for e in c.timeline)
    folder_sent = any(e.title == "Shared upload folder provided" for e in c.timeline)
    files_received = len(c.intake_files) > 0
    evidence_started = any(e.status in READINESS_FACTORS or e.status == "not_required" for e in c.readiness_evidence)
    summaries = readiness_summaries(c)
    readiness_final = bool(summaries and all(s["final"] for s in summaries))
    blueprint_approved = any(
        d.status == "Confirmed" and ("blueprint approved" in d.title.lower() or "方案藍圖核准" in d.title)
        for d in c.decisions
    )

    stage = c.stage
    if stage == "Data Requested":
        why_here = [
            {"label": "Priority modules confirmed", "zh": "已確認優先模組", "done": priority_known},
            {"label": "Primary client contact known", "zh": "已知主要客戶窗口", "done": contact_known},
            {"label": "Phase 0 data request sent", "zh": "已寄出第一階段資料清單", "done": checklist_sent},
            {"label": "Upload location provided", "zh": "已提供上傳位置", "done": folder_sent},
        ]
        exits = [{"label": "At least one real sample file is received", "zh": "收到至少一份真實資料樣本", "done": files_received}]
        return _stage_info(
            stage, "Collect the smallest useful evidence set without creating client homework.", "用最低負擔取得足以往下一步的真實資料。",
            "First sample-data upload", "客戶第一批資料上傳", "Data Received", exits, why_here,
            ["Do not send another broad questionnaire.", "Do not ask which modules they want again.", "Do not repeat the introductory pitch."],
            ["Wait for the first upload.", "When a file arrives, create the inventory and move to Data Received.", "Preserve the original file and its source before interpreting it."],
            "They already know what we need and we are not making them redo work.", "他們知道下一步，而且不需要為了我們重新整理一堆資料。",
        )
    if stage == "Data Received":
        why_here = [
            {"label": "At least one sample file received", "zh": "已收到至少一份資料", "done": files_received},
            {"label": "Priority modules still in scope", "zh": "優先模組仍已確認", "done": priority_known},
        ]
        exits = [
            {"label": "File inventory exists", "zh": "已建立檔案清單", "done": files_received},
            {"label": "Evidence review has started", "zh": "已開始證據檢視", "done": evidence_started},
        ]
        return _stage_info(
            stage, "Understand what the client actually sent before asking for anything else.", "先看客戶真正提供了什麼，再決定還缺什麼。",
            "File classification and first evidence review", "檔案分類與第一輪證據檢視", "Data Readiness", exits, why_here,
            ["Do not treat missing categories as automatic blockers.", "Do not infer pricing logic from filenames alone.", "Do not request more historical data before checking what is already usable."],
            ["Classify the received files.", "Detect useful fields and source relationships.", "Start module readiness evidence review.", "Record only the smallest unanswered gaps."],
            "PrimeStride looked at our real material before coming back with questions.", "PrimeStride 先看過我們真的在用的資料，才來問有必要的問題。",
        )
    if stage == "Data Readiness":
        why_here = [
            {"label": "Client evidence received", "zh": "已有客戶證據", "done": files_received},
            {"label": "Readiness evidence review started", "zh": "已開始資料準備度檢視", "done": evidence_started},
        ]
        exits = [{"label": "All required criteria reviewed for selected modules", "zh": "優先模組必要條件皆完成檢視", "done": readiness_final}]
        return _stage_info(
            stage, "Turn client evidence into an explainable readiness assessment and minimum gap request.", "把真實資料轉成可解釋的準備度與最小缺口。",
            "Complete evidence review", "完成證據檢視", "Client Blueprint", exits, why_here,
            ["Do not invent readiness percentages.", "Do not confuse data completeness with go-live readiness.", "Do not ask for non-blocking gaps just because a field is missing."],
            ["Review each criterion with a source.", "Label scores Provisional until evidence review is complete.", "Identify only blocking gaps.", "Prepare an evidence-informed Solution Blueprint."],
            "They can see exactly what we found, what matters, and why we are asking for anything else.", "他們看得到我們找到什麼、缺什麼、以及為什麼真的需要補。",
        )
    if stage == "Client Blueprint":
        why_here = [
            {"label": "Readiness review complete", "zh": "資料準備度檢視完成", "done": readiness_final},
            {"label": "Confirmed scope exists", "zh": "已有確認的模組方向", "done": priority_known},
        ]
        exits = [{"label": "Solution blueprint approved / decision recorded", "zh": "方案藍圖已確認並留下決策紀錄", "done": blueprint_approved}]
        return _stage_info(
            stage, "Agree on the client-specific future state, scope and first implementation slice.", "確認客戶專屬的未來流程、範圍與第一階段導入。",
            "Client confirmation of the solution blueprint", "客戶確認方案藍圖", "Proposal", exits, why_here,
            ["Do not present hypotheses as confirmed current-state facts.", "Do not expand scope because an adjacent feature is interesting.", "Do not lose the decision rationale."],
            ["Show confirmed current-state evidence.", "Separate confirmed design from TBD items.", "Record scope decisions and rationale.", "Prepare proposal only after the blueprint is aligned."],
            "The proposal feels like it was designed from our operation, not copied from another customer.", "方案像是從我們公司的真實流程長出來，而不是套版。",
        )
    if stage == "Proposal":
        why_here = [{"label": "Client-specific blueprint exists", "zh": "已有客戶專屬藍圖", "done": blueprint_approved}]
        exits = [{"label": "Commercial decision recorded", "zh": "商務決策已紀錄", "done": False}]
        return _stage_info(
            stage, "Turn the agreed blueprint into scope, investment and decision terms.", "把已確認的藍圖轉成範圍、投資與決策條件。",
            "Commercial decision", "商務決策", "Won", exits, why_here,
            ["Do not reopen already-approved scope without a new reason.", "Do not use generic ROI claims when client-specific baselines exist."],
            ["Tie price to the agreed scope.", "Use client evidence for ROI where available.", "Capture objections as new facts or decisions."],
            "The price and proposal clearly connect to what we agreed was worth fixing.", "價格和提案內容都能對回先前確認的問題與價值。",
        )
    if stage in {"Won", "Implementation"}:
        why_here = [{"label": "Commercial direction confirmed", "zh": "商務方向已確認", "done": True}]
        exits = [{"label": "Implementation acceptance criteria achieved", "zh": "導入驗收條件達成", "done": False}]
        return _stage_info(
            stage, "Deliver the agreed scope with traceable decisions, evidence and adoption milestones.", "按照已確認範圍交付，並追蹤決策、證據與採用狀況。",
            "Implementation milestones", "導入里程碑", "Go Live", exits, why_here,
            ["Do not rebuild customer-specific logic as hard-coded branches.", "Do not lose source lineage during data cleanup."],
            ["Convert blueprint decisions into configuration.", "Track blockers and acceptance criteria.", "Measure the agreed baseline and post-launch result."],
            "PrimeStride is executing exactly what was agreed, and progress is visible.", "PrimeStride 正在照已確認的內容落地，而且進度看得見。",
        )
    if stage == "Go Live":
        why_here = [{"label": "Core workflow is live", "zh": "核心流程已上線", "done": True}]
        exits = [{"label": "Initial adoption and outcome review complete", "zh": "第一輪採用與成效檢視完成", "done": False}]
        return _stage_info(
            stage, "Stabilize usage, resolve launch issues and measure early outcomes.", "穩定使用、處理上線問題並量測初步成效。",
            "Adoption and outcome review", "採用與成效檢視", "Optimization", exits, why_here,
            ["Do not call the project finished just because the software is deployed."],
            ["Monitor adoption.", "Resolve exceptions.", "Compare agreed baseline vs actual outcome.", "Identify the next highest-value improvement."],
            "PrimeStride stays with us after launch and proves whether the system is actually helping.", "不是上線就走，而是一起確認系統有沒有真的產生效果。",
        )

    why_here = [{"label": f"Current stage recorded as {stage}", "zh": f"目前階段為 {STAGE_ZH.get(stage, stage)}", "done": True}]
    exits = [{"label": "Complete the current stage definition of done", "zh": "完成本階段驗收條件", "done": False}]
    next_stage = PIPELINE_STAGES[PIPELINE_STAGES.index(stage) + 1] if stage in PIPELINE_STAGES and PIPELINE_STAGES.index(stage) < len(PIPELINE_STAGES) - 1 else None
    return _stage_info(
        stage, "Advance only when the next step is supported by captured evidence.", "只有在已有證據支持時才往下一步。",
        "Current stage work", "目前階段工作", next_stage, exits, why_here,
        ["Do not advance the account just to make the pipeline look healthier."],
        ["Capture what is known.", "Define the next concrete action.", "Record decisions before changing scope."],
        "PrimeStride always knows where the project is and what happens next.", "PrimeStride 永遠知道現在在哪裡、接下來該做什麼。",
    )


def _stage_info(stage, purpose, purpose_zh, waiting_for, waiting_for_zh, next_stage, exit_conditions, why_here, do_not, system_actions, client_experience, client_experience_zh):
    done_count = sum(1 for x in why_here if x["done"])
    total_count = len(why_here)
    ready = bool(exit_conditions and all(x["done"] for x in exit_conditions))
    return {
        "stage": stage,
        "purpose": purpose,
        "purpose_zh": purpose_zh,
        "waiting_for": waiting_for,
        "waiting_for_zh": waiting_for_zh,
        "next_stage": next_stage,
        "next_stage_zh": STAGE_ZH.get(next_stage, next_stage) if next_stage else None,
        "exit_conditions": exit_conditions,
        "why_here": why_here,
        "do_not": do_not,
        "system_actions": system_actions,
        "client_experience": client_experience,
        "client_experience_zh": client_experience_zh,
        "done_count": done_count,
        "total_count": total_count,
        "ready_to_advance": ready,
    }


@app.get("/health")
def health():
    db_kind = "postgresql" if DATABASE_URL.startswith("postgres") else "sqlite-demo"
    return {"status": "ok", "service": "PrimeStride Client OS", "version": "0.5.0", "database": db_kind}


@app.get("/", response_class=HTMLResponse)
def pipeline(request: Request, db: Session = Depends(get_db)):
    if not db.scalar(select(Company.id).limit(1)):
        db.close()
        seed_initial_account()
        db = SessionLocal()
    companies = db.scalars(select(Company).order_by(Company.updated_at.desc())).all()
    buckets = {stage: [] for stage in PIPELINE_STAGES}
    for c in companies:
        buckets.setdefault(c.stage, []).append(c)
    visible = [s for s in PIPELINE_STAGES if buckets.get(s)] or PIPELINE_STAGES[:5]
    return render(request, "pipeline.html", {"buckets": buckets, "stages": visible})


@app.post("/companies")
def create_company(name: str = Form(...), industry: str = Form(""), owner: str = Form(""), db: Session = Depends(get_db)):
    c = Company(name=name, industry=industry or None, owner=owner or None, stage="New Lead", next_action="Schedule first discovery meeting")
    db.add(c)
    db.flush()
    db.add(TimelineEvent(company_id=c.id, event_type="Created", title="Company added to pipeline"))
    db.commit()
    return RedirectResponse(f"/companies/{c.id}", 303)


@app.get("/companies/{company_id}", response_class=HTMLResponse)
def company_detail(company_id: int, request: Request, db: Session = Depends(get_db)):
    c = db.scalar(company_stmt(company_id))
    if not c:
        return HTMLResponse("Company not found", 404)
    ensure_v04_memory(db, c)
    ensure_v05_decisions(db, c)
    db.commit()
    c = db.scalar(company_stmt(company_id))
    c.pains.sort(key=lambda x: x.rank)
    c.module_fits.sort(key=lambda x: x.module_no)
    c.readiness.sort(key=lambda x: x.module_no)
    c.timeline.sort(key=lambda x: x.created_at, reverse=True)
    c.meetings.sort(key=lambda x: x.completed_at, reverse=True)
    c.memory_items.sort(key=lambda x: x.id)
    c.intake_files.sort(key=lambda x: x.received_at, reverse=True)
    c.decisions.sort(key=lambda x: x.decided_at, reverse=True)
    return render(request, "company.html", {
        "company": c,
        "stages": PIPELINE_STAGES,
        "modules": MODULES,
        "completion": discovery_completion(c.discovery),
        "memory": memory_groups(c),
        "files_received": len(c.intake_files),
        "stage_info": stage_intelligence(c),
        "readiness_summaries": readiness_summaries(c),
        "decision_count": len(c.decisions),
    })


@app.post("/companies/{company_id}/memory")
def add_memory(
    company_id: int,
    kind: str = Form(...),
    title: str = Form(...),
    details: str = Form(""),
    source: str = Form("Manual"),
    confidence: str = Form("High"),
    db: Session = Depends(get_db),
):
    allowed = {"known", "unknown", "do_not_ask", "next_question"}
    if kind not in allowed:
        return HTMLResponse("Invalid memory kind", 400)
    db.add(ClientMemory(
        company_id=company_id,
        kind=kind,
        title=title.strip(),
        details=details.strip() or None,
        source=source.strip() or "Manual",
        confidence=confidence,
    ))
    db.add(TimelineEvent(company_id=company_id, event_type="Memory", title=f"Client memory added: {title.strip()}"))
    db.commit()
    return RedirectResponse(f"/companies/{company_id}#memory", 303)


@app.get("/companies/{company_id}/stage-intelligence", response_class=HTMLResponse)
def stage_intelligence_workspace(company_id: int, request: Request, db: Session = Depends(get_db)):
    c = db.scalar(company_stmt(company_id))
    if not c:
        return HTMLResponse("Company not found", 404)
    ensure_v04_memory(db, c)
    ensure_v05_decisions(db, c)
    db.commit()
    c = db.scalar(company_stmt(company_id))
    return render(request, "stage_intelligence.html", {
        "company": c,
        "stage_info": stage_intelligence(c),
        "stages": PIPELINE_STAGES,
    })


@app.get("/companies/{company_id}/data-intake", response_class=HTMLResponse)
def data_intake_workspace(company_id: int, request: Request, db: Session = Depends(get_db)):
    c = db.scalar(company_stmt(company_id))
    if not c:
        return HTMLResponse("Company not found", 404)
    ensure_v04_memory(db, c)
    db.commit()
    c = db.scalar(company_stmt(company_id))
    c.intake_files.sort(key=lambda x: x.received_at, reverse=True)
    received_categories = {f.category for f in c.intake_files}
    return render(request, "data_intake.html", {
        "company": c,
        "expected_categories": EXPECTED_DATA_CATEGORIES,
        "received_categories": received_categories,
        "files_received": len(c.intake_files),
        "memory": memory_groups(c),
    })


@app.post("/companies/{company_id}/data-intake/register")
def register_intake_file(
    company_id: int,
    filename: str = Form(...),
    category: str = Form(...),
    source: str = Form("Manual"),
    notes: str = Form(""),
    db: Session = Depends(get_db),
):
    c = db.get(Company, company_id)
    if not c:
        return HTMLResponse("Company not found", 404)
    valid_categories = {key for key, _, _ in EXPECTED_DATA_CATEGORIES}
    if category not in valid_categories:
        return HTMLResponse("Invalid data category", 400)
    db.add(IntakeFile(
        company_id=company_id,
        filename=filename.strip(),
        category=category,
        source=source.strip() or "Manual",
        notes=notes.strip() or None,
    ))
    old = c.stage
    if c.stage == "Data Requested":
        c.stage = "Data Received"
        c.next_action = "Review received files and classify usable data"
    db.add(TimelineEvent(
        company_id=company_id,
        event_type="Data Received",
        title=f"Data file registered: {filename.strip()}",
        details=f"Category: {category}" + (f" · Stage: {old} → {c.stage}" if old != c.stage else ""),
    ))
    db.commit()
    return RedirectResponse(f"/companies/{company_id}/data-intake", 303)


@app.get("/companies/{company_id}/readiness-framework", response_class=HTMLResponse)
def readiness_framework(company_id: int, request: Request, db: Session = Depends(get_db)):
    c = db.scalar(company_stmt(company_id))
    if not c:
        return HTMLResponse("Company not found", 404)
    ensure_v04_memory(db, c)
    db.commit()
    c = db.scalar(company_stmt(company_id))
    return render(request, "readiness_framework.html", {
        "company": c,
        "summaries": readiness_summaries(c),
        "files_received": len(c.intake_files),
        "status_options": READINESS_STATUS_OPTIONS,
    })


@app.post("/companies/{company_id}/readiness-evidence")
def save_readiness_evidence(
    company_id: int,
    module_no: int = Form(...),
    criterion_key: str = Form(...),
    status: str = Form(...),
    source: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
):
    if module_no not in READINESS_CRITERIA:
        return HTMLResponse("Invalid module", 400)
    valid_keys = {x["key"] for x in READINESS_CRITERIA[module_no]}
    if criterion_key not in valid_keys or status not in READINESS_STATUS_LABELS:
        return HTMLResponse("Invalid readiness evidence", 400)
    c = db.get(Company, company_id)
    if not c:
        return HTMLResponse("Company not found", 404)
    evidence = db.scalar(select(ReadinessEvidence).where(
        ReadinessEvidence.company_id == company_id,
        ReadinessEvidence.module_no == module_no,
        ReadinessEvidence.criterion_key == criterion_key,
    )) or ReadinessEvidence(company_id=company_id, module_no=module_no, criterion_key=criterion_key)
    db.add(evidence)
    evidence.status = status
    evidence.source = source.strip() or None
    evidence.notes = notes.strip() or None
    db.flush()

    if len(c.intake_files) > 0 and status != "awaiting" and c.stage in {"Data Requested", "Data Received"}:
        old = c.stage
        c.stage = "Data Readiness"
        c.next_action = "Complete evidence review and identify only blocking data gaps"
        db.add(TimelineEvent(company_id=company_id, event_type="Stage", title=f"Stage moved: {old} → Data Readiness"))

    db.commit()
    c = db.scalar(company_stmt(company_id))
    summary = module_readiness_summary(c, module_no)
    if summary["score"] is not None:
        r = db.scalar(select(Readiness).where(Readiness.company_id == company_id, Readiness.module_no == module_no)) or Readiness(
            company_id=company_id, module_no=module_no, module_name=MODULES[module_no]
        )
        db.add(r)
        r.score = summary["score"]
        r.status = f"{summary['score_label']} · {summary['review_progress']:.0f}% evidence reviewed"
        r.notes = "Calculated from weighted readiness evidence; not an LLM-generated score."
        all_summaries = readiness_summaries(c)
        if c.stage == "Data Readiness" and all(s["final"] for s in all_summaries):
            c.next_action = "Prepare and review the evidence-informed Solution Blueprint"
        db.add(TimelineEvent(
            company_id=company_id,
            event_type="Readiness",
            title=f"Evidence updated: Module {module_no} · {criterion_key} · {status}",
            details=(f"Readiness {summary['score']:.0f}% · {summary['score_label']} · {summary['review_progress']:.0f}% evidence reviewed"),
        ))
        db.commit()
    else:
        db.add(TimelineEvent(company_id=company_id, event_type="Readiness", title=f"Evidence reset: Module {module_no} · {criterion_key} · awaiting"))
        db.commit()
    return RedirectResponse(f"/companies/{company_id}/readiness-framework", 303)


@app.get("/companies/{company_id}/solution-blueprint", response_class=HTMLResponse)
def solution_blueprint(company_id: int, request: Request, db: Session = Depends(get_db)):
    c = db.scalar(company_stmt(company_id))
    if not c:
        return HTMLResponse("Company not found", 404)
    ensure_v04_memory(db, c)
    ensure_v05_decisions(db, c)
    db.commit()
    c = db.scalar(company_stmt(company_id))
    c.decisions.sort(key=lambda x: x.decided_at, reverse=True)
    selected = selected_module_nos(c)
    phases = [{"module_no": no, **MODULE_DETAILS[no]} for no in selected]
    operating_spine = []
    if 4 in selected:
        operating_spine.append({"en": "Quote", "zh": "報價"})
    if 5 in selected:
        operating_spine.extend([
            {"en": "Order", "zh": "訂單"},
            {"en": "Work Order", "zh": "工單"},
            {"en": "Production Events", "zh": "生產事件"},
        ])
    if 6 in selected:
        operating_spine.append({"en": "Analytics", "zh": "營運分析"})
    if not operating_spine:
        operating_spine = [{"en": "Operational Data", "zh": "營運資料"}, {"en": "AI Operations", "zh": "AI 營運"}]
    return render(request, "solution_blueprint.html", {
        "company": c,
        "memory": memory_groups(c),
        "summaries": readiness_summaries(c),
        "phases": phases,
        "operating_spine": operating_spine,
        "decisions": c.decisions,
        "files_received": len(c.intake_files),
        "blueprint_mode": "Evidence-informed" if c.intake_files else "Hypothesis · evidence pending",
    })


@app.post("/companies/{company_id}/decisions")
def add_decision(
    company_id: int,
    title: str = Form(...),
    decision: str = Form(...),
    rationale: str = Form(""),
    source: str = Form("Manual"),
    status: str = Form("Confirmed"),
    db: Session = Depends(get_db),
):
    if status not in {"Confirmed", "Pending", "Superseded"}:
        return HTMLResponse("Invalid decision status", 400)
    c = db.get(Company, company_id)
    if not c:
        return HTMLResponse("Company not found", 404)
    db.add(DecisionLog(
        company_id=company_id,
        title=title.strip(),
        decision=decision.strip(),
        rationale=rationale.strip() or None,
        source=source.strip() or "Manual",
        status=status,
    ))
    db.add(TimelineEvent(company_id=company_id, event_type="Decision", title=f"Decision recorded: {title.strip()}", details=status))
    db.commit()
    return RedirectResponse(f"/companies/{company_id}/solution-blueprint#decisions", 303)


@app.post("/companies/{company_id}/intake")
def save_intake(company_id: int, top_improvements: str = Form(""), primary_priority: str = Form(""), current_tools: str = Form(""), company_size: str = Form(""), owner_repetitive_task: str = Form(""), db: Session = Depends(get_db)):
    i = db.scalar(select(PreMeetingIntake).where(PreMeetingIntake.company_id == company_id)) or PreMeetingIntake(company_id=company_id)
    db.add(i)
    for f, v in {
        "top_improvements": top_improvements,
        "primary_priority": primary_priority,
        "current_tools": current_tools,
        "company_size": company_size,
        "owner_repetitive_task": owner_repetitive_task,
    }.items():
        setattr(i, f, v or None)
    c = db.get(Company, company_id)
    if c.stage == "New Lead":
        c.stage = "Meeting Booked"
    db.add(TimelineEvent(company_id=company_id, event_type="Intake", title="Pre-meeting intake updated"))
    db.commit()
    return RedirectResponse(f"/companies/{company_id}#intake", 303)


@app.get("/companies/{company_id}/discovery-meeting", response_class=HTMLResponse)
def discovery_meeting(company_id: int, request: Request, db: Session = Depends(get_db)):
    c = db.scalar(company_stmt(company_id))
    if not c:
        return HTMLResponse("Company not found", 404)
    return render(request, "discovery_meeting.html", {"company": c, "modules": MODULES})


@app.post("/companies/{company_id}/discovery-meeting")
def complete_discovery_meeting(
    company_id: int,
    current_flow: str = Form(""),
    biggest_bottleneck: str = Form(""),
    key_person_dependency: str = Form(""),
    repeated_questions: str = Form(""),
    quote_process: str = Form(""),
    production_tracking: str = Form(""),
    management_metrics: str = Form(""),
    priority_improvement: str = Form(""),
    existing_systems: str = Form(""),
    success_definition: str = Form(""),
    baseline_notes: str = Form(""),
    customer_words: str = Form(""),
    pain1: str = Form(""),
    pain2: str = Form(""),
    pain3: str = Form(""),
    module1: str = Form("Low"),
    module2: str = Form("Low"),
    module3: str = Form("Low"),
    module4: str = Form("Low"),
    module5: str = Form("Low"),
    module6: str = Form("Low"),
    next_action: str = Form(""),
    owner: str = Form(""),
    due_date: str = Form(""),
    db: Session = Depends(get_db),
):
    c = db.get(Company, company_id)
    d = db.scalar(select(Discovery).where(Discovery.company_id == company_id)) or Discovery(company_id=company_id)
    db.add(d)
    values = {
        "current_flow": current_flow,
        "biggest_bottleneck": biggest_bottleneck,
        "key_person_dependency": key_person_dependency,
        "repeated_questions": repeated_questions,
        "quote_process": quote_process,
        "production_tracking": production_tracking,
        "management_metrics": management_metrics,
        "priority_improvement": priority_improvement,
        "existing_systems": existing_systems,
        "success_definition": success_definition,
        "baseline_notes": baseline_notes,
        "customer_words": customer_words,
    }
    for f, v in values.items():
        setattr(d, f, v or None)
    db.flush()

    db.execute(delete(PainPoint).where(PainPoint.company_id == company_id))
    for idx, text in enumerate([p for p in [pain1, pain2, pain3] if p.strip()], 1):
        db.add(PainPoint(
            company_id=company_id,
            rank=idx,
            category=f"Priority {idx}",
            description=text.strip(),
            severity="High" if idx == 1 else "Medium",
            customer_quote=(customer_words or None) if idx == 1 else None,
        ))

    fit_values = {1: module1, 2: module2, 3: module3, 4: module4, 5: module5, 6: module6}
    for no, fit in fit_values.items():
        m = db.scalar(select(ModuleFit).where(ModuleFit.company_id == company_id, ModuleFit.module_no == no)) or ModuleFit(company_id=company_id, module_no=no, module_name=MODULES[no])
        db.add(m)
        m.fit = fit
        if fit == "High":
            m.reason = priority_improvement or biggest_bottleneck

    c.next_action = next_action or c.next_action
    c.owner = owner or c.owner
    c.due_date = date.fromisoformat(due_date) if due_date else c.due_date
    completion = discovery_completion(d)
    high_fit = any(v == "High" for v in fit_values.values())
    dod_ok = completion >= 75 and bool((c.next_action or "").strip()) and high_fit and bool((biggest_bottleneck or "").strip())
    old = c.stage
    gated_stages = PIPELINE_STAGES[PIPELINE_STAGES.index("Diagnosis Confirmed"):]
    if c.stage not in gated_stages:
        c.stage = "Diagnosis Confirmed" if dod_ok else "Discovery"
    diagnosis = f"主要瓶頸：{biggest_bottleneck or '待確認'}\n第一優先：{priority_improvement or pain1 or '待確認'}"
    db.flush()
    pains = db.scalars(select(PainPoint).where(PainPoint.company_id == company_id).order_by(PainPoint.rank)).all()
    fits = db.scalars(select(ModuleFit).where(ModuleFit.company_id == company_id).order_by(ModuleFit.module_no)).all()
    meeting = Meeting(company_id=company_id, meeting_type="Discovery", status="Completed", completed_at=datetime.utcnow(), completeness=completion, diagnosis_summary=diagnosis)
    db.add(meeting)
    db.flush()
    meeting.followup_draft = build_followup(c, d, pains, fits)
    db.add(TimelineEvent(company_id=company_id, event_type="Discovery", title=f"Discovery meeting completed · {completion}%", details=f"Stage: {old} → {c.stage}"))
    db.commit()
    return RedirectResponse(f"/companies/{company_id}?meeting=complete", 303)


@app.get("/companies/{company_id}/follow-up", response_class=HTMLResponse)
def followup(company_id: int, request: Request, db: Session = Depends(get_db)):
    c = db.scalar(company_stmt(company_id))
    if not c:
        return HTMLResponse("Company not found", 404)
    latest = sorted(c.meetings, key=lambda x: x.completed_at, reverse=True)[0] if c.meetings else None
    return render(request, "followup.html", {"company": c, "meeting": latest})


@app.post("/companies/{company_id}/overview")
def update_overview(company_id: int, stage: str = Form(...), owner: str = Form(""), next_action: str = Form(""), due_date: str = Form(""), fit_status: str = Form("Unknown"), db: Session = Depends(get_db)):
    c = db.scalar(company_stmt(company_id))
    old = c.stage
    completion = discovery_completion(c.discovery)
    gated_stages = PIPELINE_STAGES[PIPELINE_STAGES.index("Diagnosis Confirmed"):]
    high_fit = any(m.fit == "High" for m in c.module_fits)
    if old not in gated_stages and stage in gated_stages and (completion < 75 or not high_fit or not next_action.strip()):
        stage = "Discovery"
    c.stage = stage
    c.owner = owner or None
    c.next_action = next_action or None
    c.fit_status = fit_status
    c.due_date = date.fromisoformat(due_date) if due_date else None
    if old != stage:
        db.add(TimelineEvent(company_id=c.id, event_type="Stage", title=f"Stage moved: {old} → {stage}"))
    db.commit()
    return RedirectResponse(f"/companies/{company_id}", 303)


@app.post("/companies/{company_id}/discovery")
def save_discovery(company_id: int, current_flow: str = Form(""), biggest_bottleneck: str = Form(""), key_person_dependency: str = Form(""), existing_systems: str = Form(""), success_definition: str = Form(""), baseline_notes: str = Form(""), customer_words: str = Form(""), db: Session = Depends(get_db)):
    d = db.scalar(select(Discovery).where(Discovery.company_id == company_id)) or Discovery(company_id=company_id)
    db.add(d)
    for f, v in {
        "current_flow": current_flow,
        "biggest_bottleneck": biggest_bottleneck,
        "key_person_dependency": key_person_dependency,
        "existing_systems": existing_systems,
        "success_definition": success_definition,
        "baseline_notes": baseline_notes,
        "customer_words": customer_words,
    }.items():
        setattr(d, f, v or None)
    db.add(TimelineEvent(company_id=company_id, event_type="Discovery", title="Discovery record updated"))
    db.commit()
    return RedirectResponse(f"/companies/{company_id}#discovery", 303)


@app.post("/companies/{company_id}/pains")
def add_pain(company_id: int, category: str = Form(...), description: str = Form(...), severity: str = Form("Medium"), customer_quote: str = Form(""), db: Session = Depends(get_db)):
    ranks = db.scalars(select(PainPoint.rank).where(PainPoint.company_id == company_id)).all()
    rank = max(ranks) + 1 if ranks else 1
    db.add(PainPoint(company_id=company_id, rank=rank, category=category, description=description, severity=severity, customer_quote=customer_quote or None))
    db.commit()
    return RedirectResponse(f"/companies/{company_id}#discovery", 303)


@app.post("/companies/{company_id}/tasks")
def add_task(company_id: int, title: str = Form(...), owner: str = Form(""), due_date: str = Form(""), db: Session = Depends(get_db)):
    db.add(Task(company_id=company_id, title=title, owner=owner or None, due_date=date.fromisoformat(due_date) if due_date else None))
    db.commit()
    return RedirectResponse(f"/companies/{company_id}#tasks", 303)


@app.post("/tasks/{task_id}/toggle")
def toggle_task(task_id: int, db: Session = Depends(get_db)):
    t = db.get(Task, task_id)
    if not t:
        return HTMLResponse("Task not found", 404)
    t.done = not t.done
    cid = t.company_id
    db.commit()
    return RedirectResponse(f"/companies/{cid}#tasks", 303)


@app.post("/companies/{company_id}/readiness")
def save_readiness(company_id: int, module_no: int = Form(...), score: float = Form(...), status: str = Form(""), notes: str = Form(""), db: Session = Depends(get_db)):
    r = db.scalar(select(Readiness).where(Readiness.company_id == company_id, Readiness.module_no == module_no)) or Readiness(company_id=company_id, module_no=module_no, module_name=MODULES[module_no])
    db.add(r)
    r.score = max(0, min(100, score))
    r.status = status or None
    r.notes = notes or None
    db.add(TimelineEvent(company_id=company_id, event_type="Readiness", title=f"Readiness updated: {MODULES[module_no]} {r.score:.0f}%"))
    db.commit()
    return RedirectResponse(f"/companies/{company_id}#readiness", 303)
