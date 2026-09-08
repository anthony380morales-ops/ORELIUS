"""
Orchestration DB models — additive, non-destructive (directive §60).

Phase 1 introduces the durable spine for the mission system:
  • Mission     — a persisted mission packet + lifecycle status
  • SystemFlag  — durable kill switches / run-mode overrides
  • AgentRun    — one observability record per agent invocation (§42)

More tables (touchpoints, opportunities, conversations, prospects, cost_events,
compliance_reviews, allocation_snapshots, …) land in their respective phases.
"""
from sqlalchemy import Column, Integer, String, Boolean, JSON, DateTime, Float, Index
from datetime import datetime
from ..database import Base


class Mission(Base):
    __tablename__ = "missions"

    id = Column(Integer, primary_key=True, index=True)
    mission_id = Column(String(64), unique=True, index=True, nullable=False)
    status = Column(String(24), index=True, default="CREATED")
    brand = Column(String(16), index=True)
    platform = Column(String(24), index=True)
    objective = Column(String(48))
    priority = Column(String(16), default="medium")

    packet = Column(JSON, default=dict)          # the full validated MissionPacket
    result = Column(JSON, default=dict)           # executor result / evaluation
    cost_usd = Column(Float, default=0.0)

    # Queue mechanics (directive §9): retries, backoff, dedup, scheduling.
    dedup_key = Column(String(80), index=True, nullable=True)
    attempts = Column(Integer, default=0)
    max_attempts = Column(Integer, default=3)
    next_attempt_at = Column(DateTime, nullable=True, index=True)  # backoff gate
    scheduled_at = Column(DateTime, nullable=True, index=True)     # future execution
    error = Column(String(512), nullable=True)
    executor = Column(String(32), default="athena")               # who runs it

    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True, index=True)


class Prospect(Base):
    """Persistent conversation memory for one prospect (directive §19).

    One row per prospect per brand. Recent turns are kept inline (bounded JSON) so
    the conversation survives across sessions and the strategist can reason over
    history without a join. Additive, non-destructive."""
    __tablename__ = "prospects"

    id = Column(Integer, primary_key=True, index=True)
    prospect_id = Column(String(80), unique=True, index=True, nullable=False)
    brand = Column(String(16), index=True)
    platform = Column(String(24), index=True)
    handle = Column(String(120), nullable=True)          # external handle / thread ref

    stage = Column(String(24), index=True, default="new")
    concern = Column(String(120), nullable=True)          # their critical savings point
    score = Column(Float, default=0.0)                    # qualification signal 0-1

    consent = Column(Boolean, default=False)              # invited/permitted to DM
    do_not_contact = Column(Boolean, default=False, index=True)

    turns = Column(JSON, default=list)                    # bounded recent [{role,text,ts}]
    notes = Column(JSON, default=dict)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_inbound_at = Column(DateTime, nullable=True)


class TouchpointEvent(Base):
    """One recorded meaningful touchpoint and its outcome (directive §17, §18, §42).

    The event log the analytics roll up into the North-Star ratio and the per-action
    performance signal the allocation engine consumes. Additive."""
    __tablename__ = "touchpoint_events"

    id = Column(Integer, primary_key=True, index=True)
    day = Column(String(10), index=True)                  # YYYY-MM-DD (PT)
    brand = Column(String(16), index=True)
    platform = Column(String(24), nullable=True)
    action = Column(String(32), index=True)               # TouchpointAction value
    outcome = Column(String(16), index=True, default="meaningful")  # none|meaningful|qualified
    prospect_id = Column(String(80), nullable=True, index=True)
    mission_id = Column(String(64), nullable=True, index=True)
    cost_usd = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class AllocationSnapshot(Base):
    """One day's touchpoint allocation plan (directive §17, §18). Additive.

    Records how the daily touchpoint budget was distributed across brands and
    meaningful action types, plus the inputs (baseline vs performance weights) so
    the allocation is auditable and the adaptive engine can learn against it."""
    __tablename__ = "allocation_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    day = Column(String(10), index=True)                 # YYYY-MM-DD (PT)
    total = Column(Integer, default=0)                    # touchpoints planned
    mode = Column(String(16), default="simulation")
    plan = Column(JSON, default=dict)                     # {brand: {action: n, ...}, ...}
    inputs = Column(JSON, default=dict)                   # weights + flags used
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class SystemFlag(Base):
    __tablename__ = "system_flags"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(48), unique=True, index=True, nullable=False)
    value = Column(Boolean, default=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id = Column(Integer, primary_key=True, index=True)
    trace_id = Column(String(48), index=True)
    mission_id = Column(String(64), index=True, nullable=True)
    agent = Column(String(48), index=True)
    task = Column(String(64))
    model = Column(String(48), nullable=True)
    provider = Column(String(48), nullable=True)
    latency_ms = Column(Integer, default=0)
    tokens = Column(Integer, nullable=True)
    cost_usd = Column(Float, default=0.0)
    status = Column(String(24), default="ok")
    quality = Column(Float, nullable=True)
    error = Column(String(512), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


Index("ix_agent_runs_mission_agent", AgentRun.mission_id, AgentRun.agent)
