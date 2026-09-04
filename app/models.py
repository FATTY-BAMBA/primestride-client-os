from __future__ import annotations
from datetime import datetime, date
from sqlalchemy import String, Text, Integer, DateTime, Date, ForeignKey, Boolean, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base

PIPELINE_STAGES = [
    "New Lead", "Meeting Booked", "Discovery", "Diagnosis Confirmed",
    "Solution Fit", "Data Requested", "Data Received", "Data Readiness",
    "Client Blueprint", "Proposal", "Won", "Nurture", "Lost",
    "Implementation", "Go Live", "Optimization"
]

class Company(Base):
    __tablename__ = "companies"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    industry: Mapped[str | None] = mapped_column(String(120), nullable=True)
    stage: Mapped[str] = mapped_column(String(60), default="New Lead")
    owner: Mapped[str | None] = mapped_column(String(120), nullable=True)
    next_action: Mapped[str | None] = mapped_column(String(300), nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    next_meeting: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    fit_status: Mapped[str | None] = mapped_column(String(30), default="Unknown", nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    intake: Mapped[PreMeetingIntake | None] = relationship(back_populates="company", cascade="all, delete-orphan", uselist=False)
    pains: Mapped[list[PainPoint]] = relationship(back_populates="company", cascade="all, delete-orphan")
    discovery: Mapped[Discovery | None] = relationship(back_populates="company", cascade="all, delete-orphan", uselist=False)
    meetings: Mapped[list[Meeting]] = relationship(back_populates="company", cascade="all, delete-orphan")
    module_fits: Mapped[list[ModuleFit]] = relationship(back_populates="company", cascade="all, delete-orphan")
    tasks: Mapped[list[Task]] = relationship(back_populates="company", cascade="all, delete-orphan")
    readiness: Mapped[list[Readiness]] = relationship(back_populates="company", cascade="all, delete-orphan")
    timeline: Mapped[list[TimelineEvent]] = relationship(back_populates="company", cascade="all, delete-orphan")
    memory_items: Mapped[list[ClientMemory]] = relationship(back_populates="company", cascade="all, delete-orphan")
    intake_files: Mapped[list[IntakeFile]] = relationship(back_populates="company", cascade="all, delete-orphan")

class PreMeetingIntake(Base):
    __tablename__ = "pre_meeting_intakes"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), unique=True)
    top_improvements: Mapped[str | None] = mapped_column(Text, nullable=True)
    primary_priority: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_tools: Mapped[str | None] = mapped_column(Text, nullable=True)
    company_size: Mapped[str | None] = mapped_column(String(80), nullable=True)
    owner_repetitive_task: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    company: Mapped[Company] = relationship(back_populates="intake")

class Discovery(Base):
    __tablename__ = "discoveries"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), unique=True)
    current_flow: Mapped[str | None] = mapped_column(Text, nullable=True)
    biggest_bottleneck: Mapped[str | None] = mapped_column(Text, nullable=True)
    key_person_dependency: Mapped[str | None] = mapped_column(Text, nullable=True)
    repeated_questions: Mapped[str | None] = mapped_column(Text, nullable=True)
    quote_process: Mapped[str | None] = mapped_column(Text, nullable=True)
    production_tracking: Mapped[str | None] = mapped_column(Text, nullable=True)
    management_metrics: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority_improvement: Mapped[str | None] = mapped_column(Text, nullable=True)
    existing_systems: Mapped[str | None] = mapped_column(Text, nullable=True)
    success_definition: Mapped[str | None] = mapped_column(Text, nullable=True)
    baseline_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    customer_words: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    company: Mapped[Company] = relationship(back_populates="discovery")

class Meeting(Base):
    __tablename__ = "meetings"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    meeting_type: Mapped[str] = mapped_column(String(60), default="Discovery")
    status: Mapped[str] = mapped_column(String(30), default="Completed")
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completeness: Mapped[float] = mapped_column(Float, default=0)
    diagnosis_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    followup_draft: Mapped[str | None] = mapped_column(Text, nullable=True)
    company: Mapped[Company] = relationship(back_populates="meetings")

class PainPoint(Base):
    __tablename__ = "pain_points"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    rank: Mapped[int] = mapped_column(Integer, default=1)
    category: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(20), default="Medium")
    customer_quote: Mapped[str | None] = mapped_column(Text, nullable=True)
    company: Mapped[Company] = relationship(back_populates="pains")

class ModuleFit(Base):
    __tablename__ = "module_fits"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    module_no: Mapped[int] = mapped_column(Integer)
    module_name: Mapped[str] = mapped_column(String(100))
    fit: Mapped[str] = mapped_column(String(20), default="Low")
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    company: Mapped[Company] = relationship(back_populates="module_fits")

class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    title: Mapped[str] = mapped_column(String(250))
    owner: Mapped[str | None] = mapped_column(String(120), nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    done: Mapped[bool] = mapped_column(Boolean, default=False)
    company: Mapped[Company] = relationship(back_populates="tasks")

class Readiness(Base):
    __tablename__ = "readiness"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    module_no: Mapped[int] = mapped_column(Integer)
    module_name: Mapped[str] = mapped_column(String(100))
    score: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    company: Mapped[Company] = relationship(back_populates="readiness")

class TimelineEvent(Base):
    __tablename__ = "timeline_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    event_type: Mapped[str] = mapped_column(String(80))
    title: Mapped[str] = mapped_column(String(250))
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    company: Mapped[Company] = relationship(back_populates="timeline")

class ClientMemory(Base):
    __tablename__ = "client_memory"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    kind: Mapped[str] = mapped_column(String(30), index=True)
    title: Mapped[str] = mapped_column(String(250))
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str | None] = mapped_column(String(120), nullable=True)
    confidence: Mapped[str] = mapped_column(String(20), default="High")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    company: Mapped[Company] = relationship(back_populates="memory_items")

class IntakeFile(Base):
    __tablename__ = "intake_files"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    filename: Mapped[str] = mapped_column(String(300))
    category: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(40), default="Received")
    source: Mapped[str] = mapped_column(String(80), default="Manual")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    company: Mapped[Company] = relationship(back_populates="intake_files")
