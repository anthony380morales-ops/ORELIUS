"""
Shared Memory model — the durable ORELIUS <-> LUCIUS memory hub.

Every event either system records is a row here. ORELIUS reads the most recent
rows into its persona each turn; LUCIUS reads/writes them via the /api/memory
endpoint. Persisted in Postgres so it survives restarts and is reachable by both.
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, Float, JSON
from datetime import datetime
from ..database import Base


class SharedMemoryEvent(Base):
    __tablename__ = "shared_memory"

    id = Column(Integer, primary_key=True, index=True)
    ts = Column(Float, index=True)                       # epoch seconds (ordering)
    actor = Column(String(64), index=True, default="ORELIUS")  # ORELIUS | LUCIUS
    kind = Column(String(64), default="note")            # exchange | action | note | ...
    content = Column(Text, nullable=False)
    meta = Column(JSON, default=dict)
    # naive UTC to match the timestamp-without-tz column (asyncpg rejects tz-aware here)
    created_at = Column(DateTime, default=datetime.utcnow)

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "ts": self.ts,
            "actor": self.actor,
            "kind": self.kind,
            "content": self.content,
            "meta": self.meta or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
