"""Aleph Framework - Recursive Language Models (RLMs) for unbounded context.

Aleph lets an LLM *programmatically interact* with context stored as a variable
inside a sandboxed Python REPL, enabling scalable reasoning over large inputs.

Exports:
- Aleph: main class
- create_aleph: factory
- AlephConfig: configuration dataclass
- cocap: coherence capacity monitoring module
"""

from __future__ import annotations

from .core import Aleph
from .config import AlephConfig, create_aleph
from .types import (
    ContentFormat,
    ContextType,
    ContextMetadata,
    ContextCollection,
    ExecutionResult,
    SubQueryResult,
    ActionType,
    ParsedAction,
    TrajectoryStep,
    AlephResponse,
    Budget,
    BudgetStatus,
)
from . import cocap

__all__ = [
    "Aleph",
    "AlephConfig",
    "create_aleph",
    "ContentFormat",
    "ContextType",
    "ContextMetadata",
    "ContextCollection",
    "ExecutionResult",
    "SubQueryResult",
    "ActionType",
    "ParsedAction",
    "TrajectoryStep",
    "AlephResponse",
    "Budget",
    "BudgetStatus",
    "cocap",
]

__version__ = "0.7.5"
