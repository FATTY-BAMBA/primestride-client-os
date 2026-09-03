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
    Task, Readiness, TimelineEvent, PIPELINE_STAGES
)

BASE_DIR = Path(__file__).resolve().parent

MODULES = {
    1: "知識管理", 2: "AI 知識助理", 3: "AI 客服",
    4: "AI 報價", 5: "工單／生產管理", 6: "AI 數據分析",
}
DISCOVERY_REQUIRED = [
    "current_flow", "biggest_bottleneck", "key_person_dependency", "quote_process",
    "production_tracking", "management_metrics", "priority_improvement", "success_definition"
]


def seed_demo() -> None:
    ensure_schema()
    db = SessionLocal()
    try:
        if db.scalar(select(Company.id).limit(1)):
            return
        c = Company(
            name="ABC 印刷有限公司", industry="印刷", stage="Meeting Booked", owner="David",
            next_action="執行第一次 Discovery Meeting", due_date=date.today(), fit_status="Potential Fit"
        )
        db.add(c)
        db.flush()
        c.intake = PreMeetingIntake(
            top_improvements="報價速度、工單進度、營運數據",
            primary_priority="先解決報價依賴老闆",
            current_tools="Excel、LINE、既有 ERP、紙本工單",
            company_size="約 25 人",
            owner_repetitive_task="特殊價格需要老闆本人確認"
        )
        db.add(TimelineEvent(company_id=c.id, event_type="Meeting", title="Discovery meeting booked"))
        db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Do not make the whole deployment fail if a preview database is temporarily
    # unavailable. Requests also lazily initialize the schema through get_db().
    try:
        ensure_schema()
        seed_demo()
    except Exception as exc:
        print(f"[startup] database initialization warning: {exc!r}")
    yield


app = FastAPI(title="PrimeStride Client OS", version="0.2.1", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def company_stmt(company_id: int):
    return select(Company).where(Company.id == company_id).options(
        selectinload(Company.intake), selectinload(Company.pains), selectinload(Company.discovery),
        selectinload(Company.meetings), selectinload(Company.module_fits), selectinload(Company.tasks),
        selectinload(Company.readiness), selectinload(Company.timeline)
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
    """Use Starlette's current request-first TemplateResponse signature."""
    return templates.TemplateResponse(
        request=request,
        name=name,
        context=context,
    )


@app.get("/health")
def health():
    db_kind = "postgresql" if DATABASE_URL.startswith("postgres") else "sqlite-demo"
    return {
        "status": "ok",
        "service": "PrimeStride Client OS",
        "version": "0.2.1",
        "database": db_kind,
    }


@app.get("/", response_class=HTMLResponse)
def pipeline(request: Request, db: Session = Depends(get_db)):
    # If a new Vercel instance starts without a persistent database, make sure the
    # disposable demo record exists instead of showing an empty/failed page.
    if not db.scalar(select(Company.id).limit(1)):
        db.close()
        seed_demo()
        db = SessionLocal()
    companies = db.scalars(select(Company).order_by(Company.updated_at.desc())).all()
    buckets = {stage: [] for stage in PIPELINE_STAGES}
    for c in companies:
        buckets.setdefault(c.stage, []).append(c)
    visible = [s for s in PIPELINE_STAGES if buckets.get(s)] or PIPELINE_STAGES[:5]
    return render(request, "pipeline.html", {"buckets": buckets, "stages": visible})


@app.post("/companies")
def create_company(name: str = Form(...), industry: str = Form(""), owner: str = Form(""), db: Session = Depends(get_db)):
    c = Company(name=name, industry=industry or None, owner=owner or None, stage="New Lead", next_action="安排第一次探索會議")
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
    c.pains.sort(key=lambda x: x.rank)
    c.module_fits.sort(key=lambda x: x.module_no)
    c.readiness.sort(key=lambda x: x.module_no)
    c.timeline.sort(key=lambda x: x.created_at, reverse=True)
    c.meetings.sort(key=lambda x: x.completed_at, reverse=True)
    return render(request, "company.html", {
        "company": c,
        "stages": PIPELINE_STAGES,
        "modules": MODULES,
        "completion": discovery_completion(c.discovery),
    })


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
        m = db.scalar(select(ModuleFit).where(
            ModuleFit.company_id == company_id,
            ModuleFit.module_no == no,
        )) or ModuleFit(company_id=company_id, module_no=no, module_name=MODULES[no])
        db.add(m)
        m.fit = fit
        if fit == "High":
            m.reason = priority_improvement or biggest_bottleneck

    c.next_action = next_action or c.next_action
    c.owner = owner or c.owner
    c.due_date = date.fromisoformat(due_date) if due_date else c.due_date
    completion = discovery_completion(d)
    high_fit = any(v == "High" for v in fit_values.values())
    dod_ok = (
        completion >= 75
        and bool((c.next_action or "").strip())
        and high_fit
        and bool((biggest_bottleneck or "").strip())
    )
    old = c.stage
    c.stage = "Diagnosis Confirmed" if dod_ok else "Discovery"
    diagnosis = f"主要瓶頸：{biggest_bottleneck or '待確認'}\n第一優先：{priority_improvement or pain1 or '待確認'}"
    db.flush()
    pains = db.scalars(select(PainPoint).where(PainPoint.company_id == company_id).order_by(PainPoint.rank)).all()
    fits = db.scalars(select(ModuleFit).where(ModuleFit.company_id == company_id).order_by(ModuleFit.module_no)).all()
    meeting = Meeting(
        company_id=company_id,
        meeting_type="Discovery",
        status="Completed",
        completed_at=datetime.utcnow(),
        completeness=completion,
        diagnosis_summary=diagnosis,
    )
    db.add(meeting)
    db.flush()
    meeting.followup_draft = build_followup(c, d, pains, fits)
    db.add(TimelineEvent(
        company_id=company_id,
        event_type="Discovery",
        title=f"Discovery meeting completed · {completion}%",
        details=f"Stage: {old} → {c.stage}",
    ))
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
    if stage in gated_stages and (completion < 75 or not high_fit or not next_action.strip()):
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
    db.add(PainPoint(
        company_id=company_id,
        rank=rank,
        category=category,
        description=description,
        severity=severity,
        customer_quote=customer_quote or None,
    ))
    db.commit()
    return RedirectResponse(f"/companies/{company_id}#discovery", 303)


@app.post("/companies/{company_id}/tasks")
def add_task(company_id: int, title: str = Form(...), owner: str = Form(""), due_date: str = Form(""), db: Session = Depends(get_db)):
    db.add(Task(
        company_id=company_id,
        title=title,
        owner=owner or None,
        due_date=date.fromisoformat(due_date) if due_date else None,
    ))
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
    r = db.scalar(select(Readiness).where(
        Readiness.company_id == company_id,
        Readiness.module_no == module_no,
    )) or Readiness(company_id=company_id, module_no=module_no, module_name=MODULES[module_no])
    db.add(r)
    r.score = max(0, min(100, score))
    r.status = status or None
    r.notes = notes or None
    db.add(TimelineEvent(
        company_id=company_id,
        event_type="Readiness",
        title=f"Readiness updated: {MODULES[module_no]} {r.score:.0f}%",
    ))
    db.commit()
    return RedirectResponse(f"/companies/{company_id}#readiness", 303)
