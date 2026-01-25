"""
Aleph Swarm Coordination Module.

This module provides utilities for coordinating multi-agent swarms using Aleph's
shared memory infrastructure. All functions are pure (no classes) and return
JSON-serializable dicts.

## Core Concepts

### Agent State
Each agent has a state dict tracking its identity, status, and findings:
    >>> from aleph.swarm import create_agent_state, add_finding
    >>> agent = create_agent_state("explorer-1", "explorer", status="active")
    >>> agent = add_finding(agent, {"pattern": "singleton"}, source="core.py")

### Swarm Coordination
Swarms coordinate multiple agents with messaging:
    >>> from aleph.swarm import create_swarm_state, register_agent, send_message
    >>> swarm = create_swarm_state("analysis-swarm")
    >>> swarm = register_agent(swarm, agent)
    >>> swarm = send_message(swarm, "explorer-1", "architect", "finding", data)

### Context Patterns
Standard naming patterns for Aleph context IDs:
    >>> from aleph.swarm import agent_context_id, shared_context_id, task_context_id
    >>> agent_context_id("explorer-1", "workspace")  # "explorer-1-workspace"
    >>> shared_context_id("analysis", "kb")          # "swarm-analysis-kb"
    >>> task_context_id("fix-123", "findings")       # "task-fix-123-findings"

### Progress Tracking
Monitor task completion:
    >>> from aleph.swarm import create_progress_tracker, update_progress
    >>> tracker = create_progress_tracker(total_items=10)
    >>> tracker = update_progress(tracker, completed=3, current_item="file3.py")

## Architecture Notes

This module follows the Aleph Swarm 2.0 architecture:
- All functions are pure (no side effects, return new dicts)
- All return values are JSON-serializable
- Context naming follows standard patterns (agent-*, swarm-*, task-*)
- Designed to work with Claude Code's Teammate tool for coordination
"""

from aleph.swarm.coordination import (
    # Agent State Management
    create_agent_state,
    update_agent_state,
    add_finding,

    # Swarm Coordination
    create_swarm_state,
    register_agent,
    send_message,
    broadcast_message,
    get_messages_for,
    swarm_status_report,

    # Progress Tracking
    create_progress_tracker,
    update_progress,
    get_progress_percentage,

    # Context Patterns
    agent_context_id,
    shared_context_id,
    task_context_id,

    # Utilities
    mark_messages_read,
    get_agent_findings,
    merge_swarm_findings,
)

__all__ = [
    # Agent State Management
    "create_agent_state",
    "update_agent_state",
    "add_finding",

    # Swarm Coordination
    "create_swarm_state",
    "register_agent",
    "send_message",
    "broadcast_message",
    "get_messages_for",
    "swarm_status_report",

    # Progress Tracking
    "create_progress_tracker",
    "update_progress",
    "get_progress_percentage",

    # Context Patterns
    "agent_context_id",
    "shared_context_id",
    "task_context_id",

    # Utilities
    "mark_messages_read",
    "get_agent_findings",
    "merge_swarm_findings",
]
