"""
Persona Profile — ORELIUS's living understanding of the Master's personality.

This is the memory behind ORELIUS's "normal AI chatbot" side: over ordinary
conversations he learns the Master's communication style, tone, interests and
preferences, and tailors his replies to flow with that personality.

IMPORTANT — this is deliberately isolated from the daily Financial Intelligence
automation. That pipeline (finance_intel.py) has its own strict, non-negotiable
structure and its own system prompt; nothing here touches it. The personality a
persona profile encodes only ever shapes conversational chat, never how finance
data is gathered, filtered, or synthesized.

A single durable row (id=1) holds the whole profile as compact JSON so it can
evolve in place without schema churn.
"""
from sqlalchemy import Column, Integer, JSON, DateTime
from datetime import datetime
from ..database import Base


class PersonaProfile(Base):
    __tablename__ = "persona_profile"

    id = Column(Integer, primary_key=True, index=True)  # always 1 (single Master)
    # Compact JSON: communication_style, tone, interests, values, likes,
    # dislikes, notable_facts, summary — see PersonaProfileManager.
    profile = Column(JSON, default=dict)
    # How many exchanges have been observed since the profile was last refreshed
    # (drives the low-frequency reflection so we don't spend credits every turn).
    exchanges_since_update = Column(Integer, default=0)
    # Total exchanges ever observed — a rough confidence signal.
    total_exchanges = Column(Integer, default=0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
