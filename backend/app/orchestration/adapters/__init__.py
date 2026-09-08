"""Executor adapters — ORELIUS reaches each ecosystem executor through a clean,
simulation-first adapter (directive §13, §39). ATHENA now; HIGGBOT/LUCIUS next."""
from .athena_adapter import athena_adapter, AthenaAdapter, translate as translate_athena_job  # noqa: F401
