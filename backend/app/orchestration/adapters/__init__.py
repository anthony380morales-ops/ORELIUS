"""Executor adapters — ORELIUS reaches each ecosystem executor through a clean,
simulation-first adapter (directive §13, §39). ATHENA + HIGGBOT now; LUCIUS next."""
from .athena_adapter import athena_adapter, AthenaAdapter, translate as translate_athena_job  # noqa: F401
from .higgbot_adapter import higgbot_adapter, HiggbotAdapter  # noqa: F401
