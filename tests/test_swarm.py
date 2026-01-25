"""Tests for Aleph swarm coordination utilities."""

from __future__ import annotations

from aleph.swarm import (
    create_agent_state,
    update_agent_state,
    add_finding,
    create_swarm_state,
    register_agent,
    send_message,
    broadcast_message,
    get_messages_for,
    mark_messages_read,
    swarm_status_report,
    create_progress_tracker,
    update_progress,
    get_progress_percentage,
    agent_context_id,
    shared_context_id,
    task_context_id,
)


def test_agent_state_updates_are_immutable() -> None:
    state = create_agent_state("agent-1", "explorer", status="idle")
    updated = update_agent_state(state, status="active", metadata={"task": "scan"})

    assert state["status"] == "idle"
    assert updated["status"] == "active"
    assert updated["metadata"]["task"] == "scan"


def test_add_finding_appends_entry() -> None:
    state = create_agent_state("agent-1", "explorer")
    updated = add_finding(state, {"issue": "x"}, source="file.py:10")

    assert state["findings"] == []
    assert len(updated["findings"]) == 1
    entry = updated["findings"][0]
    assert entry["content"] == {"issue": "x"}
    assert entry["source"] == "file.py:10"


def test_swarm_messaging_and_report() -> None:
    agent = create_agent_state("agent-1", "explorer")
    agent = add_finding(agent, {"note": "found"}, source="scan")

    swarm = create_swarm_state("analysis")
    swarm = register_agent(swarm, agent)
    swarm = send_message(swarm, "agent-1", "lead", "finding", {"issue": "x"})
    swarm = broadcast_message(swarm, "agent-1", "notice", "hello")

    msgs = get_messages_for(swarm, "lead")
    assert len(msgs) == 2

    swarm = mark_messages_read(swarm, "lead")
    assert all(msg["read"] for msg in get_messages_for(swarm, "lead"))

    report = swarm_status_report(swarm)
    assert report["agent_count"] == 1
    assert report["message_count"] == 2
    assert report["total_findings"] == 1


def test_progress_tracking_and_context_ids() -> None:
    tracker = create_progress_tracker(total_items=4)
    updated = update_progress(tracker, completed=2, current_item="file2.py")

    assert tracker["completed"] == 0
    assert updated["completed"] == 2
    assert get_progress_percentage(updated) == 50.0

    assert agent_context_id("agent-1", "workspace") == "agent-1-workspace"
    assert shared_context_id("analysis", "kb") == "swarm-analysis-kb"
    assert task_context_id("fix-123", "findings") == "task-fix-123-findings"
